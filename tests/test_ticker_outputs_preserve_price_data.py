import pandas as pd

from market_strats.run_backtest import _preserve_price_data_for_outputs


def test_preserve_price_data_keeps_close_and_adj_close():
    price_data = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-01"]),
            "close": [101.0, 100.0],
            "adj_close": [99.0, 98.0],
        }
    )

    output = _preserve_price_data_for_outputs(price_data)

    assert list(output["date"]) == sorted(output["date"])
    assert "close" in output.columns
    assert "adj_close" in output.columns
    assert output["close"].iloc[0] == 100.0
    assert output["adj_close"].iloc[0] == 98.0


def test_preserve_price_data_falls_back_to_adj_close_when_close_missing():
    price_data = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "adj_close": [98.0, 99.0],
        }
    )

    output = _preserve_price_data_for_outputs(price_data)

    assert "close" in output.columns
    assert "adj_close" in output.columns
    assert output["close"].equals(output["adj_close"])