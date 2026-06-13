from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.interpretable_ranker_robustness import (
    RIDGE_MODEL,
    _prospective_holdout_protocol,
    _prediction_metrics,
    _sector_neutral_comparison,
    _target_horizon_decay,
    _topk_diagnostics,
    _rank_turnover,
    moving_block_bootstrap,
    permutation_test,
    prediction_grain_audit,
    save_phase23h_interpretable_ranker_robustness,
)


def _synthetic_predictions() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2024-01-05", periods=8, freq="W-FRI")
    securities = ["AAA", "BBB", "CCC", "DDD"]
    models = [RIDGE_MODEL, "baseline_63d_momentum_rank"]
    for date_index, date in enumerate(dates):
        actual_values = np.array([0.04, 0.02, -0.01, -0.03]) + date_index * 0.001
        for model in models:
            scores = (
                np.array([0.9, 0.5, 0.1, -0.2])
                if model == RIDGE_MODEL
                else np.array([0.1, 0.8, -0.1, -0.3])
            )
            ranks = pd.Series(scores).rank(ascending=False, method="first").astype(int)
            actual_ranks = pd.Series(actual_values).rank(
                ascending=False, method="first"
            ).astype(int)
            for security, score, rank, actual, actual_rank in zip(
                securities, scores, ranks, actual_values, actual_ranks, strict=False
            ):
                rows.append(
                    {
                        "decision_timestamp_utc": f"{date.date()}T22:00:00+00:00",
                        "signal_date": str(date.date()),
                        "panel_row_id": f"{date.date()}|U|SEC_{security}",
                        "universe_id": "U",
                        "permanent_security_id": f"SEC_{security}",
                        "ticker": security,
                        "model_version": model,
                        "training_cutoff": f"{date.date()}T22:00:00+00:00",
                        "predicted_20d_excess_return_or_ranking_score": score,
                        "predicted_rank": int(rank),
                        "actual_20d_excess_return": actual,
                        "actual_rank": int(actual_rank),
                        "positive_alpha_indicator": bool(actual > 0),
                        "prediction_is_out_of_sample": True,
                    }
                )
    return pd.DataFrame(rows)


def _synthetic_panel() -> pd.DataFrame:
    feature_values = {
        "momentum_21d": [0.4, 0.2, -0.1, -0.2],
        "momentum_63d": [0.5, 0.3, -0.2, -0.4],
        "momentum_252d_skip21d": [0.6, 0.1, -0.1, -0.3],
        "trend_distance_200d": [0.2, 0.1, -0.1, -0.2],
        "realized_volatility_21d": [0.1, 0.2, 0.3, 0.4],
        "volume_surprise_20d": [0.2, 0.0, -0.1, -0.2],
        "average_dollar_volume_20d": [2_000_000, 1_800_000, 1_600_000, 1_400_000],
        "beta_252d": [1.1, 1.0, 0.9, 0.8],
        "market_breadth_200d": [0.75, 0.75, 0.75, 0.75],
        "cross_sectional_dispersion_21d": [0.2, 0.2, 0.2, 0.2],
    }
    rows = []
    sectors = ["Technology", "Technology", "Industrials", "Industrials"]
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    for date in pd.date_range("2024-01-05", periods=8, freq="W-FRI"):
        for idx, ticker in enumerate(tickers):
            rows.append(
                {
                    "panel_row_id": f"{date.date()}|U|SEC_{ticker}",
                    "decision_timestamp_utc": f"{date.date()}T22:00:00+00:00",
                    "signal_date": str(date.date()),
                    "permanent_security_id": f"SEC_{ticker}",
                    "ticker": ticker,
                    "ticker_asof": ticker,
                    "sector_asof": sectors[idx],
                    "industry_asof": "Test",
                    **{name: values[idx] for name, values in feature_values.items()},
                }
            )
    return pd.DataFrame(rows)


