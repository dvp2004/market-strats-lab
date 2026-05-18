import pandas as pd

from market_strats.analysis.bootstrap_stability_audit import (
    _create_probability_stability_summary,
    _create_stability_conclusion,
    _profile_config,
)


def test_profile_config_maps_phase7e_to_phase7d_config():
    config = {
        "phase7_bootstrap_stability_audit": {
            "initial_capital": 10000.0,
            "min_probability_candidate_beats_spy_12m_cagr": 0.55,
            "min_probability_candidate_beats_spy_12m_calmar": 0.60,
            "min_probability_candidate_beats_spy_12m_max_drawdown": 0.60,
            "min_probability_candidate_beats_buy_hold_calmar": 0.60,
            "min_probability_candidate_beats_buy_hold_max_drawdown": 0.70,
            "max_allowed_probability_candidate_beats_buy_hold_cagr_claim": 0.50,
        }
    }

    profile = _profile_config(
        base_config=config,
        block_length_days=21,
        random_seed=42,
        bootstrap_iterations=300,
    )

    phase7d = profile["phase7_bootstrap_statistical_robustness"]

    assert phase7d["enabled"] is True
    assert phase7d["block_length_days"] == 21
    assert phase7d["random_seed"] == 42
    assert phase7d["bootstrap_iterations"] == 300


def test_create_probability_stability_summary():
    gates = pd.DataFrame(
        {
            "claim": [
                "Candidate beats SPY 12M on CAGR",
                "Candidate beats SPY 12M on CAGR",
                "Candidate beats SPY Buy & Hold on Calmar",
            ],
            "status": ["Passed", "Failed", "Passed"],
            "probability": [0.60, 0.50, 0.80],
        }
    )

    summary = _create_probability_stability_summary(gates)

    cagr_row = summary[
        summary["claim"] == "Candidate beats SPY 12M on CAGR"
    ].iloc[0]

    assert cagr_row["profile_count"] == 2
    assert cagr_row["passed_profile_count"] == 1
    assert cagr_row["failed_profile_count"] == 1
    assert cagr_row["min_probability"] == 0.5


def test_create_stability_conclusion_survives_when_all_profiles_pass():
    profiles = pd.DataFrame(
        {
            "profile_id": [1, 2],
            "all_gates_passed": [True, True],
        }
    )
    gates = pd.DataFrame(
        {
            "claim": [
                "Candidate beats SPY 12M on CAGR",
                "Candidate beats SPY Buy & Hold on Calmar",
            ],
            "status": ["Passed", "Passed"],
            "probability": [0.70, 0.80],
        }
    )
    config = {
        "phase7_bootstrap_stability_audit": {
            "min_profiles_passing_all_gates": 1.0,
        }
    }

    conclusion = _create_stability_conclusion(
        profiles=profiles,
        gates=gates,
        config=config,
    )

    first_row = conclusion.iloc[0]

    assert first_row["claim"] == (
        "Bootstrap conclusion is stable across block lengths and random seeds."
    )
    assert first_row["status"] == "Survived"


def test_create_stability_conclusion_fails_when_profile_pass_share_too_low():
    profiles = pd.DataFrame(
        {
            "profile_id": [1, 2],
            "all_gates_passed": [True, False],
        }
    )
    gates = pd.DataFrame(
        {
            "claim": [
                "Candidate beats SPY 12M on CAGR",
                "Candidate beats SPY Buy & Hold on Calmar",
            ],
            "status": ["Passed", "Failed"],
            "probability": [0.70, 0.50],
        }
    )
    config = {
        "phase7_bootstrap_stability_audit": {
            "min_profiles_passing_all_gates": 1.0,
        }
    }

    conclusion = _create_stability_conclusion(
        profiles=profiles,
        gates=gates,
        config=config,
    )

    first_row = conclusion.iloc[0]

    assert first_row["status"] == "Failed"