import pandas as pd

from market_strats.analysis.candidate_portfolio_warmup_audit import (
    create_candidate_portfolio_warmup_audit,
)


def make_result(
    dates: pd.DatetimeIndex,
    positions: list[float],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": dates,
            "position": positions,
            "cash_position": [1.0 - value for value in positions],
        }
    )


def test_warmup_audit_passes_when_component_stays_in_cash_during_warmup():
    dates = pd.bdate_range("2020-01-01", periods=5)

    result = make_result(
        dates=dates,
        positions=[0.0, 0.0, 0.0, 1.0, 1.0],
    )

    audit = create_candidate_portfolio_warmup_audit(
        component_results={"Test Component": result},
        expected_warmup_trading_days={"Test Component": 3},
        common_dates=list(dates),
    )

    assert bool(audit.iloc[0]["active_before_expected_warmup"]) is False
    assert audit.iloc[0]["warmup_status"] == "Pass"


def test_warmup_audit_fails_when_component_is_active_during_warmup():
    dates = pd.bdate_range("2020-01-01", periods=5)

    result = make_result(
        dates=dates,
        positions=[0.0, 1.0, 1.0, 1.0, 1.0],
    )

    audit = create_candidate_portfolio_warmup_audit(
        component_results={"Test Component": result},
        expected_warmup_trading_days={"Test Component": 3},
        common_dates=list(dates),
    )

    assert bool(audit.iloc[0]["active_before_expected_warmup"]) is True
    assert "Fail" in audit.iloc[0]["warmup_status"]