# Market Strats Lab

A reproducible systematic trading research lab for testing long-term market strategies honestly.

This project is **not** built to find a magic trading rule. It is built to test whether simple, explainable, systematic strategies can improve the **return / drawdown / liveability** trade-off versus buy-and-hold across major markets.

> A strategy is only useful if it survives honest testing, avoids obvious backtest traps, and gives a trade-off an actual investor could plausibly stick with.

---

## ⚠️ Important Disclaimer

This project is for **research and education only**.

It is not financial advice, investment advice, or a recommendation to buy or sell any asset. Historical backtests can be misleading — especially when many strategies, assets, and parameters are tested. Real-world results can differ because of data quality, taxes, execution costs, slippage, behavioural errors, liquidity, regime changes, and future market conditions.

**Current status: research-grade framework. Not a production-ready trading system. Not ready for real-money deployment.**

---

## Project Status

The framework currently supports:

- Multi-asset strategy backtesting
- Buy-and-hold benchmarks
- Trend-following strategies (SMA-based, daily and monthly)
- Absolute momentum strategies
- Drawdown-tranche dip-buying tests
- Dual momentum rotation tests
- Core-satellite portfolio structures
- Annual rebalance audits
- Cross-asset diagnostics and expanded universe testing
- Rolling-window analysis (3-year and 5-year)
- Regime analysis
- Cash-yield modelling via T-bill proxy
- Calendar-aware annualisation (including 24/7 assets like BTC)
- Strategy-purpose classification
- Markdown / CSV / chart report generation
- Unit tests and linting (pytest + ruff)

---

## Research Question

> Can simple systematic rules improve long-term outcomes versus buy-and-hold without destroying compounding?

Strategies are evaluated on:

| Metric | Why It Matters |
|---|---|
| Terminal wealth / CAGR | Raw compounding power |
| Max drawdown | Worst-case investor pain |
| Volatility | Path smoothness |
| Sharpe / Sortino | Risk-adjusted efficiency |
| Worst 3Y / 5Y CAGR | Bad-window survivability |
| Exposure time | How often the strategy is invested |
| Trade count / turnover | Friction and tax efficiency |
| Time underwater | Duration of loss periods |
| Regime performance | How it behaves in different market environments |
| Strategy-purpose classification | Wealth-builder vs risk-control vs compromise |

The goal is not only to ask "did it make more money?" but also "was the path liveable?"

---

## Tested Market Universe

| Ticker | Market / Asset Class | Role in Research |
|---|---|---|
| `SPY` | US large-cap equities / S&P 500 | Main benchmark and core compounding engine |
| `QQQ` | Nasdaq-100 / US growth equities | High-beta equity crash-protection test |
| `IWM` | US small caps | Small-cap trend behaviour test |
| `EFA` | Developed ex-US equities | International developed equity test |
| `EEM` | Emerging markets | Higher-volatility international equity test |
| `GLD` | Gold | Non-equity crisis / real-rate-sensitive asset |
| `TLT` | Long-duration US Treasuries | Duration-heavy bond / defensive asset |
| `AGG` | Aggregate US bonds | Broad defensive bond sleeve |
| `VNQ` | US REITs | Real-estate equity / credit-sensitive asset |
| `BTC-USD` | Bitcoin | Quarantined — separate high-volatility crypto branch |

Bitcoin is deliberately treated as a **separate/quarantined research branch** because its history is short, extreme, and not directly comparable with mature ETF markets.

---

## Strategies Implemented

### 1. Buy and Hold

The passive benchmark. Buy at inception and hold.

**SPY result (1993-01-29 to 2026-05-01, $10,000 initial capital):**

| Metric | Value |
|---|---|
| End Value | $298,092 |
| CAGR | 10.75% |
| Max Drawdown | -55.19% |
| Worst 3Y CAGR | -16.29% |
| Worst 5Y CAGR | -6.86% |

Buy-and-hold remains extremely hard to beat on raw compounding.

---

### 2. Monthly SMA Trend Strategy

