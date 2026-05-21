import pandas as pd

from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    build_phase9a_analysis_frame,
    build_phase9a_indicator_frame,
    build_phase9a_regime_frame,
)
from market_strats.analysis.technical_regime_cluster_stability_audit import (
    build_phase9b_cluster_episode_metrics,
    build_phase9b_conclusion,
    build_phase9b_episode_frame,
    build_phase9b_gate_report,
    build_phase9b_helpful_stability_report,
    build_phase9b_instability_report,
    build_phase9b_stability_summary,
    build_phase9b_summary,
    save_phase9b_technical_regime_cluster_stability_audit,
)


def _price_frame(start: str = "2020-01-01", periods: int = 520) -> pd.DataFrame:
    prices = [100.0]
    for index in range(1, periods):
        drift = 0.0005 if index % 80 < 50 else -0.0002
        prices.append(prices[-1] * (1.0 + drift))

    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=periods, freq="B"),
            "adj_close": prices,
            "close": prices,
        }
    )


def _strategy_frame(start: str, periods: int, daily_return: float) -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq="B")
    returns = [daily_return if index % 90 < 60 else -daily_return for index in range(periods)]

    return pd.DataFrame(
        {
            "date": dates,
            "strategy_return": returns,
            "turnover": [0.0] * periods,
            "equity": [10000.0] * periods,
        }
    )


def _phase9a_config() -> dict:
    return {
        "ticker": "SPY",
        "indicators": {
            "sma_short_days": 20,
            "sma_long_days": 50,
            "rsi_days": 14,
            "volatility_days": 21,
            "short_momentum_days": 21,
            "medium_momentum_days": 63,
            "long_momentum_days": 126,
            "drawdown_near_high_threshold": -0.05,
            "drawdown_correction_threshold": -0.10,
            "drawdown_bear_threshold": -0.20,
            "trend_distance_near_threshold": 0.03,
            "trend_distance_extended_threshold": 0.10,
        },
    }


def _phase9b_config() -> dict:
    return {
        "ticker": "SPY",
        "episode_definitions": {
            "episode_1": {"start_date": "2020-01-01", "end_date": "2020-09-30"},
            "episode_2": {"start_date": "2020-10-01", "end_date": "2021-06-30"},
            "episode_3": {"start_date": "2021-07-01", "end_date": "2022-03-31"},
            "episode_4": {"start_date": "2022-04-01", "end_date": "2022-12-31"},
        },
        "regime_columns": [
            "trend_state",
            "drawdown_bucket",
            "trend_distance_bucket",
            "rsi_bucket",
            "volatility_bucket",
            "long_momentum_state",
            "technical_risk_state",
        ],
        "gates": {
            "min_full_period_cluster_rows": 20,
            "min_episode_cluster_rows": 5,
            "min_episode_coverage_count": 2,
            "min_stability_rows": 4,
            "min_direction_consistency_rate": 0.50,
            "require_instability_report": True,
            "require_no_strategy_promotion": True,
            "max_allowed_diagnostic_role": "Diagnostic only",
        },
    }


def _analysis_frame() -> pd.DataFrame:
    periods = 520
    prices = _price_frame(periods=periods)
    candidate = _strategy_frame("2020-01-01", periods, 0.0005)
    buy_hold = _strategy_frame("2020-01-01", periods, 0.0007)
    spy_12m = _strategy_frame("2020-01-01", periods, 0.0003)

    indicators = build_phase9a_indicator_frame(prices, _phase9a_config())
    regimes = build_phase9a_regime_frame(indicators, _phase9a_config())

    return build_phase9a_analysis_frame(
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        regime_frame=regimes,
    )


def test_phase9b_episode_and_cluster_metrics_are_created():
    analysis = _analysis_frame()
    phase_config = _phase9b_config()

    episode_frame = build_phase9b_episode_frame(analysis, phase_config)
    cluster_metrics = build_phase9b_cluster_episode_metrics(
        analysis,
        episode_frame,
        phase_config,
    )

    assert not episode_frame.empty
    assert not cluster_metrics.empty
    assert "episode" in cluster_metrics.columns
    assert "direction_vs_buy_hold" in cluster_metrics.columns


def test_phase9b_stability_reports_and_gate_report_are_created():
    analysis = _analysis_frame()
    phase_config = _phase9b_config()
    episode_frame = build_phase9b_episode_frame(analysis, phase_config)
    cluster_metrics = build_phase9b_cluster_episode_metrics(
        analysis,
        episode_frame,
        phase_config,
    )
    stability = build_phase9b_stability_summary(cluster_metrics, phase_config)
    instability = build_phase9b_instability_report(stability)
    helpful = build_phase9b_helpful_stability_report(stability)
    summary = build_phase9b_summary(cluster_metrics, stability, instability, helpful)
    gate_report = build_phase9b_gate_report(summary, phase_config)
    conclusion = build_phase9b_conclusion(gate_report)

    assert not stability.empty
    assert not instability.empty
    assert not summary.empty
    assert not gate_report.empty
    assert conclusion.iloc[0]["phase"] == "Phase 9B"


def test_save_phase9b_writes_expected_reports(tmp_path):
    periods = 520
    prices = _price_frame(periods=periods)
    candidate = _strategy_frame("2020-01-01", periods, 0.0005)
    buy_hold = _strategy_frame("2020-01-01", periods, 0.0007)
    spy_12m = _strategy_frame("2020-01-01", periods, 0.0003)

    config = {
        "phase9a_technical_indicator_expansion_diagnostic": _phase9a_config(),
        "phase9b_technical_regime_cluster_stability_audit": {
            "enabled": True,
            **_phase9b_config(),
        },
    }

    outputs = save_phase9b_technical_regime_cluster_stability_audit(
        config=config,
        reports_dir=tmp_path,
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        price_data=prices,
    )

    assert not outputs["summary"].empty
    assert (tmp_path / "phase9b_technical_cluster_analysis_frame.csv").exists()
    assert (tmp_path / "phase9b_technical_cluster_episode_frame.csv").exists()
    assert (tmp_path / "phase9b_technical_cluster_episode_metrics.csv").exists()
    assert (tmp_path / "phase9b_technical_cluster_stability_summary.csv").exists()
    assert (tmp_path / "phase9b_technical_cluster_instability_report.csv").exists()
    assert (
        tmp_path / "phase9b_technical_cluster_helpful_stability_report.csv"
    ).exists()
    assert (tmp_path / "phase9b_technical_cluster_summary.csv").exists()
    assert (tmp_path / "phase9b_technical_cluster_gate_report.csv").exists()
    assert (tmp_path / "phase9b_technical_cluster_conclusion.csv").exists()
    assert (
        tmp_path / "phase9b_technical_regime_cluster_stability_audit.md"
    ).exists()