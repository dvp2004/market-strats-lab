from pathlib import Path

import pandas as pd

from market_strats.analysis.strategy_factory_watchlist_dashboard import (
    save_phase17c_strategy_factory_watchlist_dashboard,
)


WATCHLIST = [
    "sf_spy_qqq_60_40_monthly_rebalanced",
    "sf_spy_core_phase6_overlay_satellite_qqq",
    "sf_spy_qqq_btc_capped_offensive",
]


def _write_source_files(tmp_path: Path) -> dict[str, Path]:
    source_dir = tmp_path / "reports" / "strategy_factory"
    source_dir.mkdir(parents=True, exist_ok=True)

    shortlist = pd.DataFrame(
        [
            {
                "strategy": "sf_spy_buy_hold",
                "phase17b_classification": "rejected",
                "rolling_3y_candidate_beats_spy_pct": 0.0,
                "btc_cap_dependency_flag": False,
                "btc_weekend_gap_diagnostic_available": True,
                "promotion_allowed": False,
                "paper_watchlist_only": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            },
            *[
                {
                    "strategy": strategy,
                    "phase17b_classification": "paper_watchlist_growth",
                    "rolling_3y_candidate_beats_spy_pct": 93.0,
                    "btc_cap_dependency_flag": strategy
                    == "sf_spy_qqq_btc_capped_offensive",
                    "btc_weekend_gap_diagnostic_available": True,
                    "promotion_allowed": False,
                    "paper_watchlist_only": True,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
                for strategy in WATCHLIST
            ],
            {
                "strategy": "sf_spy_qqq_tactical_momentum",
                "phase17b_classification": "rejected",
                "rolling_3y_candidate_beats_spy_pct": 52.0,
                "btc_cap_dependency_flag": False,
                "btc_weekend_gap_diagnostic_available": True,
                "promotion_allowed": False,
                "paper_watchlist_only": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            },
        ]
    )
    metrics_rows = []
    for strategy in ["sf_spy_buy_hold", *WATCHLIST, "sf_spy_qqq_tactical_momentum"]:
        for scenario, cagr in [
            ("no_extra_cost", 13.66 if strategy == "sf_spy_buy_hold" else 16.0),
            ("low", 13.66 if strategy == "sf_spy_buy_hold" else 15.9),
            ("realistic_stress", 13.66 if strategy == "sf_spy_buy_hold" else 15.8),
        ]:
            metrics_rows.append(
                {
                    "strategy": strategy,
                    "friction_scenario": scenario,
                    "cagr_pct": cagr,
                    "max_drawdown_pct": -33.72
                    if strategy == "sf_spy_buy_hold"
                    else -31.4,
                    "calmar": 0.405 if strategy == "sf_spy_buy_hold" else 0.505,
                    "candidate_minus_spy_cagr_pct": 0.0
                    if strategy == "sf_spy_buy_hold"
                    else cagr - 13.66,
                    "candidate_max_drawdown_advantage_vs_spy_pct_points": 0.0
                    if strategy == "sf_spy_buy_hold"
                    else 2.32,
                }
            )
    rolling = pd.DataFrame(
        [
            {
                "strategy": strategy,
                "rolling_3y_candidate_beats_spy_pct": 93.0
                if strategy in WATCHLIST
                else 52.0,
                "worst_3y_active_cagr": -2.0 if strategy in WATCHLIST else -7.0,
                "latest_3y_active_cagr": 2.0 if strategy in WATCHLIST else -6.0,
            }
            for strategy in ["sf_spy_buy_hold", *WATCHLIST, "sf_spy_qqq_tactical_momentum"]
        ]
    )
    btc_gap = pd.DataFrame(
        [
            {
                "diagnostic_available": True,
                "btc_source_path": "data/fresh/processed/BTC-USD.parquet",
                "btc_rows": 1000,
                "btc_min_date": "2014-09-17",
                "btc_max_date": "2026-06-08",
                "weekend_gap_count": 100,
                "average_friday_to_monday_return": 0.5,
                "median_friday_to_monday_return": 0.2,
                "worst_friday_to_monday_return": -12.0,
                "best_friday_to_monday_return": 15.0,
                "gaps_worse_than_minus_5_pct": 10,
                "gaps_worse_than_minus_10_pct": 2,
            }
        ]
    )

    paths = {
        "shortlist": source_dir / "phase17b_shortlist_decision.csv",
        "metrics": source_dir / "phase17b_friction_metrics.csv",
        "rolling": source_dir / "phase17b_rolling_relative_summary.csv",
        "btc_gap": source_dir / "phase17b_btc_weekend_gap_diagnostic.csv",
    }
    shortlist.to_csv(paths["shortlist"], index=False)
    pd.DataFrame(metrics_rows).to_csv(paths["metrics"], index=False)
    rolling.to_csv(paths["rolling"], index=False)
    btc_gap.to_csv(paths["btc_gap"], index=False)
    return paths


def _config(tmp_path: Path, paths: dict[str, Path] | None = None) -> dict:
    output_dir = tmp_path / "reports" / "strategy_factory" / "watchlist"
    paths = paths or {}
    return {
        "phase17c_strategy_factory_watchlist_dashboard": {
            "enabled": True,
            "output_dir": str(output_dir),
            "dashboard_dir": str(output_dir / "dashboard"),
            "source_shortlist_file": str(paths.get("shortlist", tmp_path / "missing_short.csv")),
            "source_metrics_file": str(paths.get("metrics", tmp_path / "missing_metrics.csv")),
            "source_rolling_file": str(paths.get("rolling", tmp_path / "missing_rolling.csv")),
            "source_btc_gap_file": str(paths.get("btc_gap", tmp_path / "missing_btc.csv")),
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
        }
    }


def test_phase17c_watchlist_includes_only_paper_watchlist_candidates(tmp_path):
    paths = _write_source_files(tmp_path)
    outputs = save_phase17c_strategy_factory_watchlist_dashboard(
        config=_config(tmp_path, paths),
        reports_dir=tmp_path / "reports",
    )

    candidates = outputs["candidates"]
    assert set(candidates["candidate_id"]) == set(WATCHLIST)
    assert "sf_spy_qqq_tactical_momentum" not in set(candidates["candidate_id"])
    assert "sf_spy_buy_hold" not in set(candidates["candidate_id"])


def test_phase17c_watchlist_flags_and_btc_caveats(tmp_path):
    paths = _write_source_files(tmp_path)
    outputs = save_phase17c_strategy_factory_watchlist_dashboard(
        config=_config(tmp_path, paths),
        reports_dir=tmp_path / "reports",
    )

    candidates = outputs["candidates"]
    caveats = outputs["caveats"]
    assert not bool(candidates["promotion_allowed"].any())
    assert bool(candidates["paper_watchlist_only"].all())
    assert not bool(candidates["live_trading_allowed"].any())
    assert not bool(candidates["real_money_allowed"].any())
    assert not bool(candidates["broker_api_integration_allowed"].any())
    assert "btc_cap_dependency_flag" in candidates.columns
    assert "btc_weekend_gap_diagnostic_available" in caveats.columns
    btc = candidates.loc[
        candidates["candidate_id"] == "sf_spy_qqq_btc_capped_offensive"
    ].iloc[0]
    assert bool(btc["btc_cap_dependency_flag"])


def test_phase17c_missing_source_files_fail_closed(tmp_path):
    outputs = save_phase17c_strategy_factory_watchlist_dashboard(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )

    assert outputs["candidates"].empty
    assert outputs["conclusion"].iloc[0]["decision"] == (
        "strategy_factory_watchlist_dashboard_failed_closed"
    )
    assert "failed" in set(outputs["gate_report"]["gate_status"])


def test_phase17c_dashboard_index_and_charts_are_written(tmp_path):
    paths = _write_source_files(tmp_path)
    save_phase17c_strategy_factory_watchlist_dashboard(
        config=_config(tmp_path, paths),
        reports_dir=tmp_path / "reports",
    )

    dashboard_dir = (
        tmp_path / "reports" / "strategy_factory" / "watchlist" / "dashboard"
    )
    for path in [
        dashboard_dir / "index.md",
        dashboard_dir / "watchlist_overview.csv",
        dashboard_dir / "watchlist_roles.csv",
        dashboard_dir / "watchlist_risk_flags.csv",
        dashboard_dir / "watchlist_metric_snapshot.csv",
        dashboard_dir / "watchlist_rolling_snapshot.csv",
        dashboard_dir / "watchlist_stop_conditions.csv",
        dashboard_dir / "watchlist_metric_snapshot.png",
        dashboard_dir / "watchlist_rolling_3y_beat_rate.png",
    ]:
        assert path.exists()