```
At month-end:
  if adjusted close > N-month SMA → hold asset
  else → hold cash
Execute on the next trading day.
```

Baseline uses **10-month SMA**.

**SPY result:**

| Metric | Value |
|---|---|
| End Value | $196,512 |
| CAGR | 9.37% |
| Max Drawdown | -26.28% |
| Trade Count | 47 |

The 10-month SMA reduces drawdown but gives up too much compounding versus buy-and-hold and 12-month absolute momentum.

---

### 3. Daily SMA Trend Strategy

```
Daily:
  if adjusted close > N-day SMA → hold asset
  else → hold cash
Execute on the next trading day.
```

Baseline uses **200-day SMA**.

**SPY result:**

| Metric | Value |
|---|---|
| CAGR | 8.82% |
| Max Drawdown | -22.88% |
| Trade Count | 215 |

For SPY, the 200-day SMA controls drawdown but is too noisy and trade-heavy.

**Notable non-SPY result on EFA:**

| Strategy | CAGR | Max Drawdown |
|---|---|---|
| EFA Buy and Hold | 6.38% | -61.04% |
| EFA 200-Day SMA | 7.63% | -26.31% |

The EFA 200-day SMA result beat buy-and-hold on both CAGR and drawdown. This is promising but **not yet validated** — it needs a neighbouring-window robustness test before being treated as a real discovery.

---

### 4. 12-Month Absolute Momentum

```
At month-end:
  calculate trailing 12-month return
  if return > cash hurdle (T-bill rate) → hold asset
  else → hold cash
Execute on the next trading day.
```

**SPY result:**

| Metric | Value |
|---|---|
| End Value | $299,943 |
| CAGR | 10.77% |
| Max Drawdown | -33.72% |
| Worst 3Y CAGR | -2.27% |
| Worst 5Y CAGR | -0.19% |
| Trade Count | 17 |
| Exposure Time | 79.49% |

This is currently the cleanest overall SPY result. The CAGR edge over buy-and-hold is tiny — the real result is:

> SPY 12-month absolute momentum produced buy-and-hold-like wealth with materially lower drawdown and much better bad-window behaviour.

---

### 5. Drawdown Tranche

```
Hold a base allocation.
Add additional exposure tranches when the asset falls from its high:
  -10% drawdown → add first tranche
  -20% drawdown → add second tranche
  -30% drawdown → add third tranche
```

This strategy formally tested the "buy more when it drops" idea.

**SPY result:**

| Metric | Value |
|---|---|
| CAGR | 8.92% |
| Max Drawdown | -50.45% |

**Failed as a standalone strategy.** It produced cash drag in strong markets and did not reduce drawdown enough during genuine bear markets. Averaging into weakness without knowing whether it is a dip or a bear market is the core flaw.

---

### 6. Trend-Filtered Drawdown

Drawdown tranches, but only deployed when a momentum filter is positive.

**SPY result:**

| Metric | Value |
|---|---|
| CAGR | 8.93% |
| Max Drawdown | -28.28% |
| Exposure Time | 58.01% |

Improved safety versus raw drawdown tranche, but became too underinvested to compound well.

---

### 7. Dual Momentum

```
At month-end:
  compare 12-month returns of two assets
  select the stronger asset
  if selected asset also beats cash (absolute filter) → hold it
  else → hold cash
Execute on the next trading day.
```

Tested on two first-principles pairs.

**SPY / EFA (common period: 2001-08-27 to 2026-05-01):**

| Strategy | CAGR | Max Drawdown |
|---|---|---|
| Buy & Hold SPY | 9.57% | -55.19% |
| Dual Momentum SPY/EFA | 8.56% | -33.72% |

Risk-control win, not a wealth win. Reduced drawdown but did not beat SPY compounding.

**SPY / TLT (common period: 2002-07-30 to 2026-05-01):**

| Strategy | CAGR | Max Drawdown |
|---|---|---|
| Buy & Hold SPY | 11.12% | -55.19% |
| Dual Momentum SPY/TLT | 6.55% | -32.62% |

