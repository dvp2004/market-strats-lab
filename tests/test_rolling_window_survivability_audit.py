import numpy as np
import pandas as pd

from market_strats.analysis.rolling_window_survivability_audit import (
    _create_survivability_gate_report,
    _create_window_survivability_summary,
    _metrics_from_returns,
)


def test_metrics_from_returns_outputs_expected_fields():
    returns = np.array([0.01, -0.02, 0.03, 0.01, -0.01])

    metrics = _metrics_from_returns(
        returns=returns,
        initial_capital=10000.0,
    )

    assert "cagr_pct" in metrics
    assert "calmar" in metrics
    assert "max_drawdown_pct" in metrics
    assert metrics["end_value"] > 0


def test_create_window_survivability_summary_counts_window_shares():
    rolling_metrics = pd.DataFrame(
        {
            "window_name": ["1Y", "1Y"],
            "trading_days": [252, 252],
            "candidate_cagr_pct": [10.0, 8.0],
            "spy_12m_cagr_pct": [9.0, 9.0],
            "buy_hold_cagr_pct": [12.0, 12.0],
            "candidate_calmar": [0.5, 0.4],
            "spy_12m_calmar": [0.3, 0.5],
            "buy_hold_calmar": [0.2, 0.3],
            "candidate_max_drawdown_pct": [-20.0, -25.0],
            "spy_12m_max_drawdown_pct": [-30.0, -20.0],
            "buy_hold_max_drawdown_pct": [-50.0, -40.0],
            "candidate_minus_spy_12m_cagr_pct_points": [1.0, -1.0],
            "candidate_minus_buy_hold_cagr_pct_points": [-2.0, -4.0],
        }
    )

    summary = _create_window_survivability_summary(rolling_metrics)

    row = summary.iloc[0]

    assert row["window_name"] == "1Y"
    assert row["window_count"] == 2
    assert row["candidate_beats_spy_12m_cagr_share"] == 0.5
    assert row["candidate_beats_buy_hold_drawdown_share"] == 1.0


def test_create_survivability_gate_report_passes_expected_thresholds():
    summary = pd.DataFrame(
        {
            "window_name": ["1Y"],
            "candidate_beats_spy_12m_calmar_share": [0.7],
            "candidate_beats_spy_12m_drawdown_share": [0.8],
            "candidate_beats_buy_hold_cagr_share": [0.3],
            "candidate_beats_buy_hold_calmar_share": [0.8],
            "candidate_beats_buy_hold_drawdown_share": [0.9],
            "candidate_worst_cagr_pct": [2.0],
        }
    )

    config = {
        "phase7_rolling_window_survivability_audit": {
            "min_candidate_beats_spy_12m_calmar_window_share": 0.55,
            "min_candidate_beats_spy_12m_drawdown_window_share": 0.55,
            "min_candidate_beats_buy_hold_calmar_window_share": 0.60,
            "min_candidate_beats_buy_hold_drawdown_window_share": 0.70,
            "max_candidate_beats_buy_hold_cagr_window_share_for_raw_wealth_hierarchy": 0.50,
        }
    }

    gate_report = _create_survivability_gate_report(
        summary=summary,
        config=config,
    )

    assert (gate_report["status"] == "Passed").all()