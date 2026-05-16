import pandas as pd

from market_strats.analysis.regime_switch_overlay_guard_promotion_validation import (
    _create_guard_promotion_gate_report,
    _create_guard_promotion_summary,
)


def test_create_guard_promotion_summary():
    metrics = pd.DataFrame(
        {
            "period": ["full", "full"],
            "segment_type": ["core", "core"],
            "guard_name": ["baseline_no_guard", "deep_drawdown_guard"],
            "cagr_pct": [9.49, 9.93],
            "calmar": [0.393, 0.412],
            "max_drawdown_pct": [-24.12, -24.12],
            "end_value": [61294.08, 66429.13],
            "trade_count": [52, 46],
        }
    )

    summary = _create_guard_promotion_summary(
        metrics=metrics,
        benchmark_guard="baseline_no_guard",
        candidate_guard="deep_drawdown_guard",
    )

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["cagr_delta_pct_points"] == 0.44
    assert row["calmar_delta"] == 0.019
    assert row["trade_count_delta"] == -6


def test_create_guard_promotion_gate_report_passes_when_all_gates_pass():
    summary = pd.DataFrame(
        {
            "period": ["full", "holdout", "crisis_2006_2010"],
            "segment_type": ["core", "core", "episode"],
            "candidate_cagr_pct": [9.93, 11.62, 8.0],
            "candidate_calmar": [0.412, 0.482, 0.30],
            "candidate_max_drawdown_pct": [-24.12, -24.12, -20.0],
            "cagr_delta_pct_points": [0.44, 0.0, 0.1],
            "calmar_delta": [0.019, 0.0, 0.01],
            "drawdown_delta_pct_points": [0.0, 0.0, 0.0],
        }
    )
    config = {
        "phase4_guard_promotion_validation": {
            "spy_12m_cagr_gate": 9.68,
            "spy_12m_calmar_gate": 0.287,
            "spy_12m_max_drawdown_gate": -33.72,
            "max_allowed_segment_cagr_damage_pct_points": -0.50,
            "max_allowed_segment_calmar_damage": -0.05,
            "max_allowed_segment_drawdown_damage_pct_points": -1.00,
        }
    }

    gate_report = _create_guard_promotion_gate_report(
        summary=summary,
        config=config,
    )

    final_gate = gate_report[
        gate_report["gate"]
        == "Candidate can be promoted to execution-realistic overlay candidate."
    ].iloc[0]

    assert final_gate["status"] == "Passed"


def test_create_guard_promotion_gate_report_fails_segment_damage():
    summary = pd.DataFrame(
        {
            "period": ["full", "holdout", "crisis_2006_2010"],
            "segment_type": ["core", "core", "episode"],
            "candidate_cagr_pct": [9.93, 11.62, 8.0],
            "candidate_calmar": [0.412, 0.482, 0.30],
            "candidate_max_drawdown_pct": [-24.12, -24.12, -20.0],
            "cagr_delta_pct_points": [0.44, 0.0, -1.0],
            "calmar_delta": [0.019, 0.0, 0.01],
            "drawdown_delta_pct_points": [0.0, 0.0, 0.0],
        }
    )
    config = {
        "phase4_guard_promotion_validation": {
            "spy_12m_cagr_gate": 9.68,
            "spy_12m_calmar_gate": 0.287,
            "spy_12m_max_drawdown_gate": -33.72,
            "max_allowed_segment_cagr_damage_pct_points": -0.50,
            "max_allowed_segment_calmar_damage": -0.05,
            "max_allowed_segment_drawdown_damage_pct_points": -1.00,
        }
    }

    gate_report = _create_guard_promotion_gate_report(
        summary=summary,
        config=config,
    )

    segment_gate = gate_report[
        gate_report["gate"] == "Candidate avoids material episode-level damage."
    ].iloc[0]

    assert segment_gate["status"] == "Failed"