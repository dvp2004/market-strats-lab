import pandas as pd

from market_strats.analysis.asset_expansion_diagnostic import (
    _apply_constraints,
    _build_close_panel,
    _create_decision_rows,
)


def _make_ticker_output(ticker: str, dates: pd.DatetimeIndex) -> dict:
    prices = pd.DataFrame(
        {
            "date": dates,
            "adj_close": [100.0 + index for index in range(len(dates))],
            "close": [100.0 + index for index in range(len(dates))],
        }
    )

    return {
        "price_data": prices,
        "data": prices,
        "strategy_results": {},
    }


def test_apply_constraints_caps_group_weight():
    selected_assets = ["GLD", "SLV", "USO"]
    weights = _apply_constraints(
        selected_assets=selected_assets,
        max_asset_weight=1 / 3,
        group_caps={"precious_metals": 0.5, "commodities": 0.5},
        asset_groups={
            "GLD": "precious_metals",
            "SLV": "precious_metals",
            "USO": "commodities",
        },
    )

    assert round(float(weights.loc[["GLD", "SLV"]].sum()), 6) == 0.5
    assert round(float(weights.loc["USO"]), 6) == round(1 / 3, 6)


def test_build_close_panel_inner_joins_dates():
    dates_a = pd.bdate_range("2020-01-01", periods=5)
    dates_b = pd.bdate_range("2020-01-03", periods=5)

    ticker_outputs = {
        "AAA": _make_ticker_output("AAA", dates_a),
        "BBB": _make_ticker_output("BBB", dates_b),
    }

    panel = _build_close_panel(ticker_outputs, ["AAA", "BBB"])

    assert not panel.empty
    assert list(panel.columns) == ["AAA", "BBB"]
    assert panel.index.min() == pd.Timestamp("2020-01-03")

def test_create_decision_rows_judges_overlay_not_only_allocator():
    metrics = pd.DataFrame(
        {
            "period": [
                "full",
                "full",
                "full",
                "full",
                "reference",
                "reference",
                "holdout",
                "holdout",
            ],
            "strategy": [
                "Base Allocator",
                "Base + Oil Allocator",
                "Base 3D Overlay",
                "Base + Oil 3D Overlay",
                "Base 3D Overlay",
                "Base + Oil 3D Overlay",
                "Base 3D Overlay",
                "Base + Oil 3D Overlay",
            ],
            "cagr_pct": [8.0, 9.0, 10.0, 10.7, 7.0, 8.3, 12.9, 12.94],
            "calmar": [0.29, 0.38, 0.34, 0.40, 0.24, 0.35, 0.49, 0.494],
            "max_drawdown_pct": [-28.0, -24.0, -29.0, -26.0, -30.0, -24.0, -24.0, -24.0],
            "volatility_pct": [14.0, 14.5, 14.4, 14.6, 15.0, 15.0, 13.8, 14.2],
        }
    )

    allocation_summary = pd.DataFrame(
        {
            "universe": ["Base + Oil"],
            "asset": ["USO"],
            "avg_weight_pct": [2.6],
            "days_held": [474],
            "pct_days_held": [9.4],
            "final_weight_pct": [33.333],
        }
    )

    decision = _create_decision_rows(
        metrics=metrics,
        allocation_summary=allocation_summary,
        baseline_universe_name="Base",
        expanded_universe_name="Base + Oil",
    )

    assert not decision.empty

    row = decision.iloc[0]

    assert row["allocator_pass"]
    assert row["overlay_full_pass"]
    assert not row["overlay_holdout_material_pass"]
    assert row["final_classification"] == "Promising but not validated"