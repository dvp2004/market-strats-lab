from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_candidate_reconciliation import (
    build_current_paper_candidate_reconciliation,
    save_phase21b_regime_candidate_reconciliation,
)


def _phase21a_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "master_strategy_classification": "provisional_core_candidate_for_further_research",
                "regime_robustness_score": 61.48,
                "worst_max_drawdown_pct": -24.12,
                "classification_blocking_reasons": "",
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_gld_tlt_50_30_10_10",
                "master_strategy_classification": "provisional_core_inception_limited_for_further_research",
                "regime_robustness_score": 56.32,
                "worst_max_drawdown_pct": -42.73,
                "classification_blocking_reasons": "asset_inception_limited_regime_history",
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "master_strategy_classification": "provisional_high_caveat_candidate_for_further_research",
                "regime_robustness_score": 51.82,
                "worst_max_drawdown_pct": -28.02,
                "classification_blocking_reasons": "btc_inception_limited_pre_2014_regime_history",
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "master_strategy_classification": "rejected_regime_fragile",
                "regime_robustness_score": 13.39,
                "worst_max_drawdown_pct": -65.22,
                "classification_blocking_reasons": "severe_drawdown_worse_than_minus_50pct",
            },
        ]
    )


def _targets_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "primary_paper_candidate_clean_growth",
                "asset": "SPY",
                "target_weight": 0.6,
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "primary_paper_candidate_clean_growth",
                "asset": "QQQ",
                "target_weight": 0.4,
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "SPY",
                "target_weight": 0.5,
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "QQQ",
                "target_weight": 0.45,
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "candidate_role": "high_growth_high_caveat_btc_candidate",
                "asset": "BTC-USD",
                "target_weight": 0.05,
            },
        ]
    )


def _orders_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "asset": "SPY",
                "paper_order_allowed": True,
            },
            {
                "canonical_candidate_id": "canonical_inverse_vol_63d_btc_usd_qqq_spy",
                "asset": "BTC-USD",
                "paper_order_allowed": True,
            },
        ]
    )


