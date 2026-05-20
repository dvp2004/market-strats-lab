import pandas as pd

from market_strats.analysis.bid_ask_market_impact_diagnostic import (
    apply_bid_ask_market_impact_scenario,
    build_phase8b_daily_returns,
    build_phase8b_gate_report,
    build_phase8b_metrics,
    build_phase8b_summary,
    save_phase8b_bid_ask_market_impact_diagnostic,
    _resolve_phase8b_input_frames,
    Phase8BInput,
)


def _sample_strategy_frame(returns, turnover):
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=len(returns), freq="B"),
            "strategy_return": returns,
            "turnover": turnover,
        }
    )


def test_bid_ask_market_impact_cost_only_applies_on_turnover_days():
    frame = _sample_strategy_frame(
        returns=[0.01, 0.02, -0.01, 0.00],
        turnover=[0.0, 1.0, 0.0, 0.5],
    )

    scenario = {
        "spread_bps": 10.0,
        "impact_bps_per_100pct_turnover": 20.0,
        "stress_drawdown_threshold": -0.10,
        "deep_stress_drawdown_threshold": -0.20,
        "stress_multiplier": 1.0,
        "deep_stress_multiplier": 1.0,
    }

    result = apply_bid_ask_market_impact_scenario(
        frame,
        strategy_name="Candidate",
        scenario_name="stress",
        scenario=scenario,
        initial_capital=10000.0,
    )

    assert result.loc[0, "extra_cost_return"] == 0.0
    assert result.loc[2, "extra_cost_return"] == 0.0
    assert result.loc[1, "extra_cost_return"] > 0.0
    assert result.loc[3, "extra_cost_return"] > 0.0
    assert result.loc[1, "adjusted_strategy_return"] < result.loc[1, "base_strategy_return"]


def test_stress_multiplier_increases_costs_in_drawdown():
    frame = _sample_strategy_frame(
        returns=[0.00, -0.15, 0.00, 0.00],
        turnover=[0.0, 0.0, 1.0, 1.0],
    )

    scenario = {
        "spread_bps": 10.0,
        "impact_bps_per_100pct_turnover": 0.0,
        "stress_drawdown_threshold": -0.10,
        "deep_stress_drawdown_threshold": -0.20,
        "stress_multiplier": 3.0,
        "deep_stress_multiplier": 5.0,
    }

    result = apply_bid_ask_market_impact_scenario(
        frame,
        strategy_name="Candidate",
        scenario_name="stress",
        scenario=scenario,
        initial_capital=10000.0,
    )

    assert result.loc[2, "stress_multiplier"] == 3.0
    assert result.loc[2, "extra_cost_return"] == 0.003


def test_phase8b_builders_create_metrics_summary_and_gate_report():
    candidate = _sample_strategy_frame(
        returns=[0.00, 0.03, 0.02, 0.01, 0.00],
        turnover=[0.0, 0.5, 0.0, 0.5, 0.0],
    )
    spy_12m = _sample_strategy_frame(
        returns=[0.00, 0.02, 0.01, 0.00, 0.00],
        turnover=[0.0, 0.2, 0.0, 0.2, 0.0],
    )
    buy_hold = _sample_strategy_frame(
        returns=[0.00, 0.04, 0.02, 0.01, 0.00],
        turnover=[0.0, 0.0, 0.0, 0.0, 0.0],
    )

    phase_config = {
        "initial_capital": 10000.0,
        "gate_scenario": "stress",
        "strategy_names": {
            "final_candidate": "Final candidate",
            "spy_buy_hold": "SPY Buy & Hold",
            "spy_12m_momentum": "SPY 12M Momentum",
        },
        "gates": {
            "max_candidate_cagr_degradation_pts_vs_no_extra_cost": 99.0,
        },
        "scenarios": {
            "no_extra_cost": {
                "spread_bps": 0.0,
                "impact_bps_per_100pct_turnover": 0.0,
            },
            "stress": {
                "spread_bps": 1.0,
                "impact_bps_per_100pct_turnover": 1.0,
            },
        },
    }

    daily = build_phase8b_daily_returns(
        [
            Phase8BInput("Final candidate", candidate),
            Phase8BInput("SPY Buy & Hold", buy_hold),
            Phase8BInput("SPY 12M Momentum", spy_12m),
        ],
        phase_config=phase_config,
    )

    metrics = build_phase8b_metrics(daily, initial_capital=10000.0)
    summary = build_phase8b_summary(metrics, phase_config)
    gate_report = build_phase8b_gate_report(metrics, summary, phase_config)

    assert not daily.empty
    assert set(metrics["scenario"]) == {"no_extra_cost", "stress"}
    assert not summary.empty
    assert "passed" in gate_report.columns
    assert len(gate_report) == 7


