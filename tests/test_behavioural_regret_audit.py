import pandas as pd

from market_strats.analysis.behavioural_regret_audit import (
    _resolve_phase8d_input_frames,
    build_phase8d_daily_regret,
    build_phase8d_gate_report,
    build_phase8d_rolling_regret,
    build_phase8d_rolling_summary,
    build_phase8d_summary,
    save_phase8d_behavioural_regret_audit,
)


def _sample_frame(start: str, periods: int, daily_return: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=periods, freq="B"),
            "strategy_return": [daily_return] * periods,
            "turnover": [0.0] * periods,
        }
    )


def test_phase8d_inputs_align_to_candidate_period_and_reset_first_return():
    candidate = _sample_frame("2006-04-28", 5, 0.01)
    candidate["equity"] = 10000.0

    buy_hold = _sample_frame("2006-04-25", 10, 0.99)
    spy_12m = _sample_frame("2006-04-25", 10, 0.88)

    resolved_candidate, resolved_buy_hold, resolved_12m = _resolve_phase8d_input_frames(
        config={},
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
        relative_momentum_outputs=None,
        ticker_outputs=None,
    )

    expected_start = pd.Timestamp("2006-04-28")
    expected_end = pd.Timestamp("2006-05-04")

    for frame in [resolved_candidate, resolved_buy_hold, resolved_12m]:
        assert frame["date"].min() == expected_start
        assert frame["date"].max() == expected_end
        assert frame.loc[0, "strategy_return"] == 0.0


def test_phase8d_daily_regret_and_summary_are_created():
    candidate = _sample_frame("2020-01-01", 252 * 4, 0.0004)
    buy_hold = _sample_frame("2020-01-01", 252 * 4, 0.0006)
    spy_12m = _sample_frame("2020-01-01", 252 * 4, 0.0003)

    daily = build_phase8d_daily_regret(
        final_candidate=candidate,
        benchmarks={
            "SPY Buy & Hold": buy_hold,
            "SPY 12M Momentum": spy_12m,
        },
        initial_capital=10000.0,
    )
    summary = build_phase8d_summary(daily)

    assert not daily.empty
    assert set(daily["benchmark"]) == {"SPY Buy & Hold", "SPY 12M Momentum"}
    assert not summary.empty
    assert "terminal_relative_wealth" in summary.columns
    assert "max_relative_drawdown" in summary.columns


def test_phase8d_rolling_summary_and_gate_report_are_created():
    candidate = _sample_frame("2010-01-01", 252 * 8, 0.0005)
    buy_hold = _sample_frame("2010-01-01", 252 * 8, 0.0006)
    spy_12m = _sample_frame("2010-01-01", 252 * 8, 0.0003)

    daily = build_phase8d_daily_regret(
        final_candidate=candidate,
        benchmarks={
            "SPY Buy & Hold": buy_hold,
            "SPY 12M Momentum": spy_12m,
        },
        initial_capital=10000.0,
    )
    summary = build_phase8d_summary(daily)
    rolling = build_phase8d_rolling_regret(daily, rolling_windows_years=[1, 3])
    rolling_summary = build_phase8d_rolling_summary(rolling)

    phase_config = {
        "strategy_names": {
            "spy_buy_hold": "SPY Buy & Hold",
            "spy_12m_momentum": "SPY 12M Momentum",
        },
        "gates": {
            "min_terminal_relative_wealth_vs_buy_hold": 0.0,
            "max_time_lagging_buy_hold_rate": 1.0,
            "max_relative_drawdown_vs_buy_hold": 1.0,
            "max_longest_lagging_streak_years_vs_buy_hold": 99.0,
            "min_terminal_relative_wealth_vs_spy12m": 0.0,
            "max_time_lagging_spy12m_rate": 1.0,
            "max_rolling_3y_underperformance_rate_vs_buy_hold": 1.0,
            "min_worst_3y_active_cagr_vs_buy_hold": -1.0,
        },
    }

    gate_report = build_phase8d_gate_report(summary, rolling_summary, phase_config)

    assert not rolling.empty
    assert not rolling_summary.empty
    assert not gate_report.empty
    assert "passed" in gate_report.columns


def test_save_phase8d_writes_expected_reports(tmp_path):
    candidate = _sample_frame("2010-01-01", 252 * 8, 0.0005)
    candidate["equity"] = 10000.0
    buy_hold = _sample_frame("2010-01-01", 252 * 8, 0.0006)
    spy_12m = _sample_frame("2010-01-01", 252 * 8, 0.0003)

    config = {
        "phase8d_behavioural_regret_audit": {
            "enabled": True,
            "initial_capital": 10000.0,
            "rolling_windows_years": [1, 3],
            "gates": {
                "min_terminal_relative_wealth_vs_buy_hold": 0.0,
                "max_time_lagging_buy_hold_rate": 1.0,
                "max_relative_drawdown_vs_buy_hold": 1.0,
                "max_longest_lagging_streak_years_vs_buy_hold": 99.0,
                "min_terminal_relative_wealth_vs_spy12m": 0.0,
                "max_time_lagging_spy12m_rate": 1.0,
                "max_rolling_3y_underperformance_rate_vs_buy_hold": 1.0,
                "min_worst_3y_active_cagr_vs_buy_hold": -1.0,
            },
        }
    }

    outputs = save_phase8d_behavioural_regret_audit(
        config=config,
        reports_dir=tmp_path,
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
    )

    assert not outputs["daily_regret"].empty
    assert (tmp_path / "phase8d_behavioural_regret_daily.csv").exists()
    assert (tmp_path / "phase8d_behavioural_regret_summary.csv").exists()
    assert (tmp_path / "phase8d_behavioural_regret_rolling_windows.csv").exists()
    assert (tmp_path / "phase8d_behavioural_regret_rolling_summary.csv").exists()
    assert (tmp_path / "phase8d_behavioural_regret_gate_report.csv").exists()
    assert (tmp_path / "phase8d_behavioural_regret_conclusion.csv").exists()
    assert (tmp_path / "phase8d_behavioural_regret_audit.md").exists()