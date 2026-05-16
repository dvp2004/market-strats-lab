import pandas as pd

from market_strats.analysis.regime_switch_overlay_guard_validation import (
    _create_guard_validation_summary,
    _create_removed_switch_audit,
    _normalise_switch_key,
    _summarise_removed_switches,
)


def test_normalise_switch_key():
    events = pd.DataFrame(
        {
            "switch_date": ["2020-01-01"],
            "from_mode": ["offensive_spy"],
            "to_mode": ["defensive_allocator"],
        }
    )

    keys = _normalise_switch_key(events)

    assert keys.iloc[0] == "2020-01-01|offensive_spy|defensive_allocator"


def test_create_guard_validation_summary():
    metrics = pd.DataFrame(
        {
            "period": ["full", "full"],
            "guard_name": ["baseline_no_guard", "deep_drawdown_guard"],
            "cagr_pct": [9.49, 9.93],
            "calmar": [0.393, 0.412],
            "max_drawdown_pct": [-24.12, -24.12],
            "end_value": [61294.08, 66429.13],
            "trade_count": [52, 46],
        }
    )

    summary = _create_guard_validation_summary(
        metrics=metrics,
        benchmark_guard="baseline_no_guard",
        candidate_guard="deep_drawdown_guard",
    )

    assert not summary.empty
    row = summary.iloc[0]
    assert row["cagr_delta_pct_points"] == 0.44
    assert row["trade_count_delta"] == -6


def test_create_removed_switch_audit():
    benchmark_events = pd.DataFrame(
        {
            "switch_date": ["2020-01-01", "2020-02-01"],
            "from_mode": ["offensive_spy", "defensive_allocator"],
            "to_mode": ["defensive_allocator", "offensive_spy"],
            "spy_distance_from_trend_pct": [-1.0, 2.0],
            "spy_drawdown_pct": [-25.0, -20.0],
            "applied_overlay_slippage_bps": [50.0, 50.0],
            "overlay_slippage_cost_pct": [1.0, 1.0],
        }
    )
    candidate_events = benchmark_events.iloc[[1]].copy()
    effectiveness = benchmark_events.copy()
    effectiveness["transition"] = [
        "offensive_spy_to_defensive_allocator",
        "defensive_allocator_to_offensive_spy",
    ]
    effectiveness["switch_value_added_20d_pct_points"] = [-3.0, 1.0]
    effectiveness["switch_helped_20d"] = [False, True]

    removed = _create_removed_switch_audit(
        benchmark_events=benchmark_events,
        candidate_events=candidate_events,
        benchmark_effectiveness_events=effectiveness,
        horizons=[20],
    )

    assert len(removed) == 1
    assert removed.iloc[0]["switch_date"] == "2020-01-01"
    assert removed.iloc[0]["switch_value_added_20d_pct_points"] == -3.0


def test_summarise_removed_switches():
    removed = pd.DataFrame(
        {
            "applied_overlay_slippage_bps": [50.0, 50.0],
            "spy_drawdown_pct": [-25.0, -30.0],
            "switch_value_added_20d_pct_points": [-3.0, -2.0],
            "switch_helped_20d": [False, False],
        }
    )

    summary = _summarise_removed_switches(
        removed_switches=removed,
        horizons=[20],
    )

    assert summary.iloc[0]["removed_switch_count"] == 2
    assert summary.iloc[0]["avg_removed_value_added_20d_pct_points"] == -2.5
    assert summary.iloc[0]["removed_helped_20d_pct"] == 0.0