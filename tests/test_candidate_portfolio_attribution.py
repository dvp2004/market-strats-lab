import pandas as pd

from market_strats.analysis.candidate_portfolio_attribution import (
    create_candidate_portfolio_sleeve_attribution,
    create_candidate_portfolio_sleeve_summary,
)


def make_result(
    dates: pd.DatetimeIndex,
    returns: list[float],
    position: float,
) -> pd.DataFrame:
    equity = 10_000 * (1.0 + pd.Series(returns)).cumprod()

    return pd.DataFrame(
        {
            "date": dates,
            "adj_close": equity,
            "strategy_return": returns,
            "equity": equity,
            "position": position,
            "cash_position": 1.0 - position,
            "turnover": [1.0] + [0.0] * (len(dates) - 1),
        }
    )


def test_create_candidate_portfolio_sleeve_attribution_returns_one_row_per_component():
    dates = pd.bdate_range("2020-01-01", periods=5)

    component_a = make_result(dates, [0, 0.01, 0.01, 0.01, 0.01], 1.0)
    component_b = make_result(dates, [0, 0.00, 0.00, 0.00, 0.00], 0.0)

    portfolio_result = pd.DataFrame(
        {
            "date": dates,
            "equity": [10_000, 10_060, 10_120, 10_180, 10_240],
        }
    )

    attribution = create_candidate_portfolio_sleeve_attribution(
        component_results={
            "Component A": component_a,
            "Component B": component_b,
        },
        weights={
            "Component A": 0.60,
            "Component B": 0.40,
        },
        portfolio_result=portfolio_result,
        common_dates=list(dates),
        initial_capital=10_000,
    )

    assert len(attribution) == 2
    assert "contribution_to_portfolio_return_pct_points" in attribution.columns
    assert "final_weight_pct" in attribution.columns


def test_create_candidate_portfolio_sleeve_summary_identifies_contributors():
    attribution = pd.DataFrame(
        {
            "component": ["A", "B"],
            "contribution_to_portfolio_return_pct_points": [10.0, 2.0],
            "weight_drift_pct_points": [5.0, -5.0],
        }
    )
    portfolio_result = pd.DataFrame({"equity": [10_000, 11_200]})

    summary = create_candidate_portfolio_sleeve_summary(
        attribution=attribution,
        portfolio_result=portfolio_result,
        initial_capital=10_000,
    )

    assert len(summary) == 1
    assert summary.iloc[0]["top_contributor"] == "A"
    assert summary.iloc[0]["weakest_contributor"] == "B"
    assert summary.iloc[0]["largest_overweight_component"] == "A"
    assert summary.iloc[0]["largest_underweight_component"] == "B"