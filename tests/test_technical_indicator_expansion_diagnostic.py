import pandas as pd

from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    build_phase9a_analysis_frame,
    build_phase9a_conclusion,
    build_phase9a_gate_report,
    build_phase9a_indicator_frame,
    build_phase9a_regime_frame,
    build_phase9a_regime_summary,
    build_phase9a_summary,
    build_phase9a_underperformance_clusters,
    save_phase9a_technical_indicator_expansion_diagnostic,
)


def _price_frame(start: str = "2020-01-01", periods: int = 400) -> pd.DataFrame:
    prices = [100.0]
    for index in range(1, periods):
        prices.append(prices[-1] * (1.0 + 0.0005 + (0.0002 if index % 20 < 10 else -0.0001)))

    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=periods, freq="B"),
            "adj_close": prices,
            "close": prices,
        }
    )


def _strategy_frame(start: str, periods: int, daily_return: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=periods, freq="B"),
            "strategy_return": [daily_return] * periods,
            "turnover": [0.0] * periods,
        }
    )


def _phase_config() -> dict:
    return {
        "initial_capital": 10000.0,
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
        "gates": {
            "min_indicator_coverage_rate": 0.50,
            "min_regime_rows": 4,
            "require_no_strategy_promotion": True,
            "require_underperformance_clusters_reported": True,
            "max_allowed_final_candidate_role": "Diagnostic only",
        },
    }


def test_phase9a_indicator_and_regime_frames_are_created():
    prices = _price_frame()
    phase_config = _phase_config()

    indicators = build_phase9a_indicator_frame(prices, phase_config)
    regimes = build_phase9a_regime_frame(indicators, phase_config)

    assert not indicators.empty
    assert "trend_distance_long" in indicators.columns
    assert "rsi" in indicators.columns
    assert "technical_risk_state" in regimes.columns


def test_phase9a_analysis_summary_and_gate_report_are_created():
    periods = 400
    prices = _price_frame(periods=periods)
    candidate = _strategy_frame("2020-01-01", periods, 0.0005)
    buy_hold = _strategy_frame("2020-01-01", periods, 0.0007)
    spy_12m = _strategy_frame("2020-01-01", periods, 0.0003)
    phase_config = _phase_config()

    indicators = build_phase9a_indicator_frame(prices, phase_config)
    regimes = build_phase9a_regime_frame(indicators, phase_config)
    analysis = build_phase9a_analysis_frame(
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        regime_frame=regimes,
    )
    regime_summary = build_phase9a_regime_summary(analysis)
    clusters = build_phase9a_underperformance_clusters(regime_summary)
    summary = build_phase9a_summary(analysis, regime_summary, clusters)
    gate_report = build_phase9a_gate_report(summary, phase_config)
    conclusion = build_phase9a_conclusion(gate_report)

    assert not analysis.empty
    assert not regime_summary.empty
    assert not clusters.empty
    assert not summary.empty
    assert not gate_report.empty
    assert conclusion.iloc[0]["phase"] == "Phase 9A"


def test_save_phase9a_writes_expected_reports(tmp_path):
    periods = 400
    prices = _price_frame(periods=periods)
    candidate = _strategy_frame("2020-01-01", periods, 0.0005)
    candidate["equity"] = 10000.0
    buy_hold = _strategy_frame("2020-01-01", periods, 0.0007)
    spy_12m = _strategy_frame("2020-01-01", periods, 0.0003)

    config = {
        "phase9a_technical_indicator_expansion_diagnostic": {
            "enabled": True,
            **_phase_config(),
        }
    }

    outputs = save_phase9a_technical_indicator_expansion_diagnostic(
        config=config,
        reports_dir=tmp_path,
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        price_data=prices,
    )

    assert not outputs["summary"].empty
    assert (tmp_path / "phase9a_technical_indicator_frame.csv").exists()
    assert (tmp_path / "phase9a_technical_regime_frame.csv").exists()
    assert (tmp_path / "phase9a_technical_indicator_analysis_frame.csv").exists()
    assert (tmp_path / "phase9a_technical_regime_summary.csv").exists()
    assert (tmp_path / "phase9a_technical_underperformance_clusters.csv").exists()
    assert (tmp_path / "phase9a_technical_indicator_summary.csv").exists()
    assert (tmp_path / "phase9a_technical_indicator_gate_report.csv").exists()
    assert (tmp_path / "phase9a_technical_indicator_conclusion.csv").exists()
    assert (tmp_path / "phase9a_technical_indicator_expansion_diagnostic.md").exists()