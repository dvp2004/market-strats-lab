from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.historical_regime_stress_lab import (
    PHASE6_BASELINE_DAILY_FILE,
    PHASE6_BASELINE_ID,
    build_regime_robustness_score_components,
    build_regime_robustness_scores,
    calculate_regime_metric_row,
    classify_master_strategy_candidates,
    parse_regime_windows,
    save_phase21a_historical_regime_stress_lab,
)


def _price_frame(
    symbol: str,
    *,
    start: str,
    end: str = "2026-06-08",
    daily_return: float = 0.0003,
) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    seasonal = np.sin(np.arange(len(dates)) / 23.0) * 0.001
    if symbol == "QQQ":
        seasonal += 0.0002
    if symbol == "BTC-USD":
        seasonal = np.sin(np.arange(len(dates)) / 13.0) * 0.006 + 0.0007
    prices = 100.0 * np.cumprod(1.0 + daily_return + seasonal)
    return pd.DataFrame({"date": dates, "adj_close": prices})


def _price_data() -> dict[str, pd.DataFrame]:
    return {
        "SPY": _price_frame("SPY", start="1993-01-29", daily_return=0.00025),
        "QQQ": _price_frame("QQQ", start="1999-03-10", daily_return=0.00035),
        "GLD": _price_frame("GLD", start="2004-11-18", daily_return=0.00012),
        "TLT": _price_frame("TLT", start="2002-07-30", daily_return=0.00008),
        "BTC-USD": _price_frame("BTC-USD", start="2014-09-17", daily_return=0.0008),
    }


def _write_phase6_daily_curve(path: Path) -> None:
    dates = pd.bdate_range("2006-04-28", "2026-06-08")
    returns = np.sin(np.arange(len(dates)) / 31.0) * 0.001 + 0.0002
    returns[0] = 0.0
    equity = 10000.0 * np.cumprod(1.0 + returns)
    frame = pd.DataFrame(
        {
            "source_system_id": PHASE6_BASELINE_ID,
            "decision_date": dates,
            "strategy_return": returns,
            "candidate_equity": equity,
            "exposure": 1.0,
            "turnover": 0.0,
        }
    )
    frame.to_csv(path, index=False)


def _config(tmp_path: Path) -> dict:
    output_dir = tmp_path / "regime_stress"
    finalist_dir = tmp_path / "finalist_validation"
    return {
        "phase19a_strategy_factory_multiverse": {
            "universes": {
                "core_us_growth": {
                    "symbols": ["SPY", "QQQ", "CASH"],
                    "allow_btc": False,
                },
                "defensive_multi_asset": {
                    "symbols": ["SPY", "QQQ", "GLD", "TLT", "CASH"],
                    "allow_btc": False,
                },
                "btc_capped_growth": {
                    "symbols": ["SPY", "QQQ", "BTC-USD", "CASH"],
                    "allow_btc": True,
                    "btc_caps": [0.05, 0.10],
                },
            }
        },
        "phase21a_historical_regime_stress_lab": {
            "enabled": True,
            "output_dir": str(output_dir),
            "dashboard_dir": str(output_dir / "dashboard"),
            "source_finalist_validation_dir": str(finalist_dir),
            "phase6_baseline_daily_path": str(tmp_path / PHASE6_BASELINE_DAILY_FILE),
            "initial_capital": 10000,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "regime_windows": {
                "dot_com_crash": {
                    "start": "2000-03-10",
                    "end": "2002-10-09",
                    "description": "Dot-com crash",
                },
                "post_2022_recovery": {
                    "start": "2022-10-15",
                    "end": "2026-05-01",
                    "description": "Post-2022 recovery",
                },
                "full_canonical": {
                    "start": "2006-04-28",
                    "end": "2026-05-01",
                    "description": "Canonical window",
                },
            },
            "candidate_groups": {
                "include_phase19a_finalists": False,
                "include_spy_benchmark": True,
                "include_phase6_loose_relief_baseline": True,
                "include_spy_qqq_static_variants": True,
                "include_btc_candidates_where_available": True,
                "include_gls_tlt_reference_where_available": True,
            },
            "min_regime_trading_days": 20,
        },
    }


def test_regime_windows_are_loaded():
    windows = parse_regime_windows(
        {
            "regime_windows": {
                "test": {
                    "start": "2020-01-01",
                    "end": "2020-03-01",
                    "description": "Test regime",
                }
            }
        }
    )

    assert windows.iloc[0]["regime_name"] == "test"
    assert windows.iloc[0]["start"] == "2020-01-01"
    assert not bool(windows.iloc[0]["is_full_canonical_context"])


def test_covid_crash_is_flagged_short_window_directional_only():
    windows = parse_regime_windows({})
    covid = windows.loc[windows["regime_name"] == "covid_crash"].iloc[0]

    assert bool(covid["short_window_directional_only"])
    assert not bool(covid["included_in_primary_calmar_score"])


