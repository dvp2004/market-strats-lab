from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.interpretable_stock_ranker import (
    NONCANONICAL_WARNING,
    run_walk_forward_ranker,
    save_phase23g_interpretable_stock_ranker,
)
from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
    save_phase23f_pilot_individual_equity_feature_calculation,
)


def _price_frame(seed: int, rows: int = 560) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=rows)
    t = np.arange(rows, dtype=float)
    drift = 0.00035 + seed * 0.00003
    cycle = 0.045 * np.sin(t / (14.0 + seed) + seed)
    slower_cycle = 0.035 * np.cos(t / (41.0 + seed * 2))
    close = 100.0 * np.exp(drift * t + cycle + slower_cycle)
    volume = 2_000_000.0 + seed * 100_000.0 + 50_000.0 * np.sin(t / 19.0)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "adj_close": close,
            "volume": volume,
        }
    )


def _manifest(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for index, ticker in enumerate(tickers, start=1):
        rows.append(
            {
                "universe_id": "SP500_PILOT_NONCANONICAL",
                "permanent_security_id": f"PILOT_SEC_{ticker}",
                "permanent_company_id": f"PILOT_COMP_{ticker}",
                "ticker": ticker,
                "sector": "Technology",
                "industry": "Software",
                "membership_start_date": "2022-01-03",
                "membership_end_date": "",
                "membership_known_timestamp_utc": "2022-01-03T00:00:00Z",
                "price_file": f"{ticker}.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
            }
        )
    return pd.DataFrame(rows)


def _phase23f_config() -> dict:
    return {
        "phase23f_pilot_individual_equity_feature_calculation": {
            "enabled": True,
            "output_dir": "reports/phase23f",
            "dashboard_status_path": "reports/dashboard/phase23f.csv",
            "input_dir": "data/individual_equity_pilot",
            "membership_manifest_path": (
                "data/individual_equity_pilot/pilot_membership_manifest.csv"
            ),
            "benchmark_path": "data/individual_equity_pilot/benchmark_SPY.csv",
            "pilot_start_date": "2023-01-03",
            "pilot_end_date": "2024-02-29",
            "decision_weekday": "FRIDAY",
            "decision_time_utc": "22:00:00",
            "market_data_available_time_utc": "21:05:00",
            "minimum_securities": 5,
            "minimum_price_rows": 320,
            "minimum_average_dollar_volume": 1_000_000.0,
            "feature_set_version": "phase23f_test_v1",
            "target_set_version": "phase23f_targets_test_v1",
        }
    }


def _phase23g_config() -> dict:
    return {
        "phase23g_interpretable_stock_ranker": {
            "enabled": True,
            "output_dir": "reports/phase23g",
            "dashboard_status_path": "reports/dashboard/phase23g.csv",
            "source_phase23f_dir": "reports/phase23f",
            "primary_target": "forward_20d_excess_return_vs_universe",
            "model_version": "phase23g_ridge_ranker_v1",
            "minimum_training_decision_dates": 6,
            "minimum_training_rows": 25,
            "minimum_test_dates": 3,
            "top_k": 2,
            "ridge_alpha": 1.0,
            "ridge_alpha_grid": [0.1, 1.0, 10.0],
            "purge_window_trading_days": 20,
            "embargo_window_trading_days": 20,
            "paper_only": True,
            "research_pilot_only": True,
            "allow_model_training": True,
            "allow_backtest": False,
            "allow_paper_orders": False,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        }
    }


def _write_phase23f_sources(tmp_path: Path) -> None:
    input_dir = tmp_path / "data" / "individual_equity_pilot"
    input_dir.mkdir(parents=True)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    _manifest(tickers).to_csv(input_dir / "pilot_membership_manifest.csv", index=False)
    for seed, ticker in enumerate(tickers, start=1):
        _price_frame(seed).to_csv(input_dir / f"{ticker}.csv", index=False)
    _price_frame(0).to_csv(input_dir / "benchmark_SPY.csv", index=False)
    outputs = save_phase23f_pilot_individual_equity_feature_calculation(
        config=_phase23f_config(),
        reports_dir=tmp_path / "reports",
    )
    assert bool(outputs["summary"].iloc[0]["pilot_panel_validation_passed"])


def test_phase23g_writes_oos_ranker_outputs_and_safety_flags(tmp_path: Path):
    _write_phase23f_sources(tmp_path)
    outputs = save_phase23g_interpretable_stock_ranker(
        config=_phase23g_config(),
        reports_dir=tmp_path / "reports",
    )

    summary = outputs["summary"].iloc[0]
    assert bool(summary["all_gates_passed"])
    assert bool(summary["research_pilot_only"])
    assert not bool(summary["promotion_allowed"])
    assert not bool(summary["live_trading_allowed"])
    assert not bool(summary["real_money_allowed"])
    assert not bool(summary["broker_api_integration_allowed"])

    predictions = outputs["oos_predictions"]
    assert not predictions.empty
    assert predictions["ticker"].astype(str).str.strip().ne("").all()
    assert predictions["permanent_security_id"].astype(str).str.strip().ne("").all()
    assert predictions["prediction_is_out_of_sample"].all()
    assert predictions["noncanonical_pilot_warning"].eq(NONCANONICAL_WARNING).all()

    output_dir = tmp_path / "reports" / "phase23g"
    expected_files = {
        "phase23g_summary.csv",
        "phase23g_gate_report.csv",
        "phase23g_model_registry.csv",
        "phase23g_walk_forward_folds.csv",
        "phase23g_oos_predictions.csv",
        "phase23g_cross_sectional_metrics.csv",
        "phase23g_information_coefficient_by_date.csv",
        "phase23g_rank_spread_diagnostics.csv",
        "phase23g_benchmark_comparison.csv",
        "phase23g_feature_coefficients.csv",
        "phase23g_coefficient_stability.csv",
        "phase23g_feature_missingness.csv",
        "phase23g_prediction_coverage.csv",
        "phase23g_integrity_audit.csv",
        "phase23g_conclusion.csv",
        "phase23g_interpretable_stock_ranker.md",
    }
    assert expected_files.issubset({path.name for path in output_dir.iterdir()})
    assert not any("order" in path.name.lower() for path in output_dir.iterdir())
    assert not (tmp_path / "reports" / "reports").exists()


def test_phase23g_walk_forward_folds_are_chronological_and_purged(tmp_path: Path):
    _write_phase23f_sources(tmp_path)
    outputs = save_phase23g_interpretable_stock_ranker(
        config=_phase23g_config(),
        reports_dir=tmp_path / "reports",
    )

    folds = outputs["walk_forward_folds"]
    assert not folds.empty
    assert (
        pd.to_datetime(folds["purge_boundary_signal_date"])
        < pd.to_datetime(folds["test_signal_date"])
    ).all()
    assert folds["training_rows"].min() >= 25
    assert folds["training_decision_dates"].min() >= 6
    assert folds["sufficient_training_history"].all()


def test_phase23g_coefficients_and_benchmarks_are_written(tmp_path: Path):
    _write_phase23f_sources(tmp_path)
    outputs = save_phase23g_interpretable_stock_ranker(
        config=_phase23g_config(),
        reports_dir=tmp_path / "reports",
    )

    coefficients = outputs["feature_coefficients"]
    assert "__intercept__" in set(coefficients["feature_name"])
    assert set(CORE_FEATURE_COLUMNS).issubset(set(coefficients["feature_name"]))
    registry = outputs["model_registry"]
    assert "phase23g_ridge_ranker_v1" in set(registry["model_version"])
    assert "baseline_63d_momentum_rank" in set(registry["model_version"])
    benchmark = outputs["benchmark_comparison"]
    assert set(registry["model_version"]).issubset(set(benchmark["model_version"]))


def test_phase23g_deterministic_rerun_consistency(tmp_path: Path):
    _write_phase23f_sources(tmp_path)
    first = save_phase23g_interpretable_stock_ranker(
        config=_phase23g_config(),
        reports_dir=tmp_path / "reports",
    )
    second = save_phase23g_interpretable_stock_ranker(
        config=_phase23g_config(),
        reports_dir=tmp_path / "reports",
    )

    columns = [
        "decision_timestamp_utc",
        "panel_row_id",
        "model_version",
        "predicted_20d_excess_return_or_ranking_score",
        "predicted_rank",
        "actual_20d_excess_return",
        "actual_rank",
    ]
    pd.testing.assert_frame_equal(
        first["oos_predictions"][columns].reset_index(drop=True),
        second["oos_predictions"][columns].reset_index(drop=True),
    )


def test_phase23g_blocks_phase23f_panel_without_ticker(tmp_path: Path):
    _write_phase23f_sources(tmp_path)
    panel_path = tmp_path / "reports" / "phase23f" / "phase23f_pilot_feature_panel.csv"
    panel = pd.read_csv(panel_path).drop(columns=["ticker"])
    panel.to_csv(panel_path, index=False)

    outputs = save_phase23g_interpretable_stock_ranker(
        config=_phase23g_config(),
        reports_dir=tmp_path / "reports",
    )
    summary = outputs["summary"].iloc[0]
    assert summary["phase23g_decision"] == "phase23g_blocked_phase23f_integrity_failure"
    assert "missing required ticker column" in summary["blocking_detail"]


def test_walk_forward_ranker_uses_only_phase23f_pilot_features(tmp_path: Path):
    _write_phase23f_sources(tmp_path)
    panel = pd.read_csv(tmp_path / "reports" / "phase23f" / "phase23f_pilot_feature_panel.csv")
    targets = pd.read_csv(tmp_path / "reports" / "phase23f" / "phase23f_pilot_targets.csv")
    outputs = run_walk_forward_ranker(panel, targets, _phase23g_config()["phase23g_interpretable_stock_ranker"])

    coefficients = outputs["coefficients"]
    used_features = set(coefficients["feature_name"]) - {"__intercept__"}
    assert used_features == set(CORE_FEATURE_COLUMNS)
    assert not {"fundamental", "sentiment", "macro"}.intersection(
        ";".join(sorted(used_features)).lower().split(";")
    )
