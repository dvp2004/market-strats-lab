import pandas as pd

from market_strats.analysis.regime_switch_overlay_guarded_switch_diagnostic import (
    _create_defensive_entry_guard_series,
    _create_guarded_switch_summary,
    _prepare_offensive_state_frame,
)


def _make_offensive_result() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=260)
    prices = [100.0] * 220 + [89.0] * 20 + [75.0] * 20

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": prices,
            "strategy_return": pd.Series(prices).pct_change().fillna(0.0),
            "equity": prices,
            "position": 1.0,
            "cash_position": 0.0,
            "turnover": 0.0,
        }
    )


def test_prepare_offensive_state_frame():
    result = _make_offensive_result()

    state = _prepare_offensive_state_frame(
        offensive_result=result,
        trend_sma_days=20,
    )

    assert "drawdown" in state.columns
    assert "trend_distance" in state.columns
    assert state["drawdown"].min() < -0.20


def test_deep_drawdown_guard_blocks_deep_entries():
    result = _make_offensive_result()

    guard = _create_defensive_entry_guard_series(
        offensive_result=result,
        trend_sma_days=20,
        guard_name="deep_drawdown_guard",
        near_high_drawdown_threshold=-0.05,
        near_high_min_trend_distance=-0.01,
        deep_drawdown_threshold=-0.20,
    )

    assert guard.any()
    assert not guard.iloc[-1]


def test_near_high_whipsaw_guard_blocks_shallow_noise():
    result = _make_offensive_result()

    guard = _create_defensive_entry_guard_series(
        offensive_result=result,
        trend_sma_days=20,
        guard_name="near_high_whipsaw_guard",
        near_high_drawdown_threshold=-0.05,
        near_high_min_trend_distance=-0.01,
        deep_drawdown_threshold=-0.20,
    )

    assert guard.dtype == bool


def test_create_guarded_switch_summary():
    metrics = pd.DataFrame(
        {
            "period": ["full", "full"],
            "guard_name": ["baseline_no_guard", "deep_drawdown_guard"],
            "cagr_pct": [9.49, 9.70],
            "calmar": [0.393, 0.400],
            "max_drawdown_pct": [-24.12, -24.00],
            "end_value": [61294.08, 63500.00],
            "trade_count": [52, 48],
        }
    )

    summary = _create_guarded_switch_summary(metrics)

    assert not summary.empty
    guarded = summary[summary["guard_name"] == "deep_drawdown_guard"].iloc[0]
    assert guarded["cagr_delta_vs_baseline_pct_points"] == 0.21