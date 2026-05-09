# Market Strats Lab

A reproducible systematic trading research lab for testing long-term market strategies honestly.

This project is **not** built to find a magic trading rule. It is built to test whether simple, explainable, systematic strategies can improve the **return / drawdown / liveability** trade-off versus buy-and-hold across major markets.

> A strategy is only useful if it survives honest testing, avoids obvious backtest traps, and gives a trade-off an actual investor could plausibly stick with.

---

## Important Disclaimer

This project is for **research and education only**.

It is not financial advice, investment advice, or a recommendation to buy or sell any asset. Historical backtests can be misleading, especially when many strategies, assets, and parameters are tested. Real-world results can differ because of data quality, taxes, execution costs, slippage, liquidity, regime changes, investor behaviour, and future market conditions.

**Current status: research-grade framework. Not a production-ready trading system. Not ready for real-money deployment.**

---

## Final Project Conclusion

The ETF/SPY research phase produced a regime-dependent answer, not a universal winner.

| Objective | Current Best Answer |
|---|---|
| Raw wealth in bull-heavy regimes | Buy and Hold |
| Defensive timing | SPY 12-Month Absolute Momentum |
| Behavioural compromise / tracking-error-regret control | 60/40 Annual Rebalanced SPY Core-Satellite |
| Capital preservation / lowest drawdown | 50/30/20 Defensive Diversified Portfolio |
| EFA-specific trend signal | EFA 200-Day SMA |

The most important finding:

> No strategy dominates across all regimes on both return and risk.

SPY 12-month absolute momentum is **not** the best overall strategy. It is a strong defensive timing strategy. Buy-and-hold dominated the 2016–2026 holdout because that period strongly favoured full equity exposure. Annual core-satellite gained credibility because it kept a permanent SPY core while still using a tactical momentum sleeve.

The project is now past the “find another strategy” stage. The next serious work is assumption sensitivity, validation, and implementation realism.

---

## Project Status

The framework currently supports:

- Multi-asset strategy backtesting
- Buy-and-hold benchmarks
- Monthly and daily SMA trend strategies
- Absolute momentum strategies
- Drawdown-tranche dip-buying tests
- Trend-filtered drawdown strategies
- Dual momentum rotation tests
- Core-satellite portfolio structures
- Independent sleeve portfolios
- Annual rebalanced portfolios
- Annual rebalance audits
- Rebalance-month sensitivity tests
- Cross-asset diagnostics
- Expanded universe testing
- Rolling-window analysis
- Regime analysis
- Cash-yield modelling via T-bill proxy
- IRX discount-rate conversion
- Calendar-aware annualisation, including 24/7 assets like BTC
- Strategy-purpose classification
- Candidate portfolio decision gates
- Candidate portfolio sleeve attribution
- Warmup audits
- Holdout validation
- Final strategy decision reports
- Final validation conclusion reports
- Markdown, CSV, and chart generation
- Unit tests and linting with `pytest` and `ruff`

---

## Research Question

> Can simple systematic rules improve long-term outcomes versus buy-and-hold without destroying compounding?

Strategies are evaluated on:

| Metric | Why It Matters |
|---|---|
| Terminal wealth / CAGR | Raw compounding power |
| Max drawdown | Worst-case investor pain |
| Calmar ratio | Return per unit of maximum drawdown |
| Volatility | Path smoothness |
| Sharpe / Sortino | Risk-adjusted efficiency |
| Worst 3Y / 5Y CAGR | Bad-window survivability |
| Exposure time | How often the strategy is invested |
| Trade count / turnover | Friction and tax efficiency |
| Time underwater | Duration of loss periods |
| Regime performance | How it behaves in different market environments |
| Strategy-purpose classification | Whether it is wealth-building, defensive, behavioural, or rejected |
| Holdout validation | Whether conclusions survive outside the reference period |

The goal is not only to ask:

> Did it make more money?

but also:

> Was the path liveable, and would an investor realistically stick with it?

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
| `BTC-USD` | Bitcoin | Quarantined separate research branch |

Bitcoin is deliberately treated as a **separate/quarantined research branch** because its history is short, extreme, structurally different, and subject to strong selection bias.

---

## Strategies Implemented

### 1. Buy and Hold

The passive benchmark. Buy at inception and hold.

**SPY full-period result: 1993-01-29 to 2026-05-01**