def _synthetic_targets() -> pd.DataFrame:
    rows = []
    for date_index, date in enumerate(pd.date_range("2024-01-05", periods=8, freq="W-FRI")):
        values = np.array([0.04, 0.02, -0.01, -0.03]) + date_index * 0.001
        for ticker, value in zip(["AAA", "BBB", "CCC", "DDD"], values, strict=False):
            for horizon in [1, 5, 20, 63]:
                rows.append(
                    {
                        "panel_row_id": f"{date.date()}|U|SEC_{ticker}",
                        "permanent_security_id": f"SEC_{ticker}",
                        "signal_date": str(date.date()),
                        "target_name": f"forward_{horizon}d_excess_return_vs_universe",
                        "target_horizon_trading_days": horizon,
                        "target_value": value / np.sqrt(horizon),
                        "target_period_end_date": str((date + pd.Timedelta(days=horizon)).date()),
                        "target_available_timestamp_utc": (
                            date + pd.Timedelta(days=horizon + 1)
                        ).isoformat(),
                    }
                )
    return pd.DataFrame(rows)


def test_prediction_grain_reconciles_model_date_security_count():
    predictions = _synthetic_predictions()
    audit = prediction_grain_audit(predictions).iloc[0]

    assert audit["prediction_model_count"] == 2
    assert audit["unique_stock_date_observations"] == 32
    assert audit["total_model_prediction_rows"] == 64
    assert bool(audit["model_date_security_unique"])


def test_bootstrap_and_permutation_are_deterministic():
    predictions = _synthetic_predictions()
    date_metrics = predictions.groupby(["model_version", "decision_timestamp_utc"]).apply(
        lambda group: pd.Series(
            {
                "signal_date": group["signal_date"].iloc[0],
                "spearman_information_coefficient": group[
                    "predicted_20d_excess_return_or_ranking_score"
                ].rank().corr(group["actual_20d_excess_return"].rank()),
                "top_minus_bottom_rank_spread": (
                    group.sort_values("predicted_rank").head(2)[
                        "actual_20d_excess_return"
                    ].mean()
                    - group.sort_values("predicted_rank").tail(2)[
                        "actual_20d_excess_return"
                    ].mean()
                ),
                "security_count": len(group),
            }
        ),
        include_groups=False,
    ).reset_index()

    first_bootstrap = moving_block_bootstrap(
        date_metrics, seed=7, samples=25, block_length=2
    )
    second_bootstrap = moving_block_bootstrap(
        date_metrics, seed=7, samples=25, block_length=2
    )
    pd.testing.assert_frame_equal(first_bootstrap, second_bootstrap)

    first_permutation = permutation_test(
        predictions, seed=11, permutations=20, top_k=2
    )
    second_permutation = permutation_test(
        predictions, seed=11, permutations=20, top_k=2
    )
    pd.testing.assert_frame_equal(first_permutation, second_permutation)


def test_sector_horizon_false_positive_and_turnover_diagnostics():
    predictions_panel = _synthetic_predictions().merge(
        _synthetic_panel(),
        on=["panel_row_id", "decision_timestamp_utc", "signal_date", "permanent_security_id", "ticker"],
        how="left",
    )

    sector_neutral = _sector_neutral_comparison(predictions_panel, top_k=2)
    assert {
        "unconstrained_ranker",
        "sector_neutral_demeaned_prediction_scores",
    } == set(sector_neutral["diagnostic"])

    horizon = _target_horizon_decay(
        _synthetic_predictions(), _synthetic_targets(), top_k=2
    )
    assert {1, 5, 20, 63} == set(horizon["target_horizon_trading_days"])

    topk, false_cases = _topk_diagnostics(predictions_panel, top_values=[1, 3])
    assert {"top_1", "bottom_1", "top_3", "bottom_3"} == set(topk["selection_bucket"])
    assert "top_k_definition" in false_cases.columns

    turnover = _rank_turnover(_synthetic_predictions(), top_k=2)
    assert turnover["top_k_membership_turnover"].ge(0).all()
    assert turnover["spearman_rank_autocorrelation"].notna().all()


