# Market Strats Lab

Market Strats Lab is a reproducible Python research project for testing systematic trading strategies honestly.

The current goal is not live trading, prediction, or “magic alpha”. The goal is to build a clean research workflow that can compare strategies against a proper benchmark, expose weak ideas quickly, and avoid misleading backtests.

## Current MVP

The first version compares two strategies on SPY:

1. **Buy and Hold**  
   Buy SPY at the beginning of the test period and hold it until the end.

2. **10-Month SMA Trend Strategy**  
   Hold SPY when its adjusted close is above its 10-month simple moving average. Move to cash when it is below the 10-month SMA.

The output includes performance metrics, equity curves, and drawdown charts.

## Why This Project Exists

Most trading strategy ideas sound better than they actually are. This project is designed to test them with discipline.

The system is built around a few principles:

- compare every strategy against buy-and-hold;
- avoid lookahead bias;
- include slippage assumptions;
- measure drawdown, not just return;
- keep strategy logic separate from data loading and reporting;
- make every test repeatable;
- add complexity only after the simple version works.

## Current Assumptions

This MVP uses deliberately simple assumptions:

- daily SPY data from Yahoo Finance via `yfinance`;
- adjusted close prices;
- no leverage;
- no shorting;
- no options;
- no margin;
- no tax modelling;
- cash earns 0% for now;
- slippage is modelled in basis points;
- trades are simulated, not live;
- this is research code, not financial advice.

These assumptions will be improved later.

## Project Structure

```text
market-strats-lab/
  configs/
    spy_sma10.yaml

  data/
    raw/
    processed/

  reports/

  experiments/

  src/
    market_strats/
      data/
        fetch_yfinance.py
        validation.py

      strategies/
        buy_and_hold.py
        sma_trend.py

      analysis/
        metrics.py
        plots.py

      run_backtest.py

  tests/
    test_metrics.py

  README.md
  pyproject.toml
  .gitignore