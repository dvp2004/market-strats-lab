import pandas as pd

from market_strats.analysis.regime_switch_overlay_switch_failure_attribution import (
    _add_failure_attribution_buckets,
    _bucket_spy_drawdown,
    _bucket_trend_distance,
    _create_failure_attribution_summary,
)


def test_bucket_spy_drawdown():
    assert _bucket_spy_drawdown(-2.0) == "near_highs_0_to_-5"
    assert _bucket_spy_drawdown(-7.0) == "mild_drawdown_-5_to_-10"
    assert _bucket_spy_drawdown(-15.0) == "correction_-10_to_-20"
    assert _bucket_spy_drawdown(-25.0) == "deep_drawdown_below_-20"


def test_bucket_trend_distance():
    assert _bucket_trend_distance(3.0) == "well_above_trend_2_plus"
    assert _bucket_trend_distance(1.0) == "near_above_trend_0_to_2"
    assert _bucket_trend_distance(-1.0) == "near_below_trend_0_to_-2"
    assert _bucket_trend_distance(-3.0) == "below_trend_-2_to_-5"
    assert _bucket_trend_distance(-6.0) == "deep_below_trend_below_-5"


def test_add_failure_attribution_buckets():
    events = pd.DataFrame(
        {
            "transition": ["offensive_spy_to_defensive_allocator"],
            "spy_drawdown_pct": [-12.0],
            "spy_distance_from_trend_pct": [-3.0],
            "applied_overlay_slippage_bps": [25.0],
        }
    )

    output = _add_failure_attribution_buckets(events)

    assert output.iloc[0]["slippage_bucket"] == "25_bps"
    assert output.iloc[0]["spy_drawdown_bucket"] == "correction_-10_to_-20"
    assert output.iloc[0]["trend_distance_bucket"] == "below_trend_-2_to_-5"


def test_create_failure_attribution_summary():
    events = pd.DataFrame(
        {
            "transition": [
                "offensive_spy_to_defensive_allocator",
                "defensive_allocator_to_offensive_spy",
                "offensive_spy_to_defensive_allocator",
            ],
            "spy_drawdown_pct": [-12.0, -4.0, -25.0],
            "spy_distance_from_trend_pct": [-3.0, 1.0, -6.0],
            "applied_overlay_slippage_bps": [25.0, 5.0, 50.0],
            "switch_value_added_5d_pct_points": [-1.0, 0.5, -2.0],
            "switch_helped_5d": [False, True, False],
            "switch_value_added_20d_pct_points": [-2.0, 1.0, -3.0],
            "switch_helped_20d": [False, True, False],
            "switch_value_added_60d_pct_points": [-1.5, 2.0, -4.0],
            "switch_helped_60d": [False, True, False],
        }
    )

    attributed = _add_failure_attribution_buckets(events)
    summary = _create_failure_attribution_summary(attributed, horizons=[5, 20, 60])

    assert not summary.empty
    assert "all_switches" in set(summary["group"])
    assert "slippage_bucket" in set(summary["group_dimension"])