Too much return sacrifice. TLT was not a strong enough rotation asset over the tested period, particularly given the 2022 rate shock.

**Allocation audits showed** that binary rotation often missed major SPY recoveries because it was fully away from the main compounding engine when markets bounced.

---

### 8. Core-Satellite Strategies

Motivated by the failure mode of binary rotation. Keeps a permanent SPY core to preserve compounding while using a tactical satellite to reduce left-tail exposure.

**Current tested allocation: 60% SPY buy-and-hold core / 40% SPY 12-month momentum satellite.**

No allocation sweep has been run. The 60/40 split was selected by principle, not optimisation.

#### 8.1 Independent 60/40 Core-Satellite

Each sleeve operates independently. No capital transfers between core and satellite after inception.

**SPY result:**

| Metric | Value |
|---|---|
| End Value | $298,833 |
| CAGR | 10.76% |
| Max Drawdown | -34.29% |
| Worst 3Y CAGR | -10.44% |
| Worst 5Y CAGR | -0.74% |
| Exposure Time | 90.71% |
| Trade Count | 18 |

Best behavioural compromise. Preserves more SPY participation than full momentum while reducing drawdown materially versus buy-and-hold. Does not beat full 12-month momentum.

#### 8.2 Annual Rebalanced 60/40 Core-Satellite

Same structure, but rebalanced back to 60/40 at each calendar year-end.

**SPY result:**

| Metric | Value |
|---|---|
| End Value | $312,588 |
| CAGR | 10.91% |
| Max Drawdown | -38.70% |
| Worst 3Y CAGR | -10.61% |
| Worst 5Y CAGR | -1.58% |
| Exposure Time | 91.56% |
| Trade Count | 51 |

Highest terminal-wealth SPY architecture tested so far, but worsened drawdown versus independent sleeves and full 12-month momentum. This is **momentum plus mean-reversion rebalancing**, not pure momentum.

---

### Full SPY Strategy Comparison

| Strategy | End Value | CAGR | Max Drawdown | Worst 3Y CAGR | Worst 5Y CAGR |
|---|---|---|---|---|---|
| Buy and Hold | $298,092 | 10.75% | -55.19% | -16.29% | -6.86% |
| 12M Absolute Momentum | $299,943 | 10.77% | -33.72% | -2.27% | -0.19% |
| 60/40 Independent Core-Satellite | $298,833 | 10.76% | -34.29% | -10.44% | -0.74% |
| 60/40 Annual Rebalanced Core-Satellite | $312,588 | 10.91% | -38.70% | -10.61% | -1.58% |

**Current SPY hierarchy:**

| Rank | Role | Strategy |
|---|---|---|
| 1 | Best defensive / risk-adjusted | SPY 12M Absolute Momentum |
| 2 | Highest terminal wealth | 60/40 Annual Rebalanced Core-Satellite |
| 3 | Best behavioural compromise | 60/40 Independent Core-Satellite |
| 4 | Passive benchmark | SPY Buy and Hold |

---

## Annual Rebalance Audit

The annual rebalance audit was added to understand why the rebalanced core-satellite achieved the highest terminal wealth.

**Summary:**

| Metric | Value |
|---|---|
| Rebalance Count | 33 |
| Average Rebalance Turnover | 2.68% |
| Maximum Rebalance Turnover | 20.87% |
| Average Drawdown at Rebalance | -5.88% |
| Worst Drawdown at Rebalance | -28.58% |
| Average Next 3M Return | 2.01% |
| Average Next 6M Return | 5.38% |
| Average Next 12M Return | 12.00% |

**Key rebalance events:**

| Date | Drawdown at Rebalance | Turnover | Next 12M Return | Interpretation |
|---|---|---|---|---|
| 2001-12-31 | -18.55% | 7.68% | -12.32% | Bad forced re-risking |
| 2002-12-31 | -28.58% | 12.69% | +22.69% | Successful re-risking |
| 2008-12-31 | -28.14% | 20.87% | +18.80% | Major successful re-risking |
| 2022-12-30 | -16.20% | 3.51% | +20.97% | Successful re-risking |

