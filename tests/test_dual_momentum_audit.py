import pandas as pd

from market_strats.analysis.dual_momentum_audit import (
    create_allocation_audit,
    create_cash_reason_summary,
    create_holding_segments,
)


def make_dual_result() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=8)

    return pd.DataFrame(
        {
            "date": dates,
            "selected_asset": [
                "CASH",
                "CASH",
                "SPY",
                "SPY",
                "TLT",
                "TLT",
                "SPY",
                "SPY",
            ],
            "cash_reason": [
                "INSUFFICIENT_HISTORY",
                "INSUFFICIENT_HISTORY",
                "INVESTED",
                "INVESTED",
                "INVESTED",
                "INVESTED",
                "INVESTED",
                "INVESTED",
            ],
            "strategy_return": [
                0.0,
                0.001,
                0.01,
                -0.01,
                -0.02,
                0.01,
                0.03,
                0.01,
            ],
            "equity": [
                10_000,
                10_010,
                10_110,
                10_009,
                9_809,
                9_907,
                10_204,
                10_306,
            ],
        }
    )


def test_create_holding_segments_groups_continuous_selected_assets():
    result = make_dual_result()

    segments = create_holding_segments(result, pair_name="TestPair")

    assert len(segments) == 4
    assert list(segments["selected_asset"]) == ["CASH", "SPY", "TLT", "SPY"]
    assert segments.iloc[0]["trading_days_held"] == 2


def test_create_allocation_audit_summarises_time_held():
    result = make_dual_result()

    audit = create_allocation_audit(result, pair_name="TestPair")

    spy = audit[audit["selected_asset"] == "SPY"].iloc[0]
    cash = audit[audit["selected_asset"] == "CASH"].iloc[0]

    assert spy["days_held"] == 4
    assert spy["switch_count"] == 2
    assert cash["days_held"] == 2


def test_create_cash_reason_summary_counts_cash_reasons():
    result = make_dual_result()

    summary = create_cash_reason_summary(result, pair_name="TestPair")

    assert len(summary) == 1
    assert summary.iloc[0]["cash_reason"] == "INSUFFICIENT_HISTORY"
    assert summary.iloc[0]["days_held"] == 2

def test_create_holding_segments_uses_equity_to_calculate_segment_return():
    result = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=3),
            "selected_asset": ["SPY", "SPY", "SPY"],
            "cash_reason": ["INVESTED", "INVESTED", "INVESTED"],
            "strategy_return": [0.0, -0.50, 2.00],
            "equity": [100.0, 110.0, 121.0],
        }
    )

    segments = create_holding_segments(result, pair_name="TestPair")

    assert len(segments) == 1
    assert segments.iloc[0]["segment_return_pct"] == 21.0