def _write_sources(tmp_path: Path) -> dict:
    regime_dir = tmp_path / "strategy_factory" / "regime_stress"
    finalist_dir = tmp_path / "strategy_factory" / "finalist_validation"
    paper_dir = tmp_path / "paper_trading" / "finalist_tracking"
    regime_dir.mkdir(parents=True)
    finalist_dir.mkdir(parents=True)
    paper_dir.mkdir(parents=True)
    phase21a = _phase21a_frame()
    for name in [
        "phase21a_master_strategy_candidates.csv",
        "phase21a_regime_robustness_scores.csv",
        "phase21a_regime_robustness_score_components.csv",
        "phase21a_candidate_regime_summary.csv",
    ]:
        phase21a.to_csv(regime_dir / name, index=False)
    pd.DataFrame(
        {
            "canonical_candidate_id": [
                "canonical_spy_qqq_60_40",
                "canonical_inverse_vol_63d_btc_usd_qqq_spy",
            ]
        }
    ).to_csv(finalist_dir / "phase19b_recommended_paper_tracking_set.csv", index=False)
    _targets_frame().to_csv(paper_dir / "finalist_paper_targets.csv", index=False)
    _orders_frame().to_csv(paper_dir / "finalist_paper_orders_preview.csv", index=False)
    return {
        "phase21b_regime_candidate_reconciliation": {
            "enabled": True,
            "output_dir": str(tmp_path / "strategy_factory" / "regime_reconciliation"),
            "dashboard_dir": str(
                tmp_path / "strategy_factory" / "regime_reconciliation" / "dashboard"
            ),
            "source_regime_stress_dir": str(regime_dir),
            "source_finalist_validation_dir": str(finalist_dir),
            "source_paper_tracking_dir": str(paper_dir),
            "max_recommended_paper_candidates": 4,
            "max_core_candidates": 2,
            "max_high_caveat_candidates": 2,
            "require_no_promotion": True,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }


def test_missing_phase21a_output_fails_closed(tmp_path):
    config = _write_sources(tmp_path)
    (tmp_path / "strategy_factory" / "regime_stress" / "phase21a_master_strategy_candidates.csv").unlink()

    outputs = save_phase21b_regime_candidate_reconciliation(
        config=config,
        reports_dir=tmp_path,
    )
    summary = pd.read_csv(outputs["summary"]).iloc[0]

    assert summary["phase21b_decision"] == "regime_candidate_reconciliation_failed_missing_sources"
    assert not bool(summary["all_gates_passed"])


def test_current_paper_candidates_are_reconciled_against_phase21a():
    current = build_current_paper_candidate_reconciliation(
        targets=_targets_frame(),
        orders=_orders_frame(),
        phase21a=_phase21a_frame(),
    )

    assert set(current["canonical_candidate_id"]) == {
        "canonical_spy_qqq_60_40",
        "canonical_inverse_vol_63d_btc_usd_qqq_spy",
    }


def test_spy_qqq_60_40_becomes_reference_only_when_regime_fragile():
    current = build_current_paper_candidate_reconciliation(
        targets=_targets_frame(),
        orders=_orders_frame(),
        phase21a=_phase21a_frame(),
    )
    spy = current.loc[current["canonical_candidate_id"] == "canonical_spy_qqq_60_40"].iloc[0]

    assert spy["phase21a_reconciliation_status"] == "keep_as_reference_only"
    assert spy["paper_tracking_recommendation"] == "reference_only"


def test_btc_candidate_remains_high_caveat():
    current = build_current_paper_candidate_reconciliation(
        targets=_targets_frame(),
        orders=_orders_frame(),
        phase21a=_phase21a_frame(),
    )
    btc = current.loc[
        current["canonical_candidate_id"] == "canonical_inverse_vol_63d_btc_usd_qqq_spy"
    ].iloc[0]

    assert btc["phase21a_reconciliation_status"] == "keep_as_high_caveat_candidate"
    assert btc["paper_tracking_recommendation"] == "provisional_high_caveat_candidate"


def test_recommendation_outputs_include_phase6_and_gld_tlt(tmp_path):
    outputs = save_phase21b_regime_candidate_reconciliation(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    shortlist = pd.read_csv(outputs["paper_shortlist_recommendation"])

    assert "phase6b_loose_relief_execution_realistic_overlay" in set(
        shortlist["canonical_candidate_id"]
    )
    assert "canonical_spy_qqq_gld_tlt_50_30_10_10" in set(shortlist["canonical_candidate_id"])


def test_recommendation_shortlist_respects_max_candidate_count(tmp_path):
    outputs = save_phase21b_regime_candidate_reconciliation(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    shortlist = pd.read_csv(outputs["paper_shortlist_recommendation"])

    assert len(shortlist) <= 4


def test_no_candidate_is_promoted_and_safety_flags_false(tmp_path):
    outputs = save_phase21b_regime_candidate_reconciliation(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    conclusion = pd.read_csv(outputs["conclusion"]).iloc[0]
    shortlist = pd.read_csv(outputs["paper_shortlist_recommendation"])

    assert not bool(conclusion["promotion_allowed"])
    assert not bool(conclusion["live_trading_allowed"])
    assert not bool(conclusion["real_money_allowed"])
    assert not bool(conclusion["broker_api_integration_allowed"])
    assert shortlist["promotion_allowed"].eq(False).all()


def test_dashboard_markdown_includes_safety_language(tmp_path):
    outputs = save_phase21b_regime_candidate_reconciliation(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    dashboard = outputs["dashboard_index"].read_text(encoding="utf-8")

    assert "NO LIVE TRADING" in dashboard
    assert "NO REAL MONEY" in dashboard
    assert "NO BROKER/API" in dashboard
    assert "NO STRATEGY PROMOTION" in dashboard
    assert "RESEARCH RECONCILIATION ONLY" in dashboard


def test_candidate_delta_report_has_expected_status_changes(tmp_path):
    outputs = save_phase21b_regime_candidate_reconciliation(
        config=_write_sources(tmp_path),
        reports_dir=tmp_path,
    )
    delta = pd.read_csv(outputs["candidate_delta_report"])
    changes = dict(zip(delta["canonical_candidate_id"], delta["status_change"], strict=False))

    assert (
        changes["canonical_spy_qqq_60_40"]
        == "paper_tracked_clean_growth_to_reference_only_regime_fragile"
    )
    assert (
        changes["canonical_inverse_vol_63d_btc_usd_qqq_spy"]
        == "remains_high_caveat_candidate"
    )
    assert (
        changes["phase6b_loose_relief_execution_realistic_overlay"]
        == "newly_reintroduced_provisional_core"
    )
