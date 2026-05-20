import pandas as pd

from market_strats.analysis.walk_forward_validation_audit import (
    _resolve_phase8c_input_frames,
    build_phase8c_comparison,
    build_phase8c_gate_report,
    build_phase8c_summary,
    build_phase8c_walk_forward_windows,
    build_phase8c_window_metrics,
    Phase8CInput,
    save_phase8c_walk_forward_validation_audit,
)


def _sample_frame(start: str, periods: int, daily_return: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=periods, freq="B"),
            "strategy_return": [daily_return] * periods,
            "turnover": [0.0] * periods,
        }
    )


def test_phase8c_inputs_align_to_candidate_period_and_reset_first_return():
    candidate = _sample_frame("2006-04-28", 5, 0.01)
    candidate["equity"] = 10000.0

    buy_hold = _sample_frame("2006-04-25", 10, 0.99)
    spy_12m = _sample_frame("2006-04-25", 10, 0.88)

    resolved_candidate, resolved_buy_hold, resolved_12m = _resolve_phase8c_input_frames(
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


def test_phase8c_builds_walk_forward_windows():
    frame = _sample_frame("2006-04-28", 252 * 12, 0.0001)

    phase_config = {
        "window": {
            "initial_train_years": 3,
            "test_years": 2,
            "step_years": 2,
            "include_partial_last_window": True,
            "min_test_years": 1.0,
        }
    }

    windows = build_phase8c_walk_forward_windows(frame, phase_config)

    assert not windows.empty
    assert {"train_start_date", "train_end_date", "test_start_date", "test_end_date"}.issubset(
        windows.columns
    )


def test_phase8c_metrics_summary_and_gate_report_are_created():
    candidate = _sample_frame("2006-04-28", 252 * 10, 0.0005)
    buy_hold = _sample_frame("2006-04-28", 252 * 10, 0.0007)
    spy_12m = _sample_frame("2006-04-28", 252 * 10, 0.0003)

    phase_config = {
        "strategy_names": {
            "final_candidate": "Final candidate",
            "spy_buy_hold": "SPY Buy & Hold",
            "spy_12m_momentum": "SPY 12M Momentum",
        },
        "window": {
            "initial_train_years": 3,
            "test_years": 2,
            "step_years": 2,
            "include_partial_last_window": True,
            "min_test_years": 1.0,
        },
        "gates": {
            "min_test_windows": 2,
            "min_candidate_beats_spy12m_cagr_rate": 0.50,
            "min_candidate_beats_spy12m_calmar_rate": 0.50,
            "min_candidate_better_spy12m_drawdown_rate": 0.00,
            "min_candidate_positive_cagr_rate": 0.50,
            "max_candidate_beats_buy_hold_cagr_rate_for_hierarchy": 1.00,
            "min_candidate_beats_buy_hold_calmar_rate": 0.00,
            "min_candidate_better_buy_hold_drawdown_rate": 0.00,
            "require_worst_candidate_cagr_positive": True,
        },
    }

    windows = build_phase8c_walk_forward_windows(candidate, phase_config)
    metrics = build_phase8c_window_metrics(
        [
            Phase8CInput("Final candidate", candidate),
            Phase8CInput("SPY Buy & Hold", buy_hold),
            Phase8CInput("SPY 12M Momentum", spy_12m),
        ],
        windows,
        initial_capital=10000.0,
    )
    comparison = build_phase8c_comparison(metrics, phase_config)
    summary = build_phase8c_summary(comparison)
    gate_report = build_phase8c_gate_report(summary, phase_config)

    assert not metrics.empty
    assert not comparison.empty
    assert not summary.empty
    assert not gate_report.empty
    assert "passed" in gate_report.columns


def test_save_phase8c_writes_expected_reports(tmp_path):
    candidate = _sample_frame("2006-04-28", 252 * 10, 0.0005)
    candidate["equity"] = 10000.0
    buy_hold = _sample_frame("2006-04-28", 252 * 10, 0.0007)
    spy_12m = _sample_frame("2006-04-28", 252 * 10, 0.0003)

    config = {
        "phase8c_walk_forward_validation_audit": {
            "enabled": True,
            "initial_capital": 10000.0,
            "window": {
                "initial_train_years": 3,
                "test_years": 2,
                "step_years": 2,
                "include_partial_last_window": True,
                "min_test_years": 1.0,
            },
            "gates": {
                "min_test_windows": 2,
                "max_candidate_beats_buy_hold_cagr_rate_for_hierarchy": 1.00,
            },
        }
    }

    outputs = save_phase8c_walk_forward_validation_audit(
        config=config,
        reports_dir=tmp_path,
        final_candidate=candidate,
        spy_buy_hold=buy_hold,
        spy_12m_momentum=spy_12m,
    )

    assert not outputs["windows"].empty
    assert (tmp_path / "phase8c_walk_forward_windows.csv").exists()
    assert (tmp_path / "phase8c_walk_forward_window_metrics.csv").exists()
    assert (tmp_path / "phase8c_walk_forward_comparison.csv").exists()
    assert (tmp_path / "phase8c_walk_forward_summary.csv").exists()
    assert (tmp_path / "phase8c_walk_forward_gate_report.csv").exists()
    assert (tmp_path / "phase8c_walk_forward_conclusion.csv").exists()
    assert (tmp_path / "phase8c_walk_forward_validation_audit.md").exists()