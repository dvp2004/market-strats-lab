import pandas as pd

from market_strats.analysis.preregistered_technical_rule_test import (
    build_phase9d_behavioural_metrics,
    build_phase9d_comparison_summary,
    build_phase9d_conclusion,
    build_phase9d_gate_report,
    build_phase9d_metrics,
    build_phase9d_rule_return_frame,
    build_phase9d_stress_metrics,
    save_phase9d_preregistered_technical_rule_test,
)
from market_strats.analysis.technical_indicator_expansion_diagnostic import (
    build_phase9a_analysis_frame,
    build_phase9a_indicator_frame,
    build_phase9a_regime_frame,
)


def _price_frame(start: str = "2020-01-01", periods: int = 520) -> pd.DataFrame:
    prices = [100.0]
    for index in range(1, periods):
        drift = 0.0005 if index % 70 < 45 else -0.0004
        prices.append(prices[-1] * (1.0 + drift))

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


def _phase9d_config() -> dict:
    return {
        "initial_capital": 10000.0,
        "ticker": "SPY",
        "rule_definitions": [
            {
                "rule_id": "H1_oversold_rsi_reentry_relief",
                "name": "Oversold RSI re-entry relief",
                "rule_type": "oversold_rsi_reentry_relief",
                "rsi_threshold": 30.0,
            },
            {
                "rule_id": "H2_negative_12m_momentum_defensive_confirmation",
                "name": "Negative 12M momentum defensive confirmation",
                "rule_type": "negative_12m_momentum_defensive_confirmation",
                "momentum_threshold": 0.0,
            },
        ],
        "holdout": {
            "start_date": "2021-01-01",
            "end_date": "2021-12-31",
        },
        "episode_definitions": {
            "episode_1": {"start_date": "2020-01-01", "end_date": "2020-12-31"},
            "episode_2": {"start_date": "2021-01-01", "end_date": "2021-12-31"},
        },
        "stress_friction": {
            "scenario_name": "test_stress",
            "spread_bps": 5.0,
            "impact_bps_per_100pct_turnover": 10.0,
            "stress_drawdown_threshold": -0.10,
            "deep_stress_drawdown_threshold": -0.20,
            "stress_multiplier": 3.0,
            "deep_stress_multiplier": 5.0,
        },
        "gates": {
            "max_full_cagr_reduction_pts_vs_baseline": 100.0,
            "min_full_calmar_delta_vs_baseline": -999.0,
            "require_full_drawdown_not_worse": False,
            "require_holdout_cagr_not_worse": False,
            "require_holdout_calmar_not_worse": False,
            "require_holdout_drawdown_not_worse": False,
            "max_episode_cagr_damage_pts": 100.0,
            "max_episode_calmar_damage": 999.0,
            "require_stress_calmar_not_worse": False,
            "require_stress_drawdown_not_worse": False,
            "require_behavioural_relative_drawdown_not_worse": False,
            "require_no_strategy_promotion": True,
            "max_allowed_role": "Candidate for further validation only",
        },
    }


def _analysis_inputs():
    periods = 520
    prices = _price_frame(periods=periods)
    candidate = _strategy_frame("2020-01-01", periods, 0.0005)
    buy_hold = _strategy_frame("2020-01-01", periods, 0.0007)
    spy_12m = _strategy_frame("2020-01-01", periods, 0.0003)

    indicators = build_phase9a_indicator_frame(prices, _phase9a_config())
    regimes = build_phase9a_regime_frame(indicators, _phase9a_config())
    analysis = build_phase9a_analysis_frame(
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        regime_frame=regimes,
    )

    return analysis, candidate, buy_hold, spy_12m, prices


def test_phase9d_rule_return_frame_contains_baseline_and_two_rules():
    analysis, candidate, _, _, _ = _analysis_inputs()

    rule_returns = build_phase9d_rule_return_frame(
        analysis_frame=analysis,
        final_candidate=candidate,
        phase_config=_phase9d_config(),
    )

    assert set(rule_returns["rule_id"]) == {
        "baseline_final_candidate",
        "H1_oversold_rsi_reentry_relief",
        "H2_negative_12m_momentum_defensive_confirmation",
    }


def test_phase9d_metrics_gate_report_and_conclusion_are_created():
    analysis, candidate, _, _, _ = _analysis_inputs()
    phase_config = _phase9d_config()

    rule_returns = build_phase9d_rule_return_frame(
        analysis_frame=analysis,
        final_candidate=candidate,
        phase_config=phase_config,
    )
    metrics = build_phase9d_metrics(rule_returns, phase_config)
    stress_metrics = build_phase9d_stress_metrics(rule_returns, phase_config)
    behavioural_metrics = build_phase9d_behavioural_metrics(rule_returns)
    comparison = build_phase9d_comparison_summary(
        metrics,
        stress_metrics,
        behavioural_metrics,
    )
    gate_report = build_phase9d_gate_report(comparison, phase_config)
    conclusion = build_phase9d_conclusion(gate_report)

    assert not metrics.empty
    assert not stress_metrics.empty
    assert not behavioural_metrics.empty
    assert not comparison.empty
    assert not gate_report.empty
    assert conclusion.iloc[0]["phase"] == "Phase 9D"


def test_save_phase9d_writes_expected_reports(tmp_path):
    analysis, candidate, buy_hold, spy_12m, prices = _analysis_inputs()
    del analysis

    config = {
        "phase9a_technical_indicator_expansion_diagnostic": _phase9a_config(),
        "phase9d_preregistered_technical_rule_test": {
            "enabled": True,
            **_phase9d_config(),
        },
    }

    outputs = save_phase9d_preregistered_technical_rule_test(
        config=config,
        reports_dir=tmp_path,
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        price_data=prices,
    )

    assert not outputs["comparison_summary"].empty
    assert (tmp_path / "phase9d_preregistered_rule_returns.csv").exists()
    assert (tmp_path / "phase9d_preregistered_rule_metrics.csv").exists()
    assert (tmp_path / "phase9d_preregistered_rule_stress_metrics.csv").exists()
    assert (
        tmp_path / "phase9d_preregistered_rule_behavioural_metrics.csv"
    ).exists()
    assert (
        tmp_path / "phase9d_preregistered_rule_comparison_summary.csv"
    ).exists()
    assert (tmp_path / "phase9d_preregistered_rule_gate_report.csv").exists()
    assert (tmp_path / "phase9d_preregistered_rule_conclusion.csv").exists()
    assert (tmp_path / "phase9d_preregistered_technical_rule_test.md").exists()