| Metric | Value |
|---|---:|
| End Value | $298,092 |
| CAGR | 10.75% |
| Calmar | 0.195 |
| Max Drawdown | -55.19% |
| Worst 3Y CAGR | -16.29% |
| Worst 5Y CAGR | -6.86% |

Buy-and-hold remains extremely hard to beat on raw compounding, but the drawdown pain is severe.

---

### 2. Monthly SMA Trend Strategy

Rule:

```text
At month-end:
  if adjusted close > N-month SMA → hold asset
  else → hold cash
Execute on the next trading day.
```

Baseline uses **10-month SMA**.

**SPY result**

| Metric | Value |
|---|---:|
| End Value | $196,512 |
| CAGR | 9.37% |
| Max Drawdown | -26.28% |
| Trade Count | 47 |

The 10-month SMA reduces drawdown but gives up too much compounding versus buy-and-hold and 12-month absolute momentum.

---

### 3. Daily SMA Trend Strategy

Rule:

```text
Daily:
  if adjusted close > N-day SMA → hold asset
  else → hold cash
Execute on the next trading day.
```

Baseline uses **200-day SMA**.

**SPY result**

| Metric | Value |
|---|---:|
| CAGR | 8.82% |
| Max Drawdown | -22.88% |
| Trade Count | 215 |

For SPY, the 200-day SMA controls drawdown but is too noisy and trade-heavy.

**EFA result**

| Strategy | CAGR | Max Drawdown |
|---|---:|---:|
| EFA Buy and Hold | 6.38% | -61.04% |
| EFA 200-Day SMA | 7.63% | -26.31% |

EFA 200D SMA was later validated through neighbouring-window robustness. It is now treated as a validated EFA-specific return-enhancing candidate, not an unresolved lead.

---

### 4. 12-Month Absolute Momentum

Rule:

```text
At month-end:
  calculate trailing 12-month return
  if return is positive / above cash hurdle → hold asset
  else → hold cash
Execute on the next trading day.
```

**SPY full-period result**

| Metric | Value |
|---|---:|
| End Value | $300,260 |
| CAGR | 10.77% |
| Calmar | 0.319 |
| Max Drawdown | -33.72% |
| Trade Count | 17 |
| Exposure Time | 79.49% |

The real SPY 12M result is not “alpha”. The CAGR edge over buy-and-hold is tiny.

The real result is:

> SPY 12-month absolute momentum produced buy-and-hold-like wealth with materially lower drawdown over the full period.

After holdout validation, the wording must be stricter:

> SPY 12M is a defensive timing strategy, not the best overall strategy.

---

### 5. Drawdown Tranche

Rule:

```text
Hold a base allocation.
Add additional exposure tranches when the asset falls from its high:
  -10% drawdown → add first tranche
  -20% drawdown → add second tranche
  -30% drawdown → add third tranche
```

This strategy formally tested the original “buy more when it drops” idea.

**SPY result**

| Metric | Value |
|---|---:|
| CAGR | 8.92% |
| Max Drawdown | -50.45% |

This failed as a standalone strategy. It produced cash drag in strong markets and did not reduce drawdown enough during genuine bear markets.

---

### 6. Trend-Filtered Drawdown

Drawdown tranches, but only deployed when a trend filter is positive.

**SPY result**

| Metric | Value |
|---|---:|
| CAGR | 8.93% |
| Max Drawdown | -28.28% |
| Exposure Time | 58.01% |

It improved safety versus raw drawdown tranche, but became too underinvested to compound well.

---

### 7. Dual Momentum

Rule:

```text
At month-end:
  compare 12-month returns of two assets
  select the stronger asset
  if selected asset also passes absolute momentum filter → hold it
  else → hold cash
Execute on the next trading day.
```

Tested on:

- SPY / EFA
- SPY / TLT

**SPY / EFA**

| Strategy | CAGR | Max Drawdown |
|---|---:|---:|
| Buy & Hold SPY | 9.57% | -55.19% |
| Dual Momentum SPY/EFA | 8.56% | -33.72% |

Risk-control win, not a wealth win.

**SPY / TLT**

| Strategy | CAGR | Max Drawdown |
|---|---:|---:|
| Buy & Hold SPY | 11.12% | -55.19% |
| Dual Momentum SPY/TLT | 6.55% | -32.62% |

Too much return sacrifice. TLT was not a strong enough rotation asset over the tested period.

