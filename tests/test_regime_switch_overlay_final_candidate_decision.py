import pandas as pd

from market_strats.analysis.regime_switch_overlay_final_candidate_decision import (
    _create_delta_report,
    _create_final_gate_report,
)


def test_create_delta_report():
    comparison = pd.DataFrame(
        {
            "period": ["full", "full"],
            "segment_type": ["core", "core"],
            "candidate_name": [
                "Phase 6B loose relief candidate",
                "Phase 4 execution candidate",
            ],
            "cagr_pct": [10.35, 9.93],
            "calmar": [0.429, 0.412],
            "max_drawdown_pct": [-24.12, -24.12],
            "volatility_pct": [13.5, 13.6],
            "trade_count": [36, 46],
        }
    )

    delta = _create_delta_report(
        comparison=comparison,
        final_candidate_name="Phase 6B loose relief candidate",
        benchmark_names=["Phase 4 execution candidate"],
    )

    assert len(delta) == 1
    row = delta.iloc[0]
    assert row["cagr_delta_pct_points"] == 0.42
    assert row["calmar_delta"] == 0.017
    assert row["trade_count_delta"] == -10


def test_create_final_gate_report_passes():
    comparison = pd.DataFrame(
        {
            "period": [
                "full",
                "full",
                "full",
                "holdout",
                "holdout",
                "crisis_2006_2010",
                "crisis_2006_2010",
            ],
            "segment_type": [
                "core",
                "core",
                "core",
                "core",
                "core",
                "episode",
                "episode",
            ],
            "candidate_name": [
                "Phase 6B loose relief candidate",
                "Phase 4 execution candidate",
                "Phase 3 flat 5bps 3D overlay",
                "Phase 6B loose relief candidate",
                "Phase 4 execution candidate",
                "Phase 6B loose relief candidate",
                "Phase 4 execution candidate",
            ],
            "cagr_pct": [10.35, 9.93, 10.22, 12.05, 11.62, 10.64, 9.49],
            "calmar": [0.429, 0.412, 0.429, 0.500, 0.482, 0.642, 0.543],
            "max_drawdown_pct": [-24.12, -24.12, -23.84, -24.12, -24.12, -17.49, -17.49],
            "volatility_pct": [13.5, 13.6, 13.58, 13.6, 13.6, 14.0, 14.0],
            "trade_count": [36, 46, 52, 20, 26, 10, 12],
        }
    )

    delta_report = _create_delta_report(
        comparison=comparison,
        final_candidate_name="Phase 6B loose relief candidate",
        benchmark_names=["Phase 4 execution candidate"],
    )

    config = {
        "phase6_final_candidate_decision": {
            "pinned_phase3_flat_5bps": {
                "cagr_pct": 10.22,
                "calmar": 0.429,
                "max_drawdown_pct": -23.84,
            },
            "pinned_spy_12m_momentum": {
                "cagr_pct": 9.68,
                "calmar": 0.287,
                "max_drawdown_pct": -33.72,
            },
            "pinned_spy_buy_hold": {
                "cagr_pct": 10.90,
                "calmar": 0.197,
                "max_drawdown_pct": -55.19,
            },
            "min_cagr_improvement_vs_execution_benchmark_pct_points": 0.30,
            "min_calmar_improvement_vs_execution_benchmark": 0.010,
            "max_allowed_drawdown_damage_pct_points": -0.50,
            "max_allowed_holdout_cagr_damage_pct_points": -0.50,
            "max_allowed_holdout_calmar_damage": -0.05,
            "max_allowed_holdout_drawdown_damage_pct_points": -0.50,
        }
    }

    gate_report = _create_final_gate_report(
        comparison=comparison,
        delta_report=delta_report,
        config=config,
    )

    final_gate = gate_report[
        gate_report["gate"]
        == "Phase 6B candidate can be promoted as best execution-realistic candidate."
    ].iloc[0]

    assert final_gate["status"] == "Passed"