Annual rebalancing improved terminal wealth by forcing money back into SPY after drawdowns — but that same mechanism also increased downside exposure.

---

## Expanded Universe Diagnostic

The expanded universe test proved that **one rule does not fit all markets**.

| Ticker | B&H CAGR | 12M Mom CAGR | CAGR Delta | B&H Max DD | 12M Max DD | DD Improvement | Interpretation |
|---|---|---|---|---|---|---|---|
| SPY | 10.75% | 10.77% | +0.02 | -55.19% | -33.72% | +21.47 pts | Strongest main candidate |
| QQQ | 10.66% | 10.30% | -0.36 | -82.96% | -40.97% | +41.99 pts | Crash-protection candidate |
| IWM | 8.60% | 6.12% | -2.48 | -58.64% | -35.34% | +23.30 pts | Risk-control only |
| EFA | 6.38% | 4.75% | -1.63 | -61.04% | -42.29% | +18.75 pts | 12M weak; 200D SMA promising but unvalidated |
| EEM | 9.92% | 7.23% | -2.69 | -66.43% | -40.46% | +25.97 pts | Risk-control only |
| GLD | 11.09% | 9.08% | -2.01 | -45.56% | -34.75% | +10.81 pts | Risk-control only |
| TLT | 3.70% | 2.88% | -0.82 | -48.35% | -26.59% | +21.76 pts | Risk-control only |
| AGG | 3.09% | 3.18% | +0.09 | -18.43% | -12.84% | +5.59 pts | Defensive candidate |
| VNQ | 7.59% | 4.64% | -2.95 | -73.07% | -46.29% | +26.78 pts | Risk-control only |
| BTC-USD | 56.06% | 56.30% | +0.24 | -83.40% | -80.77% | +2.63 pts | Quarantined |

---

## Strategy-Purpose Classification

The original composite scorecard could over-rank low-CAGR defensive strategies. The framework now classifies strategies by purpose.

| Classification | Meaning |
|---|---|
| **Wealth-builder candidate** | Preserves or improves buy-and-hold-like CAGR while improving drawdown |
| **Risk-control candidate** | Passes the wealth hurdle and improves risk, but does not clearly beat buy-and-hold CAGR |
| **Risk-control only** | Improves drawdown but sacrifices too much CAGR |
| **Behavioural compromise** | Useful for liveability even if not mathematically best |
| **Benchmark** | Passive buy-and-hold reference |
| **Rejected / weak** | Does not justify itself versus buy-and-hold |
| **Quarantined / separate branch** | Not comparable to the main ETF universe |

**Current classifications:**

| Asset | Strategy | Classification |
|---|---|---|
| SPY | 12M Absolute Momentum | Wealth-builder candidate |
| SPY | 60/40 Core-Satellite | Behavioural compromise |
| AGG | 12M Absolute Momentum | Wealth-builder candidate |
| EFA | 200D SMA | Wealth-builder candidate — **unvalidated, needs robustness test** |
| EFA | 10M SMA | Wealth-builder candidate — **unvalidated** |
| QQQ | 12M Absolute Momentum | Risk-control candidate |
| IWM | 12M Absolute Momentum | Risk-control only |
| EEM | 12M Absolute Momentum | Risk-control only |
| VNQ | 12M Absolute Momentum | Risk-control only |
| GLD | 12M Absolute Momentum | Risk-control only |
| BTC-USD | All strategies | Quarantined |

---

## Key Research Findings

### 1. SPY 12M Absolute Momentum is the Cleanest Current Leader

Buy-and-hold-like terminal wealth with much lower drawdown and better bad-window behaviour. Only 17 trades over 33 years.

### 2. The SPY 12M Result is Lower-Risk Replication, Not Alpha

The CAGR edge over buy-and-hold is 2 basis points — statistically indistinguishable from zero. The real result is:

- Similar terminal wealth
- Max drawdown cut by 21.47 percentage points
- Worst 3-year CAGR improved from -16.29% to -2.27%
- Worst 5-year CAGR improved from -6.86% to -0.19%

### 3. Drawdown Tranche Failed

The "buy more when it drops" idea, formalised as scalable percentage tranches, did not work well enough. Cash drag in bull markets plus inadequate protection in bear markets is a losing combination.

### 4. Binary Rotation is Too Blunt

Dual momentum reduced drawdown but opportunity-cost audits showed that being fully away from SPY during recoveries created large missed-return gaps.

### 5. Core-Satellite Helps Behaviourally

The independent 60/40 core-satellite preserved most compounding while reducing drawdown. Not mathematically superior to full momentum, but may be easier to stick with.

### 6. Annual Rebalanced Core-Satellite Improved Terminal Wealth — at a Cost

Highest SPY terminal wealth tested ($312,588), achieved through forced re-risking after drawdowns. But it worsened drawdown and rolling bad-window outcomes versus independent sleeves.

### 7. One Rule Does Not Fit All Markets

12M momentum is not universal. It works best for SPY, is useful for QQQ crash protection, looks clean for AGG, but damages compounding in IWM, EEM, VNQ, GLD, and EFA.

### 8. EFA 200D SMA is Promising but Unvalidated

Beat buy-and-hold on both CAGR and drawdown. But this emerged from a broad 60-combination strategy suite, so it requires neighbouring-window robustness testing before being treated as a real discovery.

### 9. Bitcoin is Quarantined

Interesting results, but short history, extreme cycles, 24/7 trading, and selection bias keep it out of the main conclusions.

---

## Current Research Roadmap

### Immediate: EFA SMA Robustness

Test SMA windows across 100D, 150D, 200D, 250D, and 300D on EFA.

**Pass condition:** Neighbouring windows perform similarly — the result is a plateau, not a spike.  
**Fail condition:** 200D is uniquely strong and nearby windows collapse — discard as noise.

### Later Branches

- Multi-asset candidate portfolio combining validated components (SPY 12M, validated EFA SMA, AGG 12M)
- Rebalance-month sensitivity on annual core-satellite (June / September year-end vs December)
- BTC-specific trend-following diagnostic
- Cash proxy sensitivity (0% vs T-bill vs investable ETF like SGOV/BIL)
- Lookahead-bias audit test suite
- Out-of-sample / walk-forward validation

---

## Methodology Notes

### Lookahead Bias Controls

- Signals are generated using only data available at the signal date
- Execution occurs on the next trading day
- Positions are applied after execution, not on the signal day
- This should still be audited with a dedicated test suite before any real-money interpretation

### Cash Returns

Cash is modelled using a T-bill proxy (`^IRX`, 13-week T-bill rate). This matters because assuming 0% cash return unfairly penalises strategies that exit equities. The cash yield is applied using the actual date frequency of each asset.

### Calendar-Aware Annualisation

The framework infers periods per year from actual data frequency. ETFs trade on US business days (~252/year); BTC trades every calendar day (365/year). Using a single annualisation factor across both would produce incorrect volatility, Sharpe, and cash-period returns for BTC.

### Adjusted Close Data

Data uses adjusted close prices from `yfinance`, which reflect actual ETF returns inclusive of dividends and splits via backward price adjustment. ETF expense ratios are implicitly embedded in the price series. Note: adjusted close prices are computed retroactively, meaning historical prices differ from what was observable in real-time — a known limitation documented here.

### Slippage

A flat 5 basis points slippage is applied per trade. Bid-ask spreads during market stress periods are likely wider than this, particularly for high-turnover strategies. This understates true trading costs during the periods when timing strategies are most active.

### Cached Data

Price data is cached in `data/processed/`. The cash-rate loader includes schema normalisation so older cached parquet files remain compatible after refactors.

---

## Known Limitations

This project is **not** production-ready. Remaining concerns include:

- `yfinance` data reliability and adjusted close retroactive adjustment
- No cross-validation against a second data source
- Survivorship and selection bias in asset universe
- BTC selection bias (we know it survived)
- No tax modelling
- No bid-ask spread modelling during stress periods
- No FX cost modelling for non-USD investors
- Cash proxy overstates retail-accessible yields by ~10–30 bps
- IRX discount rate vs yield conversion not yet explicitly confirmed in code
- No statistical significance testing on strategy comparisons (no bootstrap CIs, no Jobson-Korkie)
- No multiple-comparisons correction across 60+ strategy-asset combinations
- Rebalance-month sensitivity not yet tested for annual core-satellite
- EFA 200D SMA result not yet validated with window robustness
- No dedicated lookahead-bias audit test suite
- No walk-forward or out-of-sample validation
- Parameter-selection risk despite avoiding obvious optimisation
- Regime dependence — past crisis/recovery structures may not repeat

**Bugs caught and fixed during development:**

- Package import setup issue
- pandas month-end resampling behaviour change
- Cash-rate parquet schema mismatch
- Calendar annualisation error for BTC (252-day vs 365-day)
- Annual rebalance audit DataFrame overwrite bug
- Strategy-purpose classification label inconsistency (`Risk-control candidate` appearing with `wealth_test_pass = False`)

---

## Project Structure

```
Market-strats-lab/
├── configs/
│   └── spy_sma10.yaml
├── data/
│   └── processed/
├── reports/
├── src/
│   └── market_strats/
│       ├── analysis/
│       ├── data/
│       ├── strategies/
│       └── run_backtest.py
├── tests/
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd Market-strats-lab

# Create and activate virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project and dependencies
pip install -e ".[dev]"
```

---

## Running the Backtest

```bash
# Run the main strategy suite
.\.venv\Scripts\python -m market_strats.run_backtest --config configs/spy_sma10.yaml

# Run tests and linting
.\.venv\Scripts\python -m pytest; .\.venv\Scripts\python -m ruff check .

# Save full terminal output to file
.\.venv\Scripts\python -m market_strats.run_backtest --config configs/spy_sma10.yaml *> reports\latest_terminal_output.txt
```

---

## Current Configuration

```yaml
tickers:
  - SPY
  - QQQ
  - IWM
  - EFA
  - EEM
  - GLD
  - TLT
  - AGG
  - VNQ
  - BTC-USD

core_satellite:
  enabled: true
  ticker: SPY
  core_weight: 0.60
  satellite_weight: 0.40
  satellite_strategy: 12_month_absolute_momentum
  rebalance_mode: independent_sleeves

dual_momentum_pairs:
  - name: US_vs_International
    assets:
      - SPY
      - EFA
  - name: Equity_vs_Long_Bonds
    assets:
      - SPY
      - TLT
```

---

## Reports Generated

The framework writes output to `reports/`. Key files include:

```
reports/SPY_strategy_comparison_metrics.csv
reports/SPY_rolling_summary.csv
reports/SPY_strategy_scorecard.csv
reports/SPY_strategy_purpose_classification.csv
reports/SPY_core_satellite_diagnostic.csv
reports/SPY_annual_rebalance_audit.csv
reports/SPY_annual_rebalance_audit_summary.csv
reports/cross_asset_strategy_comparison_metrics.csv
reports/cross_asset_strategy_scorecards.csv
reports/cross_asset_strategy_purpose_classification.csv
reports/cross_asset_buy_hold_vs_12m_momentum.csv
reports/expanded_universe_diagnostic.csv
```

Markdown versions are generated for key reports. Equity curve and drawdown charts are saved as PNG files per ticker.

---

## Final Project View

This project has moved from simple backtesting to a structured research framework.

The most important conclusion is not "we found the perfect strategy." The real conclusion is:

> Simple rules can improve the path of returns, but each market has its own structure. SPY 12M momentum is the cleanest current leader, annual rebalanced core-satellite is the highest terminal-wealth SPY architecture tested, and EFA 200D SMA is the most interesting unvalidated lead.

The next stage is not to add random strategies. The next stage is to validate the strongest unresolved lead: **EFA SMA robustness**.