Allocation and opportunity-cost audits showed that binary rotation often missed major SPY recoveries because it was fully away from the main compounding engine when markets bounced.

---

### 8. SPY Core-Satellite Strategies

Core-satellite was motivated by the failure mode of binary rotation. Instead of fully exiting SPY, the portfolio keeps a permanent SPY core and uses a tactical momentum sleeve.

#### 8.1 Independent 60/40 Core-Satellite

Structure:

```text
60% SPY Buy and Hold core
40% SPY 12M Momentum satellite
No rebalancing after inception
```

**SPY result**

| Metric | Value |
|---|---:|
| End Value | $298,833 |
| CAGR | 10.76% |
| Max Drawdown | -34.29% |
| Worst 3Y CAGR | -10.44% |
| Worst 5Y CAGR | -0.74% |
| Trade Count | 18 |

Best behavioural compromise among early SPY structures. It preserved more SPY participation than full momentum while reducing drawdown materially versus buy-and-hold.

#### 8.2 Annual Rebalanced 60/40 Core-Satellite

Structure:

```text
60% SPY Buy and Hold core
40% SPY 12M Momentum satellite
Rebalanced annually back to 60/40
```

**SPY result**

| Metric | Value |
|---|---:|
| End Value | $312,725 |
| CAGR | 10.91% |
| Calmar | 0.282 |
| Max Drawdown | -38.70% |
| Trade Count | 51 |

Highest gross terminal-wealth SPY architecture tested, but with worse drawdown and weaker Calmar than pure SPY 12M.

This is not pure momentum. It is:

```text
momentum satellite + mean-reversion rebalancing
```

---

## Annual Rebalance Audit

The annual rebalance audit was added to understand why the rebalanced core-satellite achieved the highest terminal wealth.

| Metric | Value |
|---|---:|
| Rebalance Count | 33 |
| Average Rebalance Turnover | 2.68% |
| Maximum Rebalance Turnover | 20.87% |
| Average Drawdown at Rebalance | -5.88% |
| Worst Drawdown at Rebalance | -28.58% |
| Average Next 3M Return | 2.01% |
| Average Next 6M Return | 5.38% |
| Average Next 12M Return | 12.00% |

Key events:

| Date | Drawdown at Rebalance | Turnover | Next 12M Return | Interpretation |
|---|---:|---:|---:|---|
| 2001-12-31 | -18.55% | 7.68% | -12.32% | Bad forced re-risking |
| 2002-12-31 | -28.58% | 12.69% | +22.69% | Successful re-risking |
| 2008-12-31 | -28.14% | 20.87% | +18.80% | Major successful re-risking |
| 2022-12-30 | -16.20% | 3.51% | +20.97% | Successful re-risking |

Annual rebalancing improved terminal wealth by forcing capital back into SPY after drawdowns. That same mechanism also increased downside exposure.

---

## Rebalance-Month Sensitivity

To test whether December year-end rebalancing was lucky, annual rebalancing was tested in March, June, September, and December.

| Rebalance Month | End Value | CAGR | Max Drawdown | Worst 3Y CAGR | Worst 5Y CAGR |
|---:|---:|---:|---:|---:|---:|
| March | $318,177 | 10.97% | -37.39% | -10.55% | -1.31% |
| June | $308,245 | 10.86% | -37.66% | -10.65% | -1.38% |
| September | $309,959 | 10.88% | -38.31% | -10.48% | -1.55% |
| December | $312,725 | 10.91% | -38.70% | -10.60% | -1.58% |

The CAGR spread across rebalance anchors was only about 0.11 percentage points.

Conclusion:

> Annual rebalanced core-satellite was not December-fragile.

March was best, but the project deliberately did **not** switch to March. That would have been parameter-shopping.

---

## Expanded Universe Diagnostic

The expanded universe test proved that **one rule does not fit all markets**.

