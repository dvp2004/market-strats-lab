import pandas as pd
import pytest

from market_strats.run_backtest import _apply_research_period_filter


def test_apply_research_period_filter_truncates_after_end_date():
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-04-30", "2026-05-01", "2026-05-13"]
            ),
            "adj_close": [100.0, 101.0, 102.0],
            "close": [100.0, 101.0, 102.0],
        }
    )

    config = {
        "research_period": {
            "end_date": "2026-05-01",
        }
    }

    filtered = _apply_research_period_filter(
        prices=prices,
        config=config,
        ticker="SPY",
    )

    assert filtered["date"].max() == pd.Timestamp("2026-05-01")
    assert len(filtered) == 2


def test_apply_research_period_filter_raises_when_empty():
    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-13"]),
            "adj_close": [102.0],
            "close": [102.0],
        }
    )

    config = {
        "research_period": {
            "end_date": "2026-05-01",
        }
    }

    with pytest.raises(ValueError, match="no price data"):
        _apply_research_period_filter(
            prices=prices,
            config=config,
            ticker="TEST",
        )