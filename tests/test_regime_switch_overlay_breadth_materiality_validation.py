import pandas as pd

from market_strats.analysis.regime_switch_overlay_breadth_materiality_validation import (
    _create_materiality_summary,
    _variant_name_for_threshold,
)


def test_variant_name_for_threshold():
    assert _variant_name_for_threshold(0.33) == "defensive_breadth_threshold_0_33"
    assert _variant_name_for_threshold(0.50) == "defensive_breadth_threshold_0_50"
    assert _variant_name_for_threshold(0.67) == "defensive_breadth_threshold_0_67"


def test_create_materiality_summary():
    metrics = pd.DataFrame(
        {
            "period": ["full", "full"],
            "segment_type": ["core", "core"],
            "variant_name": [
                "phase4_execution_candidate",
                "defensive_breadth_threshold_0_50",
            ],
            "cagr_pct": [9.93, 10.10],
            "calmar": [0.412, 0.420],
            "max_drawdown_pct": [-24.12, -24.00],
            "end_value": [66429.13, 68000.0],
            "trade_count": [46, 44],
        }
    )

    summary = _create_materiality_summary(
        metrics=metrics,
        benchmark_variant="phase4_execution_candidate",
    )

    row = summary[
        summary["variant_name"] == "defensive_breadth_threshold_0_50"
    ].iloc[0]

    assert row["cagr_delta_pct_points"] == 0.17
    assert row["calmar_delta"] == 0.008
    assert row["trade_count_delta"] == -2