| Ticker | B&H CAGR | 12M Mom CAGR | CAGR Delta | B&H Max DD | 12M Max DD | DD Improvement | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| SPY | 10.75% | 10.77% | +0.02 | -55.19% | -33.72% | +21.47 pts | Wealth-equivalent risk reducer |
| QQQ | 10.66% | 10.30% | -0.36 | -82.96% | -40.97% | +41.99 pts | Risk-control candidate |
| IWM | 8.60% | 6.12% | -2.48 | -58.64% | -35.34% | +23.30 pts | Risk-control only |
| EFA | 6.38% | 4.75% | -1.63 | -61.04% | -42.29% | +18.75 pts | 12M weak; 200D SMA better |
| EEM | 9.92% | 7.23% | -2.69 | -66.43% | -40.46% | +25.97 pts | Risk-control only |
| GLD | 11.09% | 9.08% | -2.01 | -45.56% | -34.75% | +10.81 pts | Risk-control only |
| TLT | 3.70% | 2.88% | -0.82 | -48.35% | -26.59% | +21.76 pts | Risk-control only |
| AGG | 3.09% | 3.18% | +0.09 | -18.43% | -12.84% | +5.59 pts | Defensive sleeve candidate |
| VNQ | 7.59% | 4.64% | -2.95 | -73.07% | -46.29% | +26.78 pts | Risk-control only |
| BTC-USD | 56.06% | 56.30% | +0.24 | -83.40% | -80.77% | +2.63 pts | Quarantined |

---

## Strategy-Purpose Classification

The original composite scorecard could over-rank low-CAGR defensive strategies. The framework now classifies strategies by purpose.

| Classification | Meaning |
|---|---|
| Return-enhancing candidate | Meaningfully improves CAGR and does not worsen drawdown |
| Wealth-equivalent risk reducer | Keeps CAGR close to buy-and-hold while materially reducing drawdown |
| Defensive sleeve candidate | Useful defensive component, not a wealth engine |
| Behavioural compromise | Useful for liveability or tracking-error-regret control |
| Risk-control candidate | Passes wealth hurdle but gives up noticeable CAGR |
| Risk-control only | Improves drawdown but sacrifices too much CAGR |
| Benchmark | Passive reference |
| Rejected / weak | Does not justify itself versus benchmark |
| Quarantined / separate branch | Not comparable enough to the main ETF universe |

Current classifications:

| Asset / Strategy | Classification |
|---|---|
| SPY 12M Absolute Momentum | Wealth-equivalent risk reducer |
| SPY Annual Rebalanced Core-Satellite | Behavioural compromise |
| AGG 12M Absolute Momentum | Defensive sleeve candidate |
| EFA 200D SMA | Return-enhancing candidate |
| EFA 10M SMA | Risk-control candidate |
| QQQ 12M Absolute Momentum | Risk-control candidate |
| IWM / EEM / VNQ / GLD 12M Momentum | Risk-control only |
| BTC strategies | Quarantined / separate branch |

---

## EFA Robustness Tests

### Daily SMA Robustness

EFA 200D SMA was tested against neighbouring windows:

| SMA Window | CAGR | Delta vs B&H | Max DD | DD Improvement |
|---:|---:|---:|---:|---:|
| 100D | 6.04% | -0.34 pts | -26.56% | +34.48 pts |
| 150D | 6.45% | +0.07 pts | -24.61% | +36.43 pts |
| 200D | 7.63% | +1.25 pts | -26.31% | +34.73 pts |
| 250D | 6.54% | +0.16 pts | -21.03% | +40.01 pts |
| 300D | 6.14% | -0.24 pts | -28.66% | +32.38 pts |

Conclusion:

> EFA daily SMA trend filtering is a validated non-SPY signal family. EFA 200D SMA is the strongest return-enhancing version, but the broader 150D–250D region is what matters.

### Monthly SMA Robustness

EFA 10M SMA was tested against neighbouring monthly windows:

| SMA Window | CAGR | Delta vs B&H | Max DD | DD Improvement |
|---:|---:|---:|---:|---:|
| 6M | 5.39% | -0.99 pts | -28.66% | +32.38 pts |
| 8M | 5.69% | -0.69 pts | -33.40% | +27.64 pts |
| 10M | 6.27% | -0.11 pts | -34.73% | +26.31 pts |
| 12M | 5.87% | -0.51 pts | -27.63% | +33.41 pts |
| 14M | 5.19% | -1.19 pts | -26.83% | +34.21 pts |

Conclusion:

> EFA monthly SMA is mainly risk-control, not return-enhancing. EFA 10M SMA was demoted to risk-control candidate.

---

## Candidate Multi-Asset Portfolios

After validating SPY 12M, EFA 200D, and AGG 12M, several independent-sleeve candidate portfolios were tested.