def test_prospective_holdout_protocol_keeps_safety_flags_false():
    protocol = _prospective_holdout_protocol(
        {
            "model_version": RIDGE_MODEL,
            "primary_target": "forward_20d_excess_return_vs_universe",
            "phase23g_config": {"ridge_alpha": 1.0},
            "minimum_future_observation_count": 52,
        }
    )

    assert "frozen_model_hash" in set(protocol["protocol_item"])
    assert not protocol["promotion_allowed"].any()
    assert protocol["research_pilot_only"].all()


def test_phase23h_save_writes_outputs_and_blocks_no_order_files(tmp_path: Path):
    reports_dir = tmp_path / "reports"
    phase23g_dir = reports_dir / "phase23g"
    phase23f_dir = reports_dir / "phase23f"
    phase23g_dir.mkdir(parents=True)
    phase23f_dir.mkdir(parents=True)

    predictions = _synthetic_predictions()
    predictions.to_csv(phase23g_dir / "phase23g_oos_predictions.csv", index=False)
    metric_rows = []
    for model, model_predictions in predictions.groupby("model_version"):
        metrics_dict = _prediction_metrics(model_predictions, top_k=2)
        metric_rows.append(
            {
                "model_version": model,
                "mean_ic": metrics_dict["mean_ic"],
                "median_ic": metrics_dict["median_ic"],
                "positive_ic_date_fraction": metrics_dict["positive_ic_fraction"],
                "top_minus_bottom_rank_spread": metrics_dict[
                    "top_minus_bottom_rank_spread"
                ],
                "prediction_coverage": metrics_dict["prediction_coverage"],
            }
        )
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(phase23g_dir / "phase23g_cross_sectional_metrics.csv", index=False)
    pd.DataFrame(
        [
            {
                "phase23g_decision": "phase23g_interpretable_ranker_completed_research_only",
                "mean_ic": metrics.loc[
                    metrics["model_version"].eq(RIDGE_MODEL), "mean_ic"
                ].iloc[0],
            }
        ]
    ).to_csv(phase23g_dir / "phase23g_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "test_signal_date": "2024-01-05",
                "purge_boundary_signal_date": "2023-10-01",
                "purge_window_trading_days": 63,
                "embargo_window_trading_days": 63,
            }
        ]
    ).to_csv(phase23g_dir / "phase23g_walk_forward_folds.csv", index=False)
    pd.DataFrame({"feature_name": ["momentum_21d"], "coefficient": [0.1]}).to_csv(
        phase23g_dir / "phase23g_feature_coefficients.csv", index=False
    )
    pd.DataFrame({"feature_name": ["momentum_21d"], "mean_coefficient": [0.1]}).to_csv(
        phase23g_dir / "phase23g_coefficient_stability.csv", index=False
    )
    _synthetic_panel().to_csv(phase23f_dir / "phase23f_pilot_feature_panel.csv", index=False)
    _synthetic_targets().to_csv(phase23f_dir / "phase23f_pilot_targets.csv", index=False)

    config = {
        "phase23h_interpretable_ranker_robustness": {
            "enabled": True,
            "output_dir": "reports/phase23h",
            "dashboard_status_path": "reports/dashboard/phase23h.csv",
            "source_phase23g_dir": "reports/phase23g",
            "source_phase23f_dir": "reports/phase23f",
            "bootstrap_samples": 25,
            "permutation_count": 20,
            "top_k": 2,
            "minimum_test_dates": 3,
            "minimum_security_count": 3,
            "phase23g_config": {
                "purge_window_trading_days": 63,
                "embargo_window_trading_days": 63,
            },
        }
    }
    outputs = save_phase23h_interpretable_ranker_robustness(
        config=config,
        reports_dir=reports_dir,
    )

    assert bool(outputs["summary"].iloc[0]["phase23g_integrity_passed"])
    assert not bool(outputs["summary"].iloc[0]["paper_trading_allowed"])
    assert not bool(outputs["summary"].iloc[0]["promotion_allowed"])
    output_dir = reports_dir / "phase23h"
    assert (output_dir / "phase23h_summary.csv").exists()
    assert (output_dir / "phase23h_prospective_holdout_protocol.csv").exists()
    assert not any("order" in path.name.lower() for path in output_dir.iterdir())
    assert not (reports_dir / "reports").exists()
