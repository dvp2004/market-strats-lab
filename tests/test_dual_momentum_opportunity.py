import pandas as pd

from market_strats.analysis.dual_momentum_opportunity import (
    create_opportunity_cost_segments,
    create_opportunity_cost_summary,
)


def make_dual_result() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=6)

    return pd.DataFrame(
        {
            "date": dates,
            "selected_asset": ["SPY", "SPY", "SPY", "EFA", "EFA", "EFA"],
            "cash_reason": ["INVESTED"] * 6,
            "adj_close_SPY": [100, 110, 120, 130, 140, 150],
            "adj_close_EFA": [100, 100, 100, 100, 105, 110],
            "cash_return": [0.0, 0.001, 0.001, 0.001, 0.001, 0.001],
            "strategy_return": [0.0, 0.10, 0.09, 0.0, 0.05, 0.05],
            "equity": [100, 110, 120, 120, 126, 132],
        }
    )


def test_create_opportunity_cost_segments_outputs_expected_rows():
    result = make_dual_result()

    output = create_opportunity_cost_segments(result, pair_name="TestPair")

    assert len(output) == 2
    assert list(output["selected_asset"]) == ["SPY", "EFA"]
    assert "missed_return_vs_best_pct_points" in output.columns


def test_create_opportunity_cost_segments_identifies_best_available_asset():
    result = make_dual_result()

    output = create_opportunity_cost_segments(result, pair_name="TestPair")

    efa_segment = output[output["selected_asset"] == "EFA"].iloc[0]

    assert efa_segment["best_available_asset"] == "SPY"
    assert efa_segment["missed_return_vs_best_pct_points"] > 0


def test_create_opportunity_cost_summary_groups_by_selected_asset():
    result = make_dual_result()
    segments = create_opportunity_cost_segments(result, pair_name="TestPair")

    summary = create_opportunity_cost_summary(segments)

    assert set(summary["selected_asset"]) == {"SPY", "EFA"}
    assert "avg_missed_return_vs_best_pct_points" in summary.columns