### 50/30/20 Defensive Diversified Portfolio

```text
50% SPY 12M Absolute Momentum
30% EFA 200D SMA
20% AGG 12M Absolute Momentum
```

| Metric | Value |
|---|---:|
| CAGR | 8.53% |
| Calmar | 0.367 |
| Max Drawdown | -23.23% |
| End Value | $63,471 |

This passed drawdown and Calmar gates but failed the CAGR gate. It is a defensive diversified portfolio, not a wealth-growth replacement.

### 70/20/10 Growth-Biased Portfolio

```text
70% SPY 12M Absolute Momentum
20% EFA 200D SMA
10% AGG 12M Absolute Momentum
```

| Metric | Value |
|---|---:|
| CAGR | 9.22% |
| Calmar | 0.331 |
| Max Drawdown | -27.83% |
| End Value | $73,363 |

This improved CAGR versus 50/30/20 but failed the pre-declared CAGR gate.

### 80/10/10 SPY-Dominant Portfolio

```text
80% SPY 12M Absolute Momentum
10% EFA 200D SMA
10% AGG 12M Absolute Momentum
```

| Metric | Value |
|---|---:|
| CAGR | 9.44% |
| Calmar | 0.313 |
| Max Drawdown | -30.18% |
| End Value | $76,638 |

This moved closer to SPY 12M but failed both CAGR and drawdown gates.

Conclusion:

> The multi-asset portfolios are useful defensively, but they did not beat SPY 12M as a wealth-growth core.

The multi-asset wealth-growth branch should stop for now.

---

## Final Strategy Decision Report

| Strategy | Role | CAGR | Calmar | Max DD |
|---|---|---:|---:|---:|
| Buy and Hold | Passive benchmark | 10.75% | 0.195 | -55.19% |
| SPY 12M Absolute Momentum | Leading defensive timing strategy | 10.77% | 0.319 | -33.72% |
| 60/40 Annual Rebalanced SPY Core-Satellite | Highest gross SPY terminal wealth | 10.91% | 0.282 | -38.70% |
| 50/30/20 Defensive Diversified Portfolio | Capital preservation | 8.53% | 0.367 | -23.23% |
| 70/20/10 Growth-Biased Portfolio | Near-miss defensive-growth portfolio | 9.22% | 0.331 | -27.83% |
| 80/10/10 SPY-Dominant Portfolio | Failed sensitivity check | 9.44% | 0.313 | -30.18% |

---

## Holdout Validation

A holdout validation split was added:

| Period | Dates |
|---|---|
| Reference | 1993-01-29 to 2015-12-31 |
| Holdout | 2016-01-01 to 2026-05-01 |

For multi-asset portfolios, the common start date is later because AGG begins in 2003.

### Reference Period

| Strategy | CAGR | Calmar | Max DD |
|---|---:|---:|---:|
| Buy and Hold | 8.95% | 0.162 | -55.19% |
| SPY 12M Absolute Momentum | 10.53% | 0.553 | -19.03% |
| Annual Core-Satellite | 9.77% | 0.252 | -38.70% |
| 50/30/20 Defensive Portfolio | 7.84% | 0.570 | -13.76% |
| 70/20/10 Growth-Biased Portfolio | 8.38% | 0.530 | -15.81% |
| 80/10/10 SPY-Dominant Portfolio | 8.43% | 0.515 | -16.37% |

Reference conclusion:

> SPY 12M looked excellent. Defensive portfolios had the best Calmar and drawdown control. Buy-and-hold had severe drawdown.

### Holdout Period

| Strategy | CAGR | Calmar | Max DD |
|---|---:|---:|---:|
| Buy and Hold | 15.03% | 0.446 | -33.72% |
| SPY 12M Absolute Momentum | 11.49% | 0.341 | -33.72% |
| Annual Core-Satellite | 13.66% | 0.405 | -33.72% |
| 50/30/20 Defensive Portfolio | 9.44% | 0.406 | -23.23% |
| 70/20/10 Growth-Biased Portfolio | 10.36% | 0.372 | -27.83% |
| 80/10/10 SPY-Dominant Portfolio | 10.78% | 0.357 | -30.18% |

Holdout conclusion:

> Buy-and-hold dominated the 2016–2026 holdout because the period strongly favoured full equity exposure. SPY 12M did not reduce max drawdown in the holdout; it reduced return. Annual core-satellite outperformed SPY 12M because the permanent SPY core stayed invested during bull/rebound periods.

