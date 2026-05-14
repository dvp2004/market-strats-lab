import pandas as pd

from market_strats.analysis.eth_quarantine_diagnostic import (
    _asset_allocation_stats,
    _create_decision,
)


def test_asset_allocation_stats_returns_zero_when_missing():
    allocation_summary = pd.DataFrame(
        {
            "universe": ["Base"],
            "asset": ["SPY"],
            "avg_weight_pct": [10.0],
            "max_weight_pct": [33.333],
            "days_held": [100],
            "pct_days_held": [20.0],
            "final_weight_pct": [0.0],
        }
    )

    stats = _asset_allocation_stats(
        allocation_summary=allocation_summary,
        universe_name="Base + ETH Quarantine",
        asset="ETH-USD",
    )

    assert stats["avg_weight_pct"] == 0.0
    assert stats["days_held"] == 0


def test_create_decision_classifies_eth_quarantine_candidate():
    metrics = pd.DataFrame(
        {
            "strategy": [
                "Base Allocator",
                "Base + ETH Quarantine Allocator",
                "Base + Oil + ETH Quarantine Allocator",
                "Base 3D Overlay",
                "Base + ETH Quarantine 3D Overlay",
                "Base + Oil + ETH Quarantine 3D Overlay",
            ],
            "cagr_pct": [9.0, 9.4, 9.5, 10.0, 10.4, 10.5],
            "calmar": [0.35, 0.38, 0.39, 0.40, 0.44, 0.45],
            "max_drawdown_pct": [-25.0, -25.5, -25.4, -24.0, -24.5, -24.4],
            "volatility_pct": [14.0, 14.5, 14.6, 13.5, 14.0, 14.1],
        }
    )

    allocation_summary = pd.DataFrame(
        {
            "universe": [
                "Base + ETH Quarantine",
                "Base + Oil + ETH Quarantine",
                "Base + Oil + ETH Quarantine",
            ],
            "asset": ["ETH-USD", "ETH-USD", "USO"],
            "avg_weight_pct": [2.0, 2.2, 1.5],
            "max_weight_pct": [10.0, 10.0, 33.333],
            "days_held": [120, 130, 100],
            "pct_days_held": [12.0, 13.0, 10.0],
            "final_weight_pct": [0.0, 0.0, 0.0],
        }
    )

    decision = _create_decision(
        metrics=metrics,
        allocation_summary=allocation_summary,
        baseline_name="Base",
        eth_name="Base + ETH Quarantine",
        oil_eth_name="Base + Oil + ETH Quarantine",
    )

    assert not decision.empty
    first = decision.iloc[0]
    assert first["eth_used"]
    assert not first["eth_dominates"]
    assert first["final_classification"] == "Quarantined candidate"