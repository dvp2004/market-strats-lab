import pandas as pd

from market_strats.analysis.regime_switch_overlay_offensive_relief_validation import (
    _create_relief_conclusion,
    _create_relief_gate_report,
    _create_relief_summary,
    _normalise_switch_key,
)


def test_normalise_switch_key():
    events = pd.DataFrame(
        {
            "switch_date": ["2020-01-01"],
            "from_mode": ["defensive_allocator"],
            "to_mode": ["offensive_spy"],
        }
    )

    keys = _normalise_switch_key(events)

    assert keys.iloc[0] == "2020-01-01|defensive_allocator|offensive_spy"


def test_create_relief_summary():
    metrics = pd.DataFrame(
        {
            "period": ["full", "full"],
            "segment_type": ["core", "core"],
            "variant_name": ["phase4_execution_candidate", "baseline_relief"],
            "cagr_pct": [9.93, 10.55],
            "calmar": [0.412, 0.437],
            "max_drawdown_pct": [-24.12, -24.12],
            "end_value": [66429.13, 74386.25],
            "trade_count": [46, 30],
        }
    )

    summary = _create_relief_summary(
        metrics=metrics,
        benchmark_variant="phase4_execution_candidate",
    )

    row = summary[summary["variant_name"] == "baseline_relief"].iloc[0]

    assert row["cagr_delta_pct_points"] == 0.62
    assert row["calmar_delta"] == 0.025
    assert row["trade_count_delta"] == -16

def test_relief_gate_report_selects_best_passing_candidate():
    summary = pd.DataFrame(
        {
            "period": [
                "full",
                "full",
                "full",
                "holdout",
                "holdout",
                "holdout",
                "post_crisis_2011_2015",
                "post_crisis_2011_2015",
                "post_crisis_2011_2015",
            ],
            "segment_type": [
                "core",
                "core",
                "core",
                "core",
                "core",
                "core",
                "episode",
                "episode",
                "episode",
            ],
            "variant_name": [
                "phase4_execution_candidate",
                "baseline_relief",
                "loose_relief",
                "phase4_execution_candidate",
                "baseline_relief",
                "loose_relief",
                "phase4_execution_candidate",
                "baseline_relief",
                "loose_relief",
            ],
            "cagr_delta_pct_points": [
                0.0,
                0.62,
                0.42,
                0.0,
                1.52,
                0.43,
                0.0,
                -0.59,
                -0.23,
            ],
            "calmar_delta": [
                0.0,
                0.025,
                0.017,
                0.0,
                0.063,
                0.018,
                0.0,
                -0.031,
                -0.012,
            ],
            "drawdown_delta_pct_points": [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
        }
    )

    event_summary = pd.DataFrame(
        {
            "variant_name": [
                "phase4_execution_candidate",
                "baseline_relief",
                "loose_relief",
            ],
            "switch_count": [46, 30, 36],
        }
    )

    config = {
        "phase6_offensive_relief_validation": {
            "benchmark_variant": "phase4_execution_candidate",
            "min_full_cagr_improvement_pct_points": 0.30,
            "min_full_calmar_improvement": 0.010,
            "max_allowed_holdout_cagr_damage_pct_points": -0.50,
            "max_allowed_holdout_calmar_damage": -0.05,
            "max_allowed_drawdown_damage_pct_points": -0.50,
            "max_allowed_episode_cagr_damage_pct_points": -0.50,
            "max_allowed_episode_calmar_damage": -0.05,
            "max_allowed_switch_count_reduction": -10,
        }
    }

    gate_report = _create_relief_gate_report(
        summary=summary,
        event_summary=event_summary,
        config=config,
    )

    final_gate = gate_report[
        gate_report["gate"]
        == "Offensive relief confirmation is validated for promotion."
    ].iloc[0]

    assert final_gate["status"] == "Passed"
    assert final_gate["candidate_variant"] == "loose_relief"

    baseline_final = gate_report[
        (gate_report["candidate_variant"] == "baseline_relief")
        & (
            gate_report["gate"]
            == "Offensive relief variant passes all validation gates."
        )
    ].iloc[0]

    assert baseline_final["status"] == "Failed"

    loose_final = gate_report[
        (gate_report["candidate_variant"] == "loose_relief")
        & (
            gate_report["gate"]
            == "Offensive relief variant passes all validation gates."
        )
    ].iloc[0]

    assert loose_final["status"] == "Passed"


def test_relief_conclusion_survives_when_candidate_passes():
    gate_report = pd.DataFrame(
        {
            "candidate_variant": ["loose_relief"],
            "gate": [
                "Offensive relief confirmation is validated for promotion.",
            ],
            "status": ["Passed"],
            "evidence_quality": ["test"],
            "interpretation": ["loose_relief passed."],
        }
    )

    conclusion = _create_relief_conclusion(gate_report)

    first_claim = conclusion.iloc[0]

    assert first_claim["status"] == "Survived"
    assert "loose_relief" in first_claim["interpretation"]