---

## Final Validation Conclusion

| Claim | Status | Interpretation |
|---|---|---|
| No strategy dominates across all regimes on both return and risk | Survived | The project produced objective-dependent winners |
| Buy and Hold is the best raw compounding strategy in bull-heavy regimes | Survived | Full exposure dominated the 2016–2026 holdout |
| SPY 12M is the best overall strategy | Failed | It lagged badly in the holdout |
| SPY 12M is a strong defensive timing strategy | Survived | Strong in reference period, weakened in holdout |
| Momentum/cash filters can lag in V-shaped recovery regimes | Survived | The holdout exposed this failure mode |
| Annual core-satellite reduces tracking-error regret | Survived | Permanent core helped in bull/rebound periods |
| Annual core-satellite is regime-dependent | Survived | Underperformed SPY 12M in reference, outperformed in holdout |
| 50/30/20 is a defensive/capital-preservation portfolio | Survived | Consistently lowered drawdown |
| 50/30/20 is a wealth-growth replacement | Failed | Too much CAGR sacrifice |
| 70/20/10 and 80/10/10 solve multi-asset wealth growth | Failed | Failed pre-declared gates |
| EFA 200D SMA is a validated non-SPY signal | Survived | Survived neighbouring-window robustness |
| EFA 10M SMA is a validated return-enhancing monthly signal | Failed | Monthly robustness did not support it |
| Multi-asset wealth-growth branch should stop for now | Survived | Defensive usefulness remained, but wealth-growth replacement failed |

---

## Methodology Notes

### Lookahead Bias Controls

- Signals are generated using only data available at the signal date.
- Execution occurs on the next trading day.
- Positions are applied after execution, not on the signal day.
- The implementation is intentionally conservative, but still needs additional dedicated lookahead audit tests before real-money interpretation.

### Cash Returns

Cash is modelled using a T-bill proxy, `^IRX`.

Important detail:

- `^IRX` is quoted as a bank discount rate.
- The project converts it into an investment yield before applying cash returns.
- Cash returns are aligned to each asset’s trading calendar.
- This matters because momentum strategies spend meaningful time in cash.

### Calendar-Aware Annualisation

The framework infers periods per year from actual data frequency.

- ETFs trade on US business days.
- BTC trades every calendar day.

Using one fixed 252-day annualisation factor across all assets would distort BTC volatility, Sharpe, and cash-period returns.

### Adjusted Close Data

Data uses adjusted close prices from `yfinance`, reflecting dividends and splits through backward adjustment.

Known issue:

> Adjusted close is not perfectly point-in-time because historical prices are retroactively adjusted.

A future validation step should test raw-close signals with adjusted-close returns.

### Slippage

A flat 5 basis points slippage is applied per trade.

This is simple and conservative enough for low-turnover ETF strategies, but it does not fully model wider bid-ask spreads during market stress.

### Cached Data

Price and cash-rate data are cached in `data/processed/`. The loaders include schema normalisation so older cached files remain compatible after refactors.

---

## Known Limitations

This project is **not production-ready**.

Remaining concerns include:

- `yfinance` data reliability
- Adjusted-close retroactive adjustment
- No second data-source cross-check
- No tax modelling
- No bid-ask spread modelling during stress periods
- No FX cost modelling for non-USD investors
- Cash proxy may overstate retail-accessible yields
- No bootstrap confidence intervals
- No multiple-comparisons correction across strategy/asset combinations
- No full walk-forward optimisation framework
- Limited out-of-sample testing
- Asset universe selection bias
- BTC selection bias
- Strategy conclusions are regime-dependent
- Investor behaviour and tracking-error regret are not directly modelled
- The holdout period itself was not neutral; it was heavily bull/rebound oriented

---

## Bugs Caught and Fixed

- Package import setup issue
- pandas month-end resampling behaviour change
- Cash-rate parquet schema mismatch
- IRX discount-rate conversion issue
- Calendar annualisation error for BTC
- Annual rebalance audit DataFrame overwrite bug
- Strategy-purpose classification label inconsistency
- Candidate portfolio warmup contamination concern
- Missing Calmar and date fields in final report
- Incorrect `calculate_metrics()` keyword call in holdout validation

---

## Project Structure