def test_candidate_unavailable_before_asset_inception_is_reported(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    unavailable = pd.read_csv(outputs["unavailable_candidate_regimes"])
    btc_unavailable = unavailable.loc[
        unavailable["canonical_candidate_id"]
        == "canonical_inverse_vol_63d_btc_usd_qqq_spy"
    ]

    assert "asset_inception_after_regime_start:BTC-USD=2014-09-17" in ";".join(
        btc_unavailable["availability_reason"].astype(str)
    )


def test_btc_candidate_unavailable_in_dot_com_regime(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    unavailable = pd.read_csv(outputs["unavailable_candidate_regimes"])

    dotcom = unavailable.loc[unavailable["regime_name"] == "dot_com_crash"]
    assert not dotcom.empty
    assert dotcom["availability_reason"].astype(str).str.contains("BTC-USD").any()


def test_spy_benchmark_available_across_canonical_windows(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    metrics = pd.read_csv(outputs["regime_metrics"])
    spy = metrics.loc[metrics["canonical_candidate_id"] == "canonical_spy_buy_hold"]

    assert spy["regime_available"].map(bool).all()
    assert set(spy["regime_name"]) == {
        "dot_com_crash",
        "post_2022_recovery",
        "full_canonical",
    }


def test_phase6_loose_relief_baseline_is_included_when_daily_curve_exists(tmp_path):
    _write_phase6_daily_curve(tmp_path / PHASE6_BASELINE_DAILY_FILE)
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    metrics = pd.read_csv(outputs["regime_metrics"])
    phase6 = metrics.loc[metrics["canonical_candidate_id"] == PHASE6_BASELINE_ID]

    assert not phase6.empty
    assert phase6["equity_curve_source"].astype(str).str.contains(PHASE6_BASELINE_DAILY_FILE).any()
    assert phase6.loc[phase6["regime_available"].map(bool), "uses_aggregate_metrics_only"].eq(False).all()


def test_phase6_candidate_fails_closed_if_daily_curve_missing(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    unavailable = pd.read_csv(outputs["unavailable_candidate_regimes"])
    phase6 = unavailable.loc[unavailable["canonical_candidate_id"] == PHASE6_BASELINE_ID]

    assert not phase6.empty
    assert phase6.iloc[0]["regime_metric_status"] == "equity_curve_missing"
    assert not bool(phase6.iloc[0]["uses_aggregate_metrics_only"])


def test_metrics_compute_total_return_and_max_drawdown_from_toy_curve():
    candidate = {
        "canonical_candidate_id": "toy",
        "candidate_id": "toy",
        "candidate_role": "toy",
        "candidate_family": "toy",
        "asset_roster": "SPY",
        "assets_required": ["SPY"],
        "price_data": {
            "SPY": pd.DataFrame(
                {
                    "date": pd.bdate_range("2020-01-01", periods=5),
                    "adj_close": [100, 105, 90, 95, 110],
                }
            )
        },
        "result": pd.DataFrame(
            {
                "date": pd.bdate_range("2020-01-01", periods=5),
                "equity": [10000, 11000, 9000, 10000, 12000],
                "strategy_return": [0.0, 0.10, -0.181818, 0.111111, 0.20],
                "position": [1.0] * 5,
                "cash_position": [0.0] * 5,
                "turnover": [1.0, 0.0, 0.0, 0.0, 0.0],
            }
        ),
    }
    regime = {
        "regime_name": "toy",
        "start": "2020-01-01",
        "end": "2020-01-07",
        "description": "toy",
    }

    row, unavailable = calculate_regime_metric_row(
        candidate=candidate,
        regime=regime,
        spy_result=candidate["result"],
        initial_capital=10000,
        min_regime_trading_days=2,
    )

    assert unavailable is None
    assert row["total_return_pct"] == 20.0
    assert row["max_drawdown_pct"] < 0
    assert row["regime_metric_status"] == "computed"
    assert not row["uses_aggregate_metrics_only"]
    assert row["equity_curve_daily_verified"]


def test_relative_to_spy_metrics_compute_correctly(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    metrics = pd.read_csv(outputs["regime_metrics"])
    row = metrics.loc[
        (metrics["canonical_candidate_id"] == "canonical_spy_qqq_60_40")
        & (metrics["regime_name"] == "post_2022_recovery")
    ].iloc[0]

    assert "excess_total_return_vs_spy_pct" in metrics.columns
    assert isinstance(bool(row["beat_spy_in_regime"]), bool)


def test_robustness_score_penalizes_unavailable_regimes_and_high_drawdown():
    summary = pd.DataFrame(
        [
            {
                "canonical_candidate_id": "broad",
                "uses_btc": False,
                "regimes_available": 5,
                "regimes_unavailable": 0,
                "positive_return_regimes": 4,
                "beat_spy_regimes": 3,
                "worst_max_drawdown_pct": -20.0,
                "mean_excess_total_return_vs_spy_pct": 5.0,
            },
            {
                "canonical_candidate_id": "fragile",
                "uses_btc": True,
                "regimes_available": 2,
                "regimes_unavailable": 3,
                "positive_return_regimes": 1,
                "beat_spy_regimes": 1,
                "worst_max_drawdown_pct": -60.0,
                "mean_excess_total_return_vs_spy_pct": 0.0,
            },
        ]
    )

    scored = build_regime_robustness_scores(summary)

    assert scored.iloc[0]["canonical_candidate_id"] == "broad"
    assert scored.iloc[0]["regime_robustness_score"] > scored.iloc[1][
        "regime_robustness_score"
    ]


def test_score_components_exclude_full_canonical_from_primary_score(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    components = pd.read_csv(outputs["regime_robustness_score_components"])
    spy = components.loc[components["canonical_candidate_id"] == "canonical_spy_buy_hold"].iloc[0]

    assert spy["available_subregime_count"] == 2
    assert "full_canonical_context_score" in components.columns


def test_score_components_file_is_written(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )

    assert outputs["regime_robustness_score_components"].exists()
    components = pd.read_csv(outputs["regime_robustness_score_components"])
    assert "hard_gate_penalty_component" in components.columns
    assert "classification_after_hard_gates" in components.columns


def test_master_classification_uses_provisional_language_and_does_not_promote():
    scores = pd.DataFrame(
        [
            {
                "canonical_candidate_id": "candidate",
                "uses_btc": False,
                "regime_robustness_score": 75.0,
                "regimes_available": 6,
                "worst_max_drawdown_pct": -25.0,
                "beat_spy_regimes": 4,
            }
        ]
    )

    classified = classify_master_strategy_candidates(scores)

    assert (
        classified.iloc[0]["master_strategy_classification"]
        == "provisional_core_candidate_for_further_research"
    )
    assert not bool(classified.iloc[0]["promotion_allowed"])
    assert not bool(classified.iloc[0]["final_model_promoted"])


def test_severe_drawdown_candidate_cannot_be_provisional_core():
    scores = pd.DataFrame(
        [
            {
                "canonical_candidate_id": "candidate",
                "uses_btc": False,
                "regime_robustness_score": 80.0,
                "regimes_available": 8,
                "worst_max_drawdown_pct": -54.0,
                "beat_spy_regimes": 6,
            }
        ]
    )

    classified = classify_master_strategy_candidates(scores)

    assert classified.iloc[0]["master_strategy_classification"] == "research_only"


def test_btc_candidate_is_high_caveat_not_preinception_penalized_to_rejected(tmp_path):
    config = _config(tmp_path)
    config["phase21a_historical_regime_stress_lab"]["regime_windows"]["covid_rebound"] = {
        "start": "2020-03-24",
        "end": "2021-12-31",
        "description": "COVID rebound",
    }
    outputs = save_phase21a_historical_regime_stress_lab(
        config=config,
        reports_dir=tmp_path,
        price_data=_price_data(),
    )
    master = pd.read_csv(outputs["master_strategy_candidates"])
    btc = master.loc[
        master["canonical_candidate_id"] == "canonical_inverse_vol_63d_btc_usd_qqq_spy"
    ].iloc[0]

    assert (
        btc["master_strategy_classification"]
        == "provisional_high_caveat_candidate_for_further_research"
    )
    assert "btc_inception_limited" in str(btc["classification_blocking_reasons"])


def test_hard_gate_blocking_reasons_are_written_for_severe_drawdown():
    metrics = pd.DataFrame(
        [
            {
                "canonical_candidate_id": "fragile",
                "candidate_role": "test",
                "asset_roster": "SPY,QQQ",
                "regime_name": "global_financial_crisis",
                "regime_available": True,
                "included_in_primary_subregime_score": True,
                "included_in_primary_calmar_score": True,
                "is_full_canonical_context": False,
                "is_crash_regime": True,
                "short_window_directional_only": False,
                "beat_spy_in_regime": True,
                "total_return_pct": -10.0,
                "excess_total_return_vs_spy_pct": 1.0,
                "drawdown_improvement_vs_spy_pct": 1.0,
                "max_drawdown_pct": -55.0,
                "calmar": -0.2,
            }
        ]
    )

    components = build_regime_robustness_score_components(metrics)

    assert "severe_drawdown_worse_than_minus_50pct" in components.iloc[0][
        "classification_blocking_reasons"
    ]


def test_phase21a_outputs_files_and_safety_flags_false(tmp_path):
    outputs = save_phase21a_historical_regime_stress_lab(
        config=_config(tmp_path),
        reports_dir=tmp_path,
        price_data=_price_data(),
    )

    required = {
        "summary",
        "gate_report",
        "conclusion",
        "regime_metrics",
        "candidate_regime_summary",
        "regime_robustness_scores",
        "regime_robustness_score_components",
        "unavailable_candidate_regimes",
        "master_strategy_candidates",
        "dashboard_index",
    }
    assert required.issubset(outputs)
    for key in required:
        assert outputs[key].exists()
    conclusion = pd.read_csv(outputs["conclusion"]).iloc[0]
    assert not bool(conclusion["live_trading_allowed"])
    assert not bool(conclusion["real_money_allowed"])
    assert not bool(conclusion["broker_api_integration_allowed"])

    dashboard_text = outputs["dashboard_index"].read_text(encoding="utf-8")
    assert "No candidate is promoted" in dashboard_text
    assert "full canonical window is context" in dashboard_text.lower()
    assert "Phase6 loose_relief" in dashboard_text
