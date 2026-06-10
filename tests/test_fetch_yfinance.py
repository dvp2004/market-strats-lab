import pandas as pd
import pytest

from market_strats.data.fetch_yfinance import _drop_trailing_incomplete_rows


def _ohlcv_frame(close_values: list[float | None]) -> pd.DataFrame:
    dates = pd.date_range("2026-06-01", periods=len(close_values), freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * len(close_values),
            "high": [101.0] * len(close_values),
            "low": [99.0] * len(close_values),
            "close": close_values,
            "adj_close": close_values,
            "volume": [1000] * len(close_values),
        }
    )


def test_drop_trailing_incomplete_yfinance_rows():
    frame = _ohlcv_frame([100.0, 101.0, None])

    cleaned = _drop_trailing_incomplete_rows(frame, "SPY")

    assert len(cleaned) == 2
    assert cleaned["close"].notna().all()


def test_incomplete_non_trailing_yfinance_row_fails():
    frame = _ohlcv_frame([100.0, None, 102.0])

    with pytest.raises(ValueError, match="incomplete non-trailing"):
        _drop_trailing_incomplete_rows(frame, "SPY")