```text
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
git clone <your-repo-url>
cd Market-strats-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

---

## Running the Project

Run the full strategy suite:

```bash
.\.venv\Scripts\python -m market_strats.run_backtest --config configs/spy_sma10.yaml
```

Run tests and linting:

```bash
.\.venv\Scripts\python -m pytest; .\.venv\Scripts\python -m ruff check .
```

Save full terminal output:

```bash
.\.venv\Scripts\python -m market_strats.run_backtest --config configs/spy_sma10.yaml *> reports\latest_terminal_output.txt
```

---

## Key Reports Generated

The framework writes outputs to `reports/`.

Key final reports:

```text
reports/final_strategy_decision_report.csv
reports/final_strategy_decision_report.md
reports/finalist_holdout_validation.csv
reports/finalist_holdout_validation_summary.csv
reports/finalist_holdout_validation.md
reports/final_validation_conclusion.csv
reports/final_validation_conclusion.md
```

Other important reports:

```text
reports/SPY_strategy_comparison_metrics.csv
reports/SPY_rolling_summary.csv
reports/SPY_strategy_scorecard.csv
reports/SPY_strategy_purpose_classification.csv
reports/SPY_core_satellite_diagnostic.csv
reports/SPY_annual_rebalance_audit.csv
reports/SPY_annual_rebalance_audit_summary.csv
reports/SPY_rebalance_month_sensitivity.csv
reports/cross_asset_strategy_comparison_metrics.csv
reports/cross_asset_strategy_purpose_classification.csv
reports/cross_asset_buy_hold_vs_12m_momentum.csv
reports/expanded_universe_diagnostic.csv
reports/EFA_sma_window_robustness.csv
reports/EFA_monthly_sma_window_robustness.csv
reports/candidate_portfolio_validated_signal_portfolio_metrics.csv
reports/candidate_portfolio_growth_biased_signal_portfolio_metrics.csv
reports/candidate_portfolio_spy_dominant_signal_portfolio_metrics.csv
```

Markdown reports and PNG charts are generated for major outputs.

---

## Current Configuration Overview

The main config currently tests:

- SPY, QQQ, IWM, EFA, EEM, GLD, TLT, AGG, VNQ, BTC-USD
- Buy and hold
- Monthly SMA
- Daily SMA
- 12M absolute momentum
- Drawdown tranche
- Trend-filtered drawdown
- Dual momentum pairs
- Core-satellite strategies
- Rebalance audits
- Cross-asset diagnostics
- EFA robustness
- Candidate portfolios
- Final decision reports
- Holdout validation
- Final validation conclusions

See:

```text
configs/spy_sma10.yaml
```

---

## Research Phase Status

The ETF/SPY phase is effectively complete.

Current project state:

| Branch | Status |
|---|---|
| SPY 12M momentum | Survived as defensive timing |
| Buy-and-hold | Survived as raw bull-regime compounding benchmark |
| Annual core-satellite | Survived as behavioural/regime compromise |
| 50/30/20 multi-asset portfolio | Survived as capital preservation |
| 70/20/10 and 80/10/10 portfolios | Failed as wealth-growth replacements |
| EFA 200D SMA | Survived as validated EFA-specific signal |
| EFA 10M SMA | Failed as return-enhancing monthly signal |
| Drawdown tranche | Failed |
| Dual momentum | Risk-control only, too much opportunity cost |
| BTC | Quarantined |

---

## Next Research Phase

Do **not** keep adding ETF strategy variants.

The next serious phase is validation and implementation realism:

1. Raw-close signal sensitivity
2. Cash proxy sensitivity
3. Tax-aware analysis
4. Execution/slippage sensitivity
5. Second data-source cross-check
6. Expanded walk-forward validation
7. Behavioural/tracking-error regret analysis
8. BTC-specific quarantined research branch, only if treated separately

---

## Final Project View

This project moved from simple backtesting to a structured research framework.

The final answer is not:

> We found the perfect strategy.

The real answer is:

> Simple systematic rules can improve the path of returns, but the winner depends on objective and regime. Buy-and-hold wins raw wealth in bull-heavy regimes. SPY 12M survives as defensive timing. Annual core-satellite is a behavioural compromise. 50/30/20 is capital preservation. No tested multi-asset portfolio replaced SPY 12M as a wealth-growth core.

That is a useful result. It stops the project from pretending that one line on a chart answers every investor problem.