def test_save_phase8b_writes_expected_reports(tmp_path):
    candidate = _sample_strategy_frame(
        returns=[0.00, 0.03, 0.01, 0.01],
        turnover=[0.0, 0.4, 0.0, 0.4],
    )
    spy_12m = _sample_strategy_frame(
        returns=[0.00, 0.02, 0.00, 0.01],
        turnover=[0.0, 0.2, 0.0, 0.2],
    )
    buy_hold = _sample_strategy_frame(
        returns=[0.00, 0.04, 0.01, 0.01],
        turnover=[0.0, 0.0, 0.0, 0.0],
    )

    config = {
        "phase8b_bid_ask_market_impact_diagnostic": {
            "enabled": True,
            "initial_capital": 10000.0,
            "gate_scenario": "stress",
            "gates": {
                "max_candidate_cagr_degradation_pts_vs_no_extra_cost": 99.0,
            },
            "scenarios": {
                "no_extra_cost": {
                    "spread_bps": 0.0,
                    "impact_bps_per_100pct_turnover": 0.0,
                },
                "stress": {
                    "spread_bps": 1.0,
                    "impact_bps_per_100pct_turnover": 1.0,
                },
            },
        }
    }

    outputs = save_phase8b_bid_ask_market_impact_diagnostic(
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["metrics"].empty
    assert (tmp_path / "phase8b_bid_ask_market_impact_daily_returns.csv").exists()
    assert (tmp_path / "phase8b_bid_ask_market_impact_metrics.csv").exists()
    assert (tmp_path / "phase8b_bid_ask_market_impact_summary.csv").exists()
    assert (tmp_path / "phase8b_bid_ask_market_impact_gate_report.csv").exists()
    assert (tmp_path / "phase8b_bid_ask_market_impact_conclusion.csv").exists()
    assert (tmp_path / "phase8b_bid_ask_market_impact_diagnostic.md").exists()

def test_phase8b_resolved_inputs_are_aligned_to_candidate_period():
    candidate = pd.DataFrame(
        {
            "date": pd.date_range("2006-04-28", periods=3, freq="B"),
            "strategy_return": [0.0, 0.01, 0.02],
            "turnover": [0.0, 1.0, 0.0],
            "equity": [10000.0, 10100.0, 10302.0],
        }
    )

    spy_buy_hold = pd.DataFrame(
        {
            "date": pd.date_range("2006-04-25", periods=6, freq="B"),
            "strategy_return": [0.99, 0.99, 0.99, 0.01, 0.01, 0.01],
            "turnover": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    spy_12m = pd.DataFrame(
        {
            "date": pd.date_range("2006-04-25", periods=6, freq="B"),
            "strategy_return": [0.88, 0.88, 0.88, 0.01, 0.01, 0.01],
            "turnover": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    resolved_candidate, resolved_buy_hold, resolved_12m = _resolve_phase8b_input_frames(
        config={},
        final_candidate=candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m,
        relative_momentum_outputs=None,
        ticker_outputs=None,
    )

    expected_start = pd.Timestamp("2006-04-28")
    expected_end = pd.Timestamp("2006-05-02")

    for frame in [resolved_candidate, resolved_buy_hold, resolved_12m]:
        assert frame["date"].min() == expected_start
        assert frame["date"].max() == expected_end
        assert frame.loc[0, "strategy_return"] == 0.0