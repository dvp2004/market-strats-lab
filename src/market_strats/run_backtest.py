from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.plots import plot_drawdowns, plot_equity_curves
from market_strats.analysis.regimes import calculate_regime_metrics, create_regime_summary
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.data.fetch_yfinance import (
    fetch_daily_prices,
    load_prices_from_parquet,
    save_prices_to_parquet,
)
from market_strats.data.validation import validate_price_data
from market_strats.strategies.absolute_momentum import run_absolute_momentum_strategy
from market_strats.strategies.buy_and_hold import run_buy_and_hold
from market_strats.strategies.daily_sma_trend import run_daily_sma_trend_strategy
from market_strats.strategies.drawdown_tranche import run_drawdown_tranche_strategy
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
    sma_days = int(config["sma_days"])
    momentum_months = int(config["momentum_months"])

    drawdown_base_allocation = float(config["drawdown_base_allocation"])
    drawdown_tranche_allocation = float(config["drawdown_tranche_allocation"])
    drawdown_levels = [float(level) for level in config["drawdown_levels"]]

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

    daily_sma_trend = run_daily_sma_trend_strategy(
        prices=prices,
        initial_capital=initial_capital,
        sma_days=sma_days,
        slippage_bps=slippage_bps,
    )

    absolute_momentum = run_absolute_momentum_strategy(
        prices=prices,
        initial_capital=initial_capital,
        momentum_months=momentum_months,
        slippage_bps=slippage_bps,
    )

    drawdown_tranche = run_drawdown_tranche_strategy(
        prices=prices,
        initial_capital=initial_capital,
        base_allocation=drawdown_base_allocation,
        tranche_allocation=drawdown_tranche_allocation,
        drawdown_levels=drawdown_levels,
        slippage_bps=slippage_bps,
    )

    results = {
        "Buy and Hold": buy_hold,
        f"{sma_months}-Month SMA": sma_trend,
        f"{sma_days}-Day SMA": daily_sma_trend,
        f"{momentum_months}-Month Absolute Momentum": absolute_momentum,
        "Drawdown Tranche": drawdown_tranche,
    }

    metrics = [
        calculate_metrics(buy_hold, "Buy and Hold"),
        calculate_metrics(sma_trend, f"{sma_months}-Month SMA"),
        calculate_metrics(daily_sma_trend, f"{sma_days}-Day SMA"),
        calculate_metrics(
            absolute_momentum,
            f"{momentum_months}-Month Absolute Momentum",
        ),
        calculate_metrics(drawdown_tranche, "Drawdown Tranche"),
    ]

    metrics_df = pd.DataFrame(metrics)
    metrics_path = reports_dir / f"{ticker}_strategy_comparison_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    equity_plot_path = reports_dir / f"{ticker}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"{ticker}_drawdowns.png"

    plot_equity_curves(results, equity_plot_path)
    plot_drawdowns(results, drawdown_plot_path)

    regime_metrics_df = calculate_regime_metrics(results)
    regime_summary_df = create_regime_summary(regime_metrics_df)

    regime_metrics_path = reports_dir / f"{ticker}_regime_metrics.csv"
    regime_summary_path = reports_dir / f"{ticker}_regime_summary.csv"

    regime_metrics_df.to_csv(regime_metrics_path, index=False)
    regime_summary_df.to_csv(regime_summary_path, index=False)

    rolling_metrics_df = calculate_rolling_window_metrics(results)
    rolling_summary_df = create_rolling_summary(rolling_metrics_df)

    rolling_metrics_path = reports_dir / f"{ticker}_rolling_metrics.csv"
    rolling_summary_path = reports_dir / f"{ticker}_rolling_summary.csv"

    rolling_metrics_df.to_csv(rolling_metrics_path, index=False)
    rolling_summary_df.to_csv(rolling_summary_path, index=False)

    print("\nFull-period strategy comparison:")
    print(metrics_df.to_string(index=False))

    print("\nRegime summary:")
    print(regime_summary_df.to_string(index=False))

    print("\nRolling-window summary:")
    print(rolling_summary_df.to_string(index=False))

    print(f"\nSaved full-period metrics to: {metrics_path}")
    print(f"Saved regime metrics to: {regime_metrics_path}")
    print(f"Saved regime summary to: {regime_summary_path}")
    print(f"Saved rolling metrics to: {rolling_metrics_path}")
    print(f"Saved rolling summary to: {rolling_summary_path}")
    print(f"Saved equity curve chart to: {equity_plot_path}")
    print(f"Saved drawdown chart to: {drawdown_plot_path}")


if __name__ == "__main__":
    main()