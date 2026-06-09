from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.strategy_factory_finalist_validation import (
    build_entity_roster_recommendation,
    build_phase19b_deep_stress_metrics,
    canonicalise_phase19a_finalists,
    drawdown_quality_tier,
    save_phase19b_strategy_factory_finalist_validation,
    select_phase19b_paper_candidates,
)


def _finalist_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "universe_name": "btc_capped_growth",
                "candidate_id": "sf19_topk_momentum_252d_top3_btc10",
                "strategy_family": "top_k_momentum",
                "periods_tested": 2,
                "average_score": 0.74,
                "mean_CAGR": 15.9,
                "mean_CAGR_edge_vs_SPY": 2.1,
                "worst_max_drawdown": -24.6,
                "worst_drawdown_difference_vs_SPY": 4.1,
                "mean_Calmar": 0.67,
                "mean_turnover": 18.2,
                "mean_rolling_3y_beat_SPY_pct": 62.0,
                "BTC_average_weight": 0.067,
                "BTC_max_weight": 0.10,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "classification": "finalist_high_growth_high_caveat",
            },
            {
                "universe_name": "expanded_liquid_etf_with_btc",
                "candidate_id": "sf19_spy_qqq_60_40",
                "strategy_family": "fixed_allocation",
                "periods_tested": 2,
                "average_score": 0.67,
                "mean_CAGR": 15.6,
                "mean_CAGR_edge_vs_SPY": 2.0,
                "worst_max_drawdown": -53.8,
                "worst_drawdown_difference_vs_SPY": -1.0,
                "mean_Calmar": 0.51,
                "mean_turnover": 0.6,
                "mean_rolling_3y_beat_SPY_pct": 89.0,
                "BTC_average_weight": 0.0,
                "BTC_max_weight": 0.0,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "classification": "finalist_clean_growth",
            },
            {
                "universe_name": "btc_capped_growth",
                "candidate_id": "sf19_spy_qqq_60_40",
                "strategy_family": "fixed_allocation",
                "periods_tested": 2,
                "average_score": 0.62,
                "mean_CAGR": 15.5,
                "mean_CAGR_edge_vs_SPY": 1.8,
                "worst_max_drawdown": -53.8,
                "worst_drawdown_difference_vs_SPY": -1.0,
                "mean_Calmar": 0.50,
                "mean_turnover": 0.6,
                "mean_rolling_3y_beat_SPY_pct": 89.0,
                "BTC_average_weight": 0.0,
                "BTC_max_weight": 0.0,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "classification": "finalist_clean_growth",
            },
            {
                "universe_name": "core_us_growth",
                "candidate_id": "sf19_inverse_vol_63d_cap50",
                "strategy_family": "volatility_aware",
                "periods_tested": 2,
                "average_score": 0.56,
                "mean_CAGR": 13.8,
                "mean_CAGR_edge_vs_SPY": 0.7,
                "worst_max_drawdown": -54.7,
                "worst_drawdown_difference_vs_SPY": 2.0,
                "mean_Calmar": 0.58,
                "mean_turnover": 8.0,
                "mean_rolling_3y_beat_SPY_pct": 75.0,
                "BTC_average_weight": 0.0,
                "BTC_max_weight": 0.0,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "classification": "finalist_clean_growth",
            },
            {
                "universe_name": "btc_capped_growth",
                "candidate_id": "sf19_inverse_vol_63d_cap50_btc05",
                "strategy_family": "volatility_aware",
                "periods_tested": 2,
                "average_score": 0.80,
                "mean_CAGR": 16.5,
                "mean_CAGR_edge_vs_SPY": 2.7,
                "worst_max_drawdown": -28.0,
                "worst_drawdown_difference_vs_SPY": 3.0,
                "mean_Calmar": 0.67,
                "mean_turnover": 6.0,
                "mean_rolling_3y_beat_SPY_pct": 96.0,
                "BTC_average_weight": 0.04,
                "BTC_max_weight": 0.05,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "classification": "finalist_high_growth_high_caveat",
            },
        ]
    )


def _candidate_metrics(finalists: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in finalists.to_dict("records"):
        for period, cagr, score in [
            ("full_common", row["mean_CAGR"], row["average_score"]),
            ("post_2021", row["mean_CAGR"] - 1.0, row["average_score"] - 0.05),
        ]:
            rows.append(
                {
                    "universe_name": row["universe_name"],
                    "candidate_id": row["candidate_id"],
                    "strategy_family": row["strategy_family"],
                    "period_name": period,
                    "CAGR": cagr,
                    "max_drawdown": row["worst_max_drawdown"],
                    "Calmar": row["mean_Calmar"],
                    "turnover": row["mean_turnover"],
                    "CAGR_edge_vs_SPY": row["mean_CAGR_edge_vs_SPY"],
                    "max_drawdown_difference_vs_SPY": row[
                        "worst_drawdown_difference_vs_SPY"
                    ],
                    "score": score,
                    "missing_data_flag": False,
                }
            )
    return pd.DataFrame(rows)


def _write_phase19a_sources(source_dir: Path) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    finalists = _finalist_rows()
    finalists.to_csv(source_dir / "phase19a_finalist_shortlist.csv", index=False)
    _candidate_metrics(finalists).to_csv(source_dir / "phase19a_candidate_metrics.csv", index=False)
    finalists.to_csv(source_dir / "phase19a_leaderboard.csv", index=False)
    pd.DataFrame(
        [
            {
                "symbol": "QQQ",
                "appears_in_finalist_count": 4,
                "average_weight_among_finalists": 0.35,
            }
        ]
    ).to_csv(source_dir / "phase19a_entity_contribution_summary.csv", index=False)
    pd.DataFrame({"period_name": ["full_common"], "best_score": [0.74]}).to_csv(
        source_dir / "phase19a_period_metrics.csv",
        index=False,
    )
    pd.DataFrame(
        {
            "universe_name": ["btc_capped_growth"],
            "candidate_id": ["sf19_topk_momentum_252d_top3_btc10"],
            "flag_name": ["btc_high_caveat"],
            "flag_value": [True],
        }
    ).to_csv(source_dir / "phase19a_robustness_flags.csv", index=False)


def _config(tmp_path: Path) -> dict:
    return {
        "phase19b_strategy_factory_finalist_validation": {
            "enabled": True,
            "output_dir": str(tmp_path / "finalist_validation"),
            "dashboard_dir": str(tmp_path / "finalist_validation" / "dashboard"),
            "source_multiverse_dir": str(tmp_path / "multiverse"),
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "max_paper_candidates": 4,
            "include_benchmark_baseline": True,
            "stress_tests": {
                "btc_weekend_gap_penalty_enabled": True,
                "btc_gap_penalty_pct": 2.0,
            },
        }
    }


def test_missing_phase19a_source_files_fail_closed(tmp_path):
    config = _config(tmp_path)

    outputs = save_phase19b_strategy_factory_finalist_validation(
        config=config,
        reports_dir=tmp_path,
    )

    conclusion = pd.read_csv(outputs["conclusion"])
    assert conclusion.loc[0, "phase19b_decision"] == (
        "strategy_factory_finalist_validation_failed_closed"
    )


def test_canonical_grouping_recognises_duplicate_60_40_across_universes():
    canonical = canonicalise_phase19a_finalists(_finalist_rows())
    rows = canonical.loc[canonical["candidate_id"] == "sf19_spy_qqq_60_40"]

    assert rows["canonical_candidate_id"].nunique() == 1
    assert rows["equivalent_candidate_group"].nunique() == 1
    assert rows["canonical_representative"].sum() == 1


def test_btc_candidates_receive_caveat_and_report_only_penalty(tmp_path):
    finalists = canonicalise_phase19a_finalists(_finalist_rows())
    metrics = _candidate_metrics(_finalist_rows())

    stress = build_phase19b_deep_stress_metrics(
        finalists,
        metrics,
        reports_dir=tmp_path,
        section={"stress_tests": {"btc_weekend_gap_penalty_enabled": True}},
    )

    btc = stress.loc[stress["uses_btc"].astype(bool)].iloc[0]
    assert bool(btc["btc_gap_penalty_applied"])
    assert bool(btc["btc_gap_penalty_report_only"])


def test_drawdown_tiers_mark_severe_and_moderate_correctly():
    assert drawdown_quality_tier(-24.9) == "low_drawdown"
    assert drawdown_quality_tier(-31.0) == "moderate_drawdown"
    assert drawdown_quality_tier(-40.0) == "high_drawdown"
    assert drawdown_quality_tier(-53.8) == "severe_drawdown"


def test_paper_shortlist_length_and_safety_flags(tmp_path):
    finalists = canonicalise_phase19a_finalists(_finalist_rows())
    stress = build_phase19b_deep_stress_metrics(
        finalists,
        _candidate_metrics(_finalist_rows()),
        reports_dir=tmp_path,
        section={"stress_tests": {}},
    )

    selected = select_phase19b_paper_candidates(
        stress,
        max_paper_candidates=3,
        include_benchmark_baseline=True,
    )

    assert len(selected) <= 3
    assert not selected.empty
    assert not selected["live_trading_allowed"].astype(bool).any()
    assert not selected["real_money_allowed"].astype(bool).any()
    assert not selected["broker_api_integration_allowed"].astype(bool).any()
    assert not selected["promotion_allowed"].astype(bool).any()


def test_severe_drawdown_candidates_are_not_labelled_defensive(tmp_path):
    finalists = canonicalise_phase19a_finalists(_finalist_rows())
    stress = build_phase19b_deep_stress_metrics(
        finalists,
        _candidate_metrics(_finalist_rows()),
        reports_dir=tmp_path,
        section={"stress_tests": {}},
    )

    selected = select_phase19b_paper_candidates(
        stress,
        max_paper_candidates=4,
        include_benchmark_baseline=True,
    )

    assert "secondary_paper_candidate_defensive" not in set(
        selected["paper_candidate_role"]
    )
    clean = selected.loc[
        selected["canonical_candidate_id"] == "canonical_spy_qqq_60_40"
    ].iloc[0]
    assert clean["drawdown_quality_tier"] == "severe_drawdown"
    assert "not defensive" in clean["selection_limitations"]


def test_btc_inverse_vol_can_be_selected_high_caveat(tmp_path):
    finalists = canonicalise_phase19a_finalists(_finalist_rows())
    stress = build_phase19b_deep_stress_metrics(
        finalists,
        _candidate_metrics(_finalist_rows()),
        reports_dir=tmp_path,
        section={"stress_tests": {}},
    )

    selected = select_phase19b_paper_candidates(
        stress,
        max_paper_candidates=4,
        include_benchmark_baseline=True,
    )

    btc = selected.loc[selected["uses_btc"].astype(bool)].iloc[0]
    assert btc["paper_candidate_role"] == "high_growth_high_caveat_btc_candidate"
    assert "BTC weekend/gap risk" in btc["major_caveats"]


def test_entity_roster_recommends_qqq_and_excludes_gld_tlt_when_absent(tmp_path):
    finalists = canonicalise_phase19a_finalists(_finalist_rows())
    stress = build_phase19b_deep_stress_metrics(
        finalists,
        _candidate_metrics(_finalist_rows()),
        reports_dir=tmp_path,
        section={"stress_tests": {}},
    )
    selected = select_phase19b_paper_candidates(
        stress,
        max_paper_candidates=3,
        include_benchmark_baseline=True,
    )

    roster = build_entity_roster_recommendation(selected)

    assert bool(roster.loc[0, "include_qqq"])
    assert bool(roster.loc[0, "include_btc"])
    assert not bool(roster.loc[0, "include_gld"])
    assert not bool(roster.loc[0, "include_tlt"])


def test_phase19b_report_writer_outputs_dashboard_files(tmp_path):
    source_dir = tmp_path / "multiverse"
    _write_phase19a_sources(source_dir)
    config = _config(tmp_path)

    outputs = save_phase19b_strategy_factory_finalist_validation(
        config=config,
        reports_dir=tmp_path,
    )

    required = {
        "summary",
        "canonical_finalists",
        "deep_stress_metrics",
        "paper_candidate_shortlist",
        "recommended_paper_tracking_set",
        "entity_roster_recommendation",
        "gate_report",
        "conclusion",
        "dashboard_index",
        "top_finalists_score",
        "candidate_risk_return",
        "candidate_drawdown_comparison",
        "candidate_complexity_score",
    }
    assert required.issubset(outputs)
    for key in required:
        assert outputs[key].exists()

    shortlist = pd.read_csv(outputs["paper_candidate_shortlist"])
    tracking = pd.read_csv(outputs["recommended_paper_tracking_set"])
    caveats = pd.read_csv(outputs["dashboard_caveats"])
    assert len(shortlist) <= 4
    assert "paper_candidate_role" in shortlist.columns
    assert not tracking.empty
    assert "severe historical drawdown" in ";".join(caveats["major_caveats"].astype(str))
    assert "BTC weekend/gap risk" in ";".join(caveats["major_caveats"].astype(str))
