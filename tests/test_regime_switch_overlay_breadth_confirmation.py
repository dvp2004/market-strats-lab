import pandas as pd

from market_strats.analysis.regime_switch_overlay_breadth_confirmation import (
    _create_breadth_confirmation_summary,
    _create_risk_asset_breadth_frame,
    _variant_guard_inputs,
)


def _make_ticker_output(prices: list[float]) -> dict:
    dates = pd.bdate_range("2020-01-01", periods=len(prices))

    return {
        "price_data": pd.DataFrame(
            {
                "date": dates,
                "adj_close": prices,
            }
        )
    }


def test_create_risk_asset_breadth_frame():
    ticker_outputs = {
        "SPY": _make_ticker_output([100.0] * 5 + [110.0] * 5),
        "QQQ": _make_ticker_output([100.0] * 5 + [90.0] * 5),
    }

    breadth = _create_risk_asset_breadth_frame(
        ticker_outputs=ticker_outputs,
        risk_assets=["SPY", "QQQ"],
        breadth_sma_days=3,
    )

    assert not breadth.empty
    assert "risk_asset_breadth_pct" in breadth.columns
    assert breadth["risk_asset_count"].iloc[-1] == 2


def test_variant_guard_inputs():
    dates = pd.bdate_range("2020-01-01", periods=5)
    guards = {
        "deep_drawdown_guard": pd.Series([True, True, False, True, True], index=dates),
        "defensive_breadth_condition": pd.Series([True, False, True, True, False], index=dates),
        "offensive_breadth_condition": pd.Series([False, True, True, False, True], index=dates),
    }

    defensive_allowed, offensive_allowed, defensive_name, offensive_name = (
        _variant_guard_inputs(
            variant_name="combined_breadth_confirmation",
            guards=guards,
        )
    )

    assert defensive_allowed.tolist() == [True, False, False, True, False]
    assert offensive_allowed.tolist() == [False, True, True, False, True]
    assert defensive_name == "deep_drawdown_guard_and_defensive_breadth"
    assert offensive_name == "offensive_breadth_confirmation"


def test_create_breadth_confirmation_summary():
    metrics = pd.DataFrame(
        {
            "period": ["full", "full"],
            "variant_name": [
                "phase4_execution_candidate",
                "combined_breadth_confirmation",
            ],
            "cagr_pct": [9.93, 10.10],
            "calmar": [0.412, 0.420],
            "max_drawdown_pct": [-24.12, -24.00],
            "end_value": [66429.13, 68000.0],
            "trade_count": [46, 44],
        }
    )

    summary = _create_breadth_confirmation_summary(
        metrics=metrics,
        benchmark_variant="phase4_execution_candidate",
    )

    assert not summary.empty
    row = summary[
        summary["variant_name"] == "combined_breadth_confirmation"
    ].iloc[0]
    assert row["cagr_delta_vs_benchmark_pct_points"] == 0.17
    assert row["trade_count_delta_vs_benchmark"] == -2