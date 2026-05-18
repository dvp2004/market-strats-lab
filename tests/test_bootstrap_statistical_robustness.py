import numpy as np
import pandas as pd

from market_strats.analysis.bootstrap_statistical_robustness import (
    _bootstrap_block_indices,
    _create_bootstrap_gate_report,
    _create_bootstrap_probability_report,
    _metrics_from_returns,
)


def test_bootstrap_block_indices_returns_expected_length():
    rng = np.random.default_rng(42)

    indices = _bootstrap_block_indices(
        n_rows=100,
        block_length=21,
        rng=rng,
    )

    assert len(indices) == 100
    assert indices.min() >= 0
    assert indices.max() < 100


def test_metrics_from_returns_calculates_drawdown_and_cagr():
    returns = np.array([0.10, -0.05, 0.02, -0.01, 0.03])

    metrics = _metrics_from_returns(
        returns=returns,
        initial_capital=10000.0,
    )

    assert metrics["end_value"] > 0
    assert "cagr_pct" in metrics
    assert metrics["max_drawdown_pct"] < 0
    assert "calmar" in metrics


def test_create_bootstrap_probability_report():
    samples = pd.DataFrame(
        {
            "candidate_cagr_pct": [10.0, 11.0, 12.0],
            "candidate_calmar": [0.40, 0.50, 0.60],
            "candidate_max_drawdown_pct": [-20.0, -21.0, -19.0],
            "buy_hold_cagr_pct": [12.0, 12.0, 12.0],
            "buy_hold_calmar": [0.20, 0.20, 0.20],
            "buy_hold_max_drawdown_pct": [-50.0, -50.0, -50.0],
            "spy_12m_cagr_pct": [9.0, 10.0, 11.0],
            "spy_12m_calmar": [0.30, 0.30, 0.30],
            "spy_12m_max_drawdown_pct": [-30.0, -30.0, -30.0],
        }
    )

    report = _create_bootstrap_probability_report(samples)

    assert set(report["claim"]) == {
        "Candidate beats SPY 12M on CAGR",
        "Candidate beats SPY 12M on Calmar",
        "Candidate has better max drawdown than SPY 12M",
        "Candidate beats SPY Buy & Hold on CAGR",
        "Candidate beats SPY Buy & Hold on Calmar",
        "Candidate has better max drawdown than SPY Buy & Hold",
    }


def test_create_bootstrap_gate_report_uses_buy_hold_cagr_as_hierarchy_check():
    probability_report = pd.DataFrame(
        {
            "claim": [
                "Candidate beats SPY 12M on CAGR",
                "Candidate beats SPY 12M on Calmar",
                "Candidate has better max drawdown than SPY 12M",
                "Candidate beats SPY Buy & Hold on CAGR",
                "Candidate beats SPY Buy & Hold on Calmar",
                "Candidate has better max drawdown than SPY Buy & Hold",
            ],
            "probability": [0.70, 0.80, 0.90, 0.20, 0.80, 0.90],
            "probability_pct": [70.0, 80.0, 90.0, 20.0, 80.0, 90.0],
        }
    )

    config = {
        "phase7_bootstrap_statistical_robustness": {
            "min_probability_candidate_beats_spy_12m_cagr": 0.55,
            "min_probability_candidate_beats_spy_12m_calmar": 0.60,
            "min_probability_candidate_beats_spy_12m_max_drawdown": 0.60,
            "max_allowed_probability_candidate_beats_buy_hold_cagr_claim": 0.50,
            "min_probability_candidate_beats_buy_hold_calmar": 0.60,
            "min_probability_candidate_beats_buy_hold_max_drawdown": 0.70,
        }
    }

    gate_report = _create_bootstrap_gate_report(
        probability_report=probability_report,
        config=config,
    )

    assert (gate_report["status"] == "Passed").all()