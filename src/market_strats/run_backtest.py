from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.plots import plot_drawdowns, plot_equity_curves
from market_strats.data.fetch_yfinance import (
    fetch_daily_prices,
    load_prices_from_parquet,
    save_prices_to_parquet,
)
from market_strats.data.validation import validate_price_data
from market_strats.strategies.absolute_momentum import run_absolute_momentum_strategy
from market_strats.strategies.buy_and_hold import run_buy_and_hold
from market_strats.strategies.sma_trend import run_sma_trend_strategy


def load_config(config_path: str | Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def get_or_fetch_prices(config: dict) -> pd.DataFrame:
    ticker = config["ticker"].upper()
    processed_dir = Path("data/processed")
    price_path = processed_dir / f"{ticker}.parquet"

    if price_path.exists():
        print(f"Loading existing data from {price_path}")
        prices = load_prices_from_parquet(ticker, processed_dir)
    else:
        print(f"Fetching {ticker} data from yfinance")
        prices = fetch_daily_prices(
            ticker=ticker,
            start_date=config["start_date"],
            end_date=config.get("end_date"),
        )
        save_path = save_prices_to_parquet(prices, ticker, processed_dir)
        print(f"Saved data to {save_path}")

    validate_price_data(prices, ticker)

    return prices


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    config = load_config(args.config)

    ticker = config["ticker"].upper()
    initial_capital = float(config["initial_capital"])
    sma_months = int(config["sma_months"])
    momentum_months = int(config["momentum_months"])
    slippage_bps = float(config["slippage_bps"])

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    prices = get_or_fetch_prices(config)

    buy_hold = run_buy_and_hold(prices, initial_capital)

    sma_trend = run_sma_trend_strategy(
        prices=prices,
        initial_capital=initial_capital,
        sma_months=sma_months,
        slippage_bps=slippage_bps,
    )

    absolute_momentum = run_absolute_momentum_strategy(
        prices=prices,
        initial_capital=initial_capital,
        momentum_months=momentum_months,
        slippage_bps=slippage_bps,
    )

    results = {
        "Buy and Hold": buy_hold,
        f"{sma_months}-Month SMA": sma_trend,
        f"{momentum_months}-Month Absolute Momentum": absolute_momentum,
    }

    metrics = [
        calculate_metrics(buy_hold, "Buy and Hold"),
        calculate_metrics(sma_trend, f"{sma_months}-Month SMA"),
        calculate_metrics(
            absolute_momentum,
            f"{momentum_months}-Month Absolute Momentum",
        ),
    ]

    metrics_df = pd.DataFrame(metrics)
    metrics_path = reports_dir / f"{ticker}_strategy_comparison_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    equity_plot_path = reports_dir / f"{ticker}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"{ticker}_drawdowns.png"

    plot_equity_curves(results, equity_plot_path)
    plot_drawdowns(results, drawdown_plot_path)

    print("\nStrategy comparison:")
    print(metrics_df.to_string(index=False))

    print(f"\nSaved metrics to: {metrics_path}")
    print(f"Saved equity curve chart to: {equity_plot_path}")
    print(f"Saved drawdown chart to: {drawdown_plot_path}")


if __name__ == "__main__":
    main()