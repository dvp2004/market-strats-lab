import pandas as pd

from market_strats.analysis.annual_rebalance_audit import (
    create_annual_rebalance_audit,
    create_annual_rebalance_audit_summary,
)


def make_rebalanced_result() -> pd.DataFrame:
    dates = pd.bdate_range("2020-12-28", "2021-01-08")

    return pd.DataFrame(
        {
            "date": dates,
            "equity": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "is_rebalance_day": [
                False,
                False,
                False,
                True,
                False,
                False,
                False,
                False,
                False,
                False,
            ],
            "rebalance_turnover": [0.0, 0.0, 0.0, 0.10, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "total_equity_before_rebalance": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "core_sleeve_equity_before_rebalance": [60, 61, 62, 55, 62, 63, 64, 65, 66, 67],
            "satellite_sleeve_equity_before_rebalance": [40, 40, 40, 48, 42, 42, 42, 42, 42, 42],
            "core_weight_before_rebalance": [0.60, 0.60, 0.61, 0.53, 0.60, 0.60, 0.60, 0.60, 0.60, 0.60],
            "satellite_weight_before_rebalance": [0.40, 0.40, 0.39, 0.47, 0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            "current_core_weight": [0.60] * 10,
            "current_satellite_weight": [0.40] * 10,
            "core_initial_weight": [0.60] * 10,
            "satellite_initial_weight": [0.40] * 10,
            "position": [0.80] * 10,
            "cash_position": [0.20] * 10,
        }
    )


def test_create_annual_rebalance_audit_extracts_rebalance_events():
    result = make_rebalanced_result()

    audit = create_annual_rebalance_audit(
        result=result,
        strategy_name="Annual Rebalanced Test",
    )

    assert len(audit) == 1
    assert audit.iloc[0]["rebalance_turnover_pct"] == 10.0
    assert audit.iloc[0]["core_weight_drift_pct_points"] == -7.0


def test_create_annual_rebalance_audit_summary_summarises_events():
    result = make_rebalanced_result()
    audit = create_annual_rebalance_audit(
        result=result,
        strategy_name="Annual Rebalanced Test",
    )

    summary = create_annual_rebalance_audit_summary(audit)

    assert len(summary) == 1
    assert summary.iloc[0]["rebalance_count"] == 1
    assert summary.iloc[0]["max_rebalance_turnover_pct"] == 10.0