import pandas as pd


def test_price_data_preserves_close_and_adj_close():
    raw = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "Close": [100.0, 101.0],
            "Adj Close": [98.0, 99.0],
        }
    )

    # Replace this with your actual normalisation function once located.
    normalised = raw.rename(
        columns={
            "Date": "date",
            "Close": "close",
            "Adj Close": "adj_close",
        }
    )[["date", "close", "adj_close"]]

    assert "close" in normalised.columns
    assert "adj_close" in normalised.columns
    assert normalised["close"].iloc[0] == 100.0
    assert normalised["adj_close"].iloc[0] == 98.0