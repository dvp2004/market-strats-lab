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

## Executive Summary

Market Strats Lab started as a simple ETF trend-following project and evolved into a structured systematic strategy research framework.

The project now has two major research phases:

| Phase | Focus | Status |
|---|---|---|
| Phase 1 | Single-asset ETF timing, SPY strategies, core-satellite structures, cross-asset classification | Complete |
| Phase 2 | Tactical relative-momentum allocation and regime-switch portfolio management | Validated checkpoint reached |
| Phase 3A | Robustness checks for the 3D confirmed regime-switch overlay | Complete |
| Phase 3B | Controlled asset expansion: oil and ETH quarantine diagnostics | Oil promising but not validated; ETH rejected |

The central conclusion is:

> No strategy dominates across all regimes on both return and risk.

However, the project did identify a current best risk-adjusted system:

> **SPY Trend Regime Switch Overlay 3D Confirmed**

This system keeps exposure to SPY when SPY is in a confirmed healthy trend regime and switches to a constrained tactical relative-momentum allocator after persistent trend deterioration.

It does **not** beat SPY buy-and-hold on raw terminal wealth. SPY buy-and-hold remains the raw wealth benchmark.

But it does beat SPY 12-month absolute momentum on full-period and holdout risk-adjusted performance.

### Canonical Research Checkpoint

The canonical project endpoint is now explicitly pinned:

```text
2026-05-01
```

This matters because the data cache previously refreshed to 2026-05-13 during later experiments. That refreshed run is treated as exploratory only. The official README numbers below use the pinned 2026-05-01 endpoint.

The current validated checkpoint is:

| Item | Value |
|---|---:|
| Canonical Phase 2/3 period | 2006-04-28 to 2026-05-01 |
| Best system | SPY Trend Regime Switch Overlay 3D Confirmed |
| Best system CAGR | 10.22% |
| Best system Calmar | 0.429 |
| Best system max drawdown | -23.83% / -23.84% depending report rounding |
| SPY Buy & Hold CAGR over same period | 10.90% |
| SPY Buy & Hold max drawdown | -55.19% |
| SPY 12M Momentum CAGR over same period | 9.68% |
| SPY 12M Momentum max drawdown | -33.72% |

Strict endpoint checks are now part of the research discipline: generated reports should not contain `end_date` later than `2026-05-01` unless a deliberate new refreshed checkpoint is opened.

---

## Current Best Results

### Full-Period Comparison

Common period for the Phase 2 system comparison:

```text
2006-04-28 to 2026-05-01
```

| Strategy | Role | End Value | CAGR | Calmar | Volatility | Max Drawdown | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| SPY Buy & Hold | Raw wealth benchmark | $79,306.63 | 10.90% | 0.197 | 19.41% | -55.19% | Highest raw terminal wealth |
| SPY 12M Absolute Momentum | Defensive timing benchmark | $63,497.24 | 9.68% | 0.287 | 15.05% | -33.72% | Strong simple benchmark |
| Top 3 Equal Weight Trend-Confirmed Relative Momentum | Best standalone balanced allocator | $58,401.74 | 9.22% | 0.317 | 16.29% | -29.06% | Useful standalone Phase 2 allocator |
| Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum | Best standalone defensive allocator | $52,197.16 | 8.61% | 0.351 | 13.35% | -24.54% | Strong defensive/liveability allocator |
| **SPY Trend Regime Switch Overlay 3D Confirmed** | **Best overall risk-adjusted system** | **$70,048.61** | **10.22%** | **0.429** | **13.58%** | **-23.84%** | **Current best risk-adjusted candidate** |

### Holdout Validation

Holdout period:

```text
2016-01-04 to 2026-05-01
```

| Strategy | Holdout CAGR | Holdout Calmar | Holdout Max Drawdown | Holdout Volatility |
|---|---:|---:|---:|---:|
| SPY Trend Regime Switch Overlay 3D Confirmed | 12.06% | 0.506 | -23.83% | 13.63% |
| SPY Buy & Hold | 15.03% | 0.446 | -33.72% | 17.87% |
| SPY 12M Absolute Momentum | 11.49% | 0.341 | -33.72% | 16.12% |
| Top 3 Equal Weight Trend-Confirmed Relative Momentum | 9.40% | 0.376 | -25.02% | 16.26% |
| Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum | 8.70% | 0.386 | -22.52% | 14.03% |

Holdout conclusion:

> The 3D confirmed overlay beat SPY 12M in the holdout on CAGR, Calmar, max drawdown, volatility, Sharpe, and Sortino. SPY buy-and-hold still won raw CAGR, but with materially worse drawdown.

### Phase 3A Robustness Summary

After the 3D confirmed overlay became the current best system candidate, it was tested against execution-cost, cash-yield, and raw-close signal sensitivity.

| Robustness Check | CAGR | Calmar | Max Drawdown | Status |
|---|---:|---:|---:|---|
| Baseline 5 bps slippage | 10.22% | 0.429 | -23.84% | Baseline |
| 10 bps slippage | 9.93% | 0.415 | -23.91% | Passed |
| 25 bps slippage | 9.08% | 0.376 | -24.12% | Defensive only / weakened |
| 50 bps slippage | 7.67% | 0.304 | -25.21% | Failed as wealth-growth case |
| 0% cash yield | 9.85% | 0.413 | -23.84% | Passed |
| Raw-close signal full period | 9.72% | 0.408 | -23.84% | Passed with caveat |
| Raw-close signal holdout | 11.72% | 0.492 | -23.84% | Passed |

Robustness conclusion:

> The 3D overlay is viable under low/moderate friction and is not dependent on cash yield. Its main current weakness is high execution friction. The raw-close signal test passed with caveat, meaning the system did not collapse when SPY trend signals were based on raw closes rather than adjusted closes.

---

## Key Caveat

The 3D confirmation rule was selected after auditing the raw 200D overlay's whipsaw behaviour. Therefore, the holdout validation is a **robustness check**, not a perfectly clean out-of-sample experiment.

This matters. The result is strong, but it should not be oversold.

---

## Final Project View

The project did **not** find a universal strategy that beats SPY buy-and-hold on raw wealth while also reducing drawdown.

What it found is more useful:

| Objective | Current Winner |
|---|---|
| Raw terminal wealth | SPY Buy and Hold |
| Simple defensive timing benchmark | SPY 12M Absolute Momentum |
| Highest gross SPY architecture | 60/40 Annual Rebalanced SPY Core-Satellite |
| Best standalone balanced allocator | Top 3 Equal Weight Trend-Confirmed Relative Momentum |
| Best standalone defensive allocator | Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum |
| Best overall risk-adjusted system | SPY Trend Regime Switch Overlay 3D Confirmed |

The real answer is:

> Simple systematic rules can improve the path of returns, but the winner depends on objective and regime.

---

## Research Question

The project asks:

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
| Regime performance | How behaviour changes across market environments |
| Strategy-purpose classification | Whether a strategy is wealth-building, defensive, behavioural, or rejected |
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
| `SLV` | Silver | High-volatility commodity / precious-metal exposure |
| `DBC` | Broad commodities | Commodity cycle exposure |
| `USO` | Oil proxy | Controlled oil-expansion diagnostic |
| `TLT` | Long-duration US Treasuries | Duration-heavy bond / defensive asset |
| `AGG` | Aggregate US bonds | Broad defensive bond sleeve |
| `VNQ` | US REITs | Real-estate equity / credit-sensitive asset |
| `BTC-USD` | Bitcoin | Quarantined separate research branch |
| `ETH-USD` | Ethereum | Quarantined crypto diagnostic |

Bitcoin and Ethereum are deliberately treated as **separate/quarantined research branches** because their histories are shorter, extreme, structurally different, and subject to strong selection bias. They are not part of the main validated ETF allocator.

---

# Phase 1: ETF/SPY Strategy Research

## Phase 1 Goal

Phase 1 tested whether simple ETF timing and allocation strategies could improve the **return / drawdown / liveability** trade-off versus SPY buy-and-hold.

The baseline was:

```text
Buy SPY and hold forever.
```

The research then tested whether trend-following, absolute momentum, drawdown buying, dual momentum, core-satellite structures, rebalancing, and fixed multi-asset portfolios could improve the outcome.

---

## Phase 1 Strategies Implemented

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

EFA 200D SMA was later validated through neighbouring-window robustness. It is treated as a validated EFA-specific return-enhancing candidate, not an unresolved lead.

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

Annual rebalancing improved terminal wealth by forcing capital back into SPY after drawdowns. That same mechanism also increased downside exposure.

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

> EFA daily SMA trend filtering is a validated non-SPY signal family. EFA 200D SMA is the strongest return-enhancing version, but the broader 150D-250D region is what matters.

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

| Portfolio | Structure | CAGR | Calmar | Max DD | Verdict |
|---|---|---:|---:|---:|---|
| Defensive Diversified | 50% SPY 12M / 30% EFA 200D / 20% AGG 12M | 8.53% | 0.367 | -23.23% | Defensive, not wealth-growth |
| Growth-Biased | 70% SPY 12M / 20% EFA 200D / 10% AGG 12M | 9.22% | 0.331 | -27.83% | Near miss, failed CAGR gate |
| SPY-Dominant | 80% SPY 12M / 10% EFA 200D / 10% AGG 12M | 9.44% | 0.313 | -30.18% | Failed sensitivity check |

Conclusion:

> The multi-asset portfolios are useful defensively, but they did not beat SPY 12M as a wealth-growth core.

The multi-asset wealth-growth branch should stop for now.

---

## Phase 1 Final Validation Conclusion

| Claim | Status | Interpretation |
|---|---|---|
| No strategy dominates across all regimes on both return and risk | Survived | The project produced objective-dependent winners |
| Buy and Hold is the best raw compounding strategy in bull-heavy regimes | Survived | Full exposure dominated the 2016-2026 holdout |
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

# Phase 2: Tactical Portfolio Management

## Phase 2 Goal

Phase 2 asks:

> Can the framework dynamically allocate across broad investable assets and improve the return/drawdown/liveability trade-off versus SPY buy-and-hold and SPY 12M?

The original idea was to build towards a model that could eventually consider technical, fundamental, sentiment, macro, geopolitical, and cross-asset information.

But the project deliberately did **not** jump straight to sentiment, macro, ML, BTC, or individual stocks.

The disciplined sequence was:

```text
1. Build a price/risk allocator.
2. Diagnose whether it works.
3. Add portfolio constraints.
4. Validate.
5. Diagnose regime behaviour.
6. Only then consider more complex information.
```

---

## Phase 2 Universe

Phase 2 expanded the tactical allocation universe to:

```text
SPY, QQQ, IWM, EFA, EEM, AGG, TLT, GLD, SLV, VNQ, DBC
```

This includes US equities, international equities, bonds, REITs, gold, silver, and broad commodities.

BTC remains quarantined and is not part of the main tactical allocator.

---

## Relative Momentum Allocator

### Baseline Rule

```text
At month-end:
  rank assets by 12-month return
  keep assets with positive 12-month momentum
  hold top 3
  unused capital goes to cash
```

The framework uses daily adjusted close data, but the base allocator makes monthly decisions.

### Initial Bug Caught

The first relative momentum result showed unrealistically low exposure. This exposed a bug:

```text
Target weights were not persisting between monthly rebalance dates.
```

Fix:

```text
Initialise target weights as NaN.
Forward-fill weights between rebalance dates.
Set weights to zero only when no asset qualifies.
```

---

## Phase 2 Allocator Results

| Strategy | CAGR | Calmar | Volatility | Max Drawdown | Verdict |
|---|---:|---:|---:|---:|---|
| Top 3 Equal Weight Relative Momentum | 8.93% | 0.250 | 17.12% | -35.74% | Failed baseline |
| Top 3 Inverse Volatility Relative Momentum | 8.52% | 0.264 | 15.60% | -32.31% | Better risk, weaker return |
| Top 3 Equal Weight Trend-Confirmed Relative Momentum | 9.22% | 0.317 | 16.29% | -29.06% | Best standalone balanced allocator |
| Top 3 Inverse Volatility Trend-Confirmed Relative Momentum | 8.74% | 0.295 | 14.85% | -29.63% | Defensive variant |
| Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum | 8.61% | 0.351 | 13.35% | -24.54% | Best standalone defensive allocator |

Trend confirmation rule:

```text
Asset must have:
  1. positive 12M momentum
  2. price above 200D SMA
```

Constrained allocator additions:

```text
Maximum single-asset weight
Asset-group caps
Commodity cap
Excess allocation goes to cash
```

Conclusion:

> Trend confirmation and portfolio constraints improved the allocator, but relative momentum alone did not beat SPY buy-and-hold on raw wealth.

---

## Phase 2 Holdout Validation

Split:

| Period | Dates |
|---|---|
| Reference | 2006-04-28 to 2015-12-31 |
| Holdout | 2016-01-04 to 2026-05-01 |

### Reference Period

| Strategy | CAGR | Calmar | Volatility |
|---|---:|---:|---:|
| Top 3 Equal Weight Trend-Confirmed | 9.22% | 0.346 | 16.32% |
| Top 3 Constrained Trend-Confirmed | 8.67% | 0.540 | 12.59% |
| SPY Buy and Hold | 6.84% | 0.124 | 20.94% |
| SPY 12M Momentum | 7.95% | 0.427 | 13.82% |

Reference conclusion:

> Phase 2 added real value in the mixed/choppy reference period.

### Holdout Period

| Strategy | CAGR | Calmar | Volatility |
|---|---:|---:|---:|
| Top 3 Equal Weight Trend-Confirmed | 9.40% | 0.376 | 16.26% |
| Top 3 Constrained Trend-Confirmed | 8.70% | 0.386 | 14.03% |
| SPY Buy and Hold | 15.03% | 0.446 | 17.87% |
| SPY 12M Momentum | 11.49% | 0.341 | 16.12% |

Holdout conclusion:

> Phase 2 failed as a wealth-growth replacement in the bull-heavy 2016-2026 holdout, but retained defensive/regime-diversifying value.

---

## Regime Diagnostics

The regime diagnostic asked:

> When does the allocator work, and when does it fail?

### SPY Above 200D Trend

| Strategy | Conditional Annualised Return |
|---|---:|
| SPY Buy and Hold | 26.32% |
| SPY 12M Momentum | 22.21% |
| Equal Weight Trend-Confirmed Allocator | 18.56% |
| Constrained Trend-Confirmed Allocator | 16.22% |

Conclusion:

> When SPY is healthy, SPY dominates. The tactical allocators are too defensive.

### SPY Below 200D Trend

| Strategy | Conditional Annualised Return |
|---|---:|
| Constrained Trend-Confirmed Allocator | -14.58% |
| Equal Weight Trend-Confirmed Allocator | -18.39% |
| SPY 12M Momentum | -26.59% |
| SPY Buy and Hold | -31.34% |

Conclusion:

> When SPY trend is broken, the allocators lose much less than SPY.

### Deep SPY Bear Drawdowns Below -20%

| Strategy | Conditional Annualised Return |
|---|---:|
| Equal Weight Trend-Confirmed Allocator | 9.16% |
| Constrained Trend-Confirmed Allocator | 7.27% |
| SPY 12M Momentum | -8.84% |
| SPY Buy and Hold | -20.90% |

Conclusion:

> The relative momentum allocators are valuable when SPY is in serious trouble.

### Normal Corrections: -10% to -20%

| Strategy | Conditional Annualised Return |
|---|---:|
| SPY Buy and Hold | -6.81% |
| SPY 12M Momentum | -11.26% |
| Constrained Allocator | -11.75% |
| Equal Weight Allocator | -15.80% |

Conclusion:

> The allocators struggle in transition regimes.

---

# Regime-Switch Overlay Branch

## Motivation

The regime diagnostic showed:

```text
When SPY is healthy:
  SPY dominates.

When SPY is broken:
  the constrained allocator protects better.
```

This led to a regime-switch overlay.

---

## Raw SPY 200D Regime Switch Overlay

Rule:

```text
If SPY is above 200D SMA:
  hold SPY buy-and-hold

If SPY is below 200D SMA:
  hold constrained trend-confirmed relative momentum allocator
```

### Raw Overlay Result

| Metric | Value |
|---|---:|
| CAGR | 8.48% |
| Calmar | 0.329 |
| Volatility | 13.22% |
| Max Drawdown | -25.77% |
| End Value | $50,979 |

Conclusion:

> The raw binary overlay failed as a new leader.

It improved drawdown versus SPY 12M, but lost too much CAGR and did not beat the constrained allocator on defensive quality.

---

## Raw Overlay Whipsaw Audit

| Metric | Value |
|---|---:|
| Total Switches | 114 |
| Whipsaw Count | 86 |
| Whipsaw Rate | 75.44% |
| Median Days Until Next Switch | 5 |
| Average SPY Distance From 200D at Switch | -0.17% |

Conclusion:

> The raw overlay was not detecting clean regimes. It was thrashing around the 200D boundary.

This justified exactly one buffered test.

---

## 3D Confirmed Regime Switch Overlay

Rule:

```text
If SPY closes below its 200D SMA for 3 consecutive trading days:
  switch to constrained trend-confirmed allocator

If SPY closes above its 200D SMA for 3 consecutive trading days:
  switch back to SPY
```

No other confirmation windows, bands, blends, macro filters, sentiment filters, BTC, or individual-stock signals were tested at this stage.

### Full-Period Result

| Metric | Value |
|---|---:|
| End Value | $70,048.61 |
| CAGR | 10.22% |
| Calmar | 0.429 |
| Volatility | 13.58% |
| Max Drawdown | -23.83% |
| Sharpe | 0.785 |
| Sortino | 0.975 |

Compared to SPY 12M:

| Metric | 3D Overlay | SPY 12M |
|---|---:|---:|
| CAGR | 10.22% | 9.68% |
| Calmar | 0.429 | 0.287 |
| Volatility | 13.58% | 15.05% |
| Max Drawdown | -23.83% | -33.72% |
| End Value | $70,048.61 | $63,497.24 |

Conclusion:

> The 3D overlay beat SPY 12M full-period on CAGR, Calmar, volatility, max drawdown, Sharpe, Sortino, terminal value, and rolling-window survivability.

It still trailed SPY buy-and-hold on raw terminal wealth.

---

## 3D Overlay Mode Summary

| Mode | Days | % Days | Total Return | Average Position | Average Cash |
|---|---:|---:|---:|---:|---:|
| Offensive SPY | 3,996 | 79.38% | 452.56% | 100.00% | 0.00% |
| Defensive Allocator | 1,038 | 20.62% | 26.77% | 58.10% | 41.90% |

Interpretation:

> The overlay spent most of its time in SPY and switched to the defensive allocator roughly one-fifth of the time.

---

## 3D Overlay Whipsaw Audit

| Metric | Raw Overlay | 3D Confirmed Overlay |
|---|---:|---:|
| Total Switches | 114 | 52 |
| Whipsaw Count | 86 | 29 |
| Whipsaw Rate | 75.44% | 55.77% |
| Median Days Until Next Switch | 5 | 20 |

Conclusion:

> The 3D confirmation filter materially reduced whipsaw damage.

---

## 3D Overlay Rolling-Window Results

### 3-Year Windows

| Strategy | Avg CAGR | Worst CAGR | Avg Max DD | Worst Max DD |
|---|---:|---:|---:|---:|
| 3D Overlay | 9.88% | 2.50% | -18.03% | -23.83% |
| SPY 12M Momentum | 9.14% | -1.95% | -20.11% | -33.72% |
| SPY Buy and Hold | 11.07% | -16.73% | -25.83% | -55.19% |

### 5-Year Windows

| Strategy | Avg CAGR | Worst CAGR | Avg Max DD | Worst Max DD |
|---|---:|---:|---:|---:|
| 3D Overlay | 9.96% | 3.68% | -20.14% | -23.83% |
| SPY 12M Momentum | 9.16% | -0.19% | -23.48% | -33.72% |
| SPY Buy and Hold | 11.76% | -1.15% | -29.92% | -55.19% |

Conclusion:

> The 3D overlay improved worst rolling 3Y and 5Y survivability versus both SPY 12M and SPY buy-and-hold.

---

## 3D Overlay Holdout Validation

Split:

| Period | Dates |
|---|---|
| Reference | 2006-04-28 to 2015-12-31 |
| Holdout | 2016-01-04 to 2026-05-01 |

### Reference Period

| Strategy | CAGR | Calmar | Max DD |
|---|---:|---:|---:|
| 3D Regime Switch Overlay | 8.46% | 0.444 | -19.06% |
| SPY Buy and Hold | 6.84% | 0.124 | -55.19% |
| SPY 12M Momentum | 7.95% | 0.427 | -18.61% |
| Trend-Confirmed Allocator | 9.22% | 0.346 | -26.62% |
| Constrained Allocator | 8.67% | 0.540 | -16.06% |

Reference conclusion:

> The 3D overlay beat SPY 12M on CAGR and Calmar, but slightly lost on max drawdown: -19.06% versus -18.61%.

So it did **not** fully pass the strict SPY 12M triple gate in reference, although it was a near miss.

### Holdout Period

| Strategy | CAGR | Calmar | Max DD |
|---|---:|---:|---:|
| 3D Regime Switch Overlay | 12.06% | 0.506 | -23.83% |
| SPY Buy and Hold | 15.03% | 0.446 | -33.72% |
| SPY 12M Momentum | 11.49% | 0.341 | -33.72% |
| Trend-Confirmed Allocator | 9.40% | 0.376 | -25.02% |
| Constrained Allocator | 8.70% | 0.386 | -22.52% |

Holdout conclusion:

> The 3D overlay beat SPY 12M in holdout on CAGR, Calmar, max drawdown, volatility, Sharpe, and Sortino.

It also beat SPY buy-and-hold on every major risk-adjusted metric, while trailing it on raw CAGR.

---

## Regime Switch Overlay Validation Conclusion

| Claim | Status | Interpretation |
|---|---|---|
| Raw SPY 200D binary overlay is sufficient | Failed | Too whipsaw-prone |
| Raw SPY 200D overlay failed mainly because of whipsaw | Survived | Audit confirmed excessive boundary switching |
| 3D confirmation reduced whipsaw damage | Survived | Switches and whipsaws fell materially |
| 3D overlay beats SPY 12M full-period | Survived | Beat on return and risk metrics |
| 3D overlay beats SPY 12M in holdout | Survived | Beat on CAGR, Calmar, max DD, volatility, Sharpe, Sortino |
| 3D overlay passes strict SPY 12M triple gate in holdout | Survived | Higher CAGR, higher Calmar, better max DD |
| 3D overlay passes strict SPY 12M triple gate in reference | Failed / near miss | Slightly worse max DD than SPY 12M |
| 3D overlay beats SPY buy-and-hold on raw wealth | Failed | SPY B&H still has higher raw CAGR |
| 3D overlay is current best overall risk-adjusted candidate | Survived | Strongest current balance of CAGR, drawdown, Calmar, volatility |
| More parameter testing is justified immediately | Not yet | Overfitting risk after strong result |
| Next step should be final documentation and repository polish | Survived | Current branch has a validated checkpoint |

---

# Phase 3A: Robustness Validation

## Phase 3A Goal

Phase 3A tested whether the current best system, the **SPY Trend Regime Switch Overlay 3D Confirmed**, was fragile.

The robustness question was:

> Does the 3D overlay still work after changing realistic assumptions around trading costs, cash yield, and signal price basis?

---

## Slippage Sensitivity

| Slippage | CAGR | Calmar | Max Drawdown | Interpretation |
|---:|---:|---:|---:|---|
| 5 bps | 10.22% | 0.429 | -23.84% | Baseline |
| 10 bps | 9.93% | 0.415 | -23.91% | Passed |
| 25 bps | 9.08% | 0.376 | -24.12% | Defensive only / weakened |
| 50 bps | 7.67% | 0.304 | -25.21% | Failed as wealth-growth case |

Conclusion:

> Execution friction is the system's main vulnerability. The strategy survives low/moderate ETF-like friction, but it is not friction-proof.

---

## Cash-Yield Sensitivity

The baseline strategy earns cash returns when out of risky assets. To test whether the result was secretly powered by cash yield, the strategy was rerun with 0% cash yield.

| Scenario | CAGR | Calmar | Max Drawdown | Status |
|---|---:|---:|---:|---|
| Baseline cash yield | 10.22% | 0.429 | -23.84% | Baseline |
| 0% cash yield | 9.85% | 0.413 | -23.84% | Passed |

Conclusion:

> The 3D overlay does not depend heavily on cash yield.

---

## Raw-Close Signal Sensitivity

Because adjusted-close data is backward-adjusted, the project tested whether using raw close for SPY trend signals would break the result.

| Signal Test | Period | CAGR | Calmar | Max Drawdown | Status |
|---|---|---:|---:|---:|---|
| Adjusted-close signal | Full period | 10.22% | 0.429 | -23.84% | Baseline |
| Raw-close signal | Full period | 9.72% | 0.408 | -23.84% | Passed with caveat |
| Raw-close signal | Holdout | 11.72% | 0.492 | -23.84% | Passed |

Conclusion:

> The raw-close signal version still works, although with weaker full-period CAGR and Calmar. This supports the idea that the system is not entirely dependent on adjusted-close signal artefacts.

---

## Phase 3A Conclusion

| Claim | Status | Interpretation |
|---|---|---|
| The 3D overlay survives low/moderate slippage | Survived | 10 bps passed with 9.93% CAGR and 0.415 Calmar |
| The 3D overlay is friction-proof | Failed | 25 bps weakened the result; 50 bps failed wealth-growth |
| High execution friction is the main current vulnerability | Survived | Slippage sensitivity produced the largest degradation |
| The 3D overlay depends heavily on cash yield | Failed | 0% cash yield still passed |
| The 3D overlay survives raw-close signal sensitivity | Survived with caveat | Raw-close full-period result remained viable |
| Immediate macro/sentiment/ML expansion is justified | Not yet | Documentation and checkpoint discipline come first |

---

# Phase 3B: Controlled Asset Expansion

## Phase 3B Goal

Phase 3B tested whether adding new investable assets improves the existing portfolio-management system.

The key rule was:

> New assets are not promoted because they improve a standalone allocator. They must improve the actual 3D overlay system.

---

## USO / Oil Expansion Diagnostic

Oil was tested using `USO` as an oil proxy.

The comparison was:

```text
Base universe
vs
Base + Oil
```

### USO Allocator Impact

| Metric | Base Allocator | Base + Oil Allocator | Delta |
|---|---:|---:|---:|
| CAGR | 7.96% | 8.93% | +0.97 pts |
| Calmar | 0.280 | 0.376 | +0.096 |
| Max Drawdown | -28.42% | -23.73% | +4.69 pts |

### USO Overlay Impact

| Metric | Base 3D Overlay | Base + Oil 3D Overlay | Delta |
|---|---:|---:|---:|
| Full-period CAGR | 9.78% | 10.47% | +0.69 pts |
| Full-period Calmar | 0.335 | 0.400 | +0.065 |
| Full-period Max Drawdown | -29.18% | -26.20% | +2.98 pts |
| Holdout CAGR | 12.62% | 12.66% | +0.04 pts |
| Holdout Calmar | 0.482 | 0.483 | +0.001 |

USO allocation behaviour:

| Metric | Value |
|---|---:|
| Average USO weight | 2.563% |
| Days held | 466 |
| % days held | 9.257% |
| Final weight | 33.333% |

USO conclusion:

> Oil improved the allocator and full-period overlay, but the holdout overlay improvement was too small to validate it. USO is **promising but not validated**.

---

## ETH Quarantine Diagnostic

ETH was tested separately because its history is shorter and structurally different from the ETF universe.

ETH was capped through a crypto group cap:

```text
crypto cap = 10%
```

### ETH Overlay Impact

| Metric | Base Overlay | Base + ETH Overlay | Delta |
|---|---:|---:|---:|
| CAGR | 12.02% | 11.46% | -0.56 pts |
| Calmar | 0.459 | 0.437 | -0.022 |
| Max Drawdown | -26.20% | -26.20% | 0.00 pts |
| Volatility | Baseline | -0.21 pts | Lower, but not enough |

ETH allocation behaviour:

| Metric | Value |
|---|---:|
| Average ETH weight | 3.527% |
| Max ETH weight | 10.000% |
| Days held | 751 |
| % days held | 35.275% |
| Final weight | 0.000% |
| Dominates flag | True |

ETH conclusion:

> ETH improved allocator CAGR but worsened the actual 3D overlay. It was used often enough to matter, but it did not improve the system. ETH is **rejected** for now.

---

## Oil + ETH Combined Diagnostic

The combined `Base + Oil + ETH Quarantine` system also failed to validate.

| Metric | Base Overlay | Oil + ETH Overlay | Delta |
|---|---:|---:|---:|
| CAGR | 12.02% | 12.00% | -0.02 pts |
| Calmar | 0.459 | 0.458 | -0.001 |
| Max Drawdown | -26.20% | -26.20% | 0.00 pts |
| Volatility | Baseline | +0.31 pts | Worse |

Combined conclusion:

> Oil + ETH did not improve the overlay enough to validate inclusion. The combined expansion is **not validated**.

---

## Phase 3B Conclusion

| Expansion | Status | Interpretation |
|---|---|---|
| USO / Oil | Promising but not validated | Helped allocator and full-period overlay, failed holdout materiality |
| ETH | Rejected | Improved allocator but worsened overlay CAGR and Calmar |
| Oil + ETH | Not validated | Did not improve overlay enough to justify inclusion |

---

# Methodology Notes

## Research Period Pinning

The canonical Phase 2/3 research endpoint is pinned in configuration:

```yaml
research_period:
  phase1_start_date: "1993-01-29"
  phase2_start_date: "2006-04-28"
  end_date: "2026-05-01"
```

This was added after a data-refresh drift caused some exploratory reports to extend to 2026-05-13. The pinned endpoint prevents refreshed data from silently changing validated results.

The project now enforces this through:

- filtering each ticker's price data immediately after loading,
- filtering the dual-momentum branch separately,
- preserving filtered price data in `ticker_outputs`,
- checking generated CSV reports for `end_date > 2026-05-01`.

Canonical README numbers should be read as **2026-05-01 pinned checkpoint results**.

## Lookahead Bias Controls

- Signals are generated using only data available at the signal date.
- Execution occurs on the next trading day.
- Positions are applied after execution, not on the signal day.
- The implementation is intentionally conservative, but still needs additional dedicated lookahead audit tests before real-money interpretation.

## Cash Returns

Cash is modelled using a T-bill proxy, `^IRX`.

Important detail:

- `^IRX` is quoted as a bank discount rate.
- The project converts it into an investment yield before applying cash returns.
- Cash returns are aligned to each asset's trading calendar.
- This matters because momentum strategies spend meaningful time in cash.

## Calendar-Aware Annualisation

The framework infers periods per year from actual data frequency.

- ETFs trade on US business days.
- BTC trades every calendar day.

Using one fixed 252-day annualisation factor across all assets would distort BTC volatility, Sharpe, and cash-period returns.

## Adjusted Close Data

Data uses adjusted close prices from `yfinance`, reflecting dividends and splits through backward adjustment.

Known issue:

> Adjusted close is not perfectly point-in-time because historical prices are retroactively adjusted.

A future validation step should test raw-close signals with adjusted-close returns.

## Slippage

A flat 5 basis points slippage is applied per trade in the baseline runs.

Phase 3A tested 10 bps, 25 bps, and 50 bps sensitivity. The strategy survived 10 bps, weakened at 25 bps, and failed the wealth-growth case at 50 bps.

This is simple enough for research, but it does not fully model wider bid-ask spreads during market stress. Since regime switches happen during stressful periods, real-world friction could be materially higher than the baseline.

## Cached Data

Price and cash-rate data are cached in `data/processed/`. The loaders include schema normalisation so older cached files remain compatible after refactors.

---

# Known Limitations

This project is **not production-ready**.

Remaining concerns include:

- `yfinance` data reliability
- Adjusted-close retroactive adjustment
- Second data-source cross-check was attempted but deferred after secondary-provider ingestion issues
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
- ETH selection bias and shorter crypto history
- USO/oil result is promising but not validated
- Strategy conclusions are regime-dependent
- Investor behaviour and tracking-error regret are not directly modelled
- The 3D overlay confirmation rule was selected after auditing the full-period raw overlay
- The holdout validation is a robustness check, not a perfectly clean out-of-sample experiment
- Execution friction is the main current vulnerability
- The project is still not a production trading system

---

# Bugs Caught and Fixed

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
- Relative momentum target-weight forward-fill bug
- Missing report fixtures after adding constrained allocator
- Raw 200D regime-switch whipsaw issue diagnosed through audit
- 3D confirmation logic added after whipsaw audit
- Relative momentum allocator forward-fill exposure bug fixed
- Raw-close signal sensitivity added after adjusted-close concern
- Endpoint drift to 2026-05-13 diagnosed and fixed with `research_period.end_date`
- Dual-momentum branch endpoint bypass fixed
- Duplicate `cash_returns` return-key issue fixed
- Secondary data-source cross-check deferred after ingestion/parsing failure

---

# Project Structure

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

# Installation

```bash
git clone <your-repo-url>
cd Market-strats-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

---

# Running the Project

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

# Key Reports Generated

The framework writes outputs to `reports/`.

## Phase 1 Final Reports

```text
reports/final_strategy_decision_report.csv
reports/final_strategy_decision_report.md
reports/finalist_holdout_validation.csv
reports/finalist_holdout_validation_summary.csv
reports/finalist_holdout_validation.md
reports/final_validation_conclusion.csv
reports/final_validation_conclusion.md
```

## Phase 2 Relative Momentum Reports

```text
reports/relative_momentum_variant_decision_report.csv
reports/relative_momentum_variant_decision_report.md
reports/relative_momentum_holdout_validation.csv
reports/relative_momentum_holdout_validation_summary.csv
reports/relative_momentum_holdout_validation.md
reports/relative_momentum_validation_conclusion.csv
reports/relative_momentum_validation_conclusion.md
reports/relative_momentum_regime_diagnostic.csv
reports/relative_momentum_regime_summary.csv
reports/relative_momentum_regime_diagnostic.md
```

## Regime Switch Overlay Reports

```text
reports/regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv
reports/regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_mode_summary.csv
reports/regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_rolling_summary.csv
reports/regime_switch_overlay_audit.csv
reports/regime_switch_overlay_audit_summary.csv
reports/regime_switch_overlay_decision_report.csv
reports/regime_switch_overlay_claim_report.csv
reports/regime_switch_overlay_holdout_validation.csv
reports/regime_switch_overlay_holdout_validation_summary.csv
reports/regime_switch_overlay_validation_conclusion.csv
reports/regime_switch_overlay_current_winners.csv
```

## Phase 3A Robustness Reports

```text
reports/regime_switch_overlay_slippage_sensitivity.csv
reports/regime_switch_overlay_slippage_sensitivity_summary.csv
reports/regime_switch_overlay_cash_sensitivity.csv
reports/regime_switch_overlay_cash_sensitivity_summary.csv
reports/regime_switch_overlay_raw_close_signal_sensitivity.csv
reports/regime_switch_overlay_raw_close_signal_sensitivity_summary.csv
reports/phase3a_robustness_conclusion.csv
reports/phase3a_robustness_current_status.csv
```

## Phase 3B Asset Expansion Reports

```text
reports/asset_expansion_diagnostic_metrics.csv
reports/asset_expansion_diagnostic_allocation_summary.csv
reports/asset_expansion_diagnostic_decision.csv
reports/asset_expansion_conclusion.csv
reports/eth_quarantine_diagnostic_metrics.csv
reports/eth_quarantine_diagnostic_allocation_summary.csv
reports/eth_quarantine_diagnostic_decision.csv
```

## Other Important Reports

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

# Current Configuration Overview

The main config currently tests:

- SPY, QQQ, IWM, EFA, EEM, GLD, SLV, DBC, USO, TLT, AGG, VNQ, BTC-USD, ETH-USD
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
- Relative momentum tactical allocators
- Trend-confirmed relative momentum allocators
- Constrained relative momentum allocators
- Relative momentum holdout validation
- Relative momentum regime diagnostics
- Regime-switch overlays
- Regime-switch whipsaw audits
- Regime-switch holdout validation
- Regime-switch slippage sensitivity
- Regime-switch cash-yield sensitivity
- Raw-close signal sensitivity
- Controlled USO/oil asset expansion diagnostic
- ETH quarantine diagnostic
- Endpoint-pinned research-period validation
- Final decision reports
- Validation conclusion reports

See:

```text
configs/spy_sma10.yaml
```

---

# Research Phase Status

| Branch | Status |
|---|---|
| SPY buy-and-hold | Raw wealth benchmark |
| SPY 12M momentum | Survived as defensive timing benchmark |
| Annual core-satellite | Survived as behavioural/regime compromise |
| 50/30/20 multi-asset portfolio | Survived as capital preservation |
| 70/20/10 and 80/10/10 portfolios | Failed as wealth-growth replacements |
| EFA 200D SMA | Survived as validated EFA-specific signal |
| EFA 10M SMA | Failed as return-enhancing monthly signal |
| Drawdown tranche | Failed |
| Dual momentum | Risk-control only, too much opportunity cost |
| Plain relative momentum allocator | Failed baseline |
| Trend-confirmed relative momentum allocator | Survived as best standalone balanced allocator |
| Constrained trend-confirmed allocator | Survived as best standalone defensive allocator |
| Raw SPY 200D regime switch overlay | Failed due to whipsaw |
| SPY 3D confirmed regime switch overlay | Current best overall risk-adjusted candidate |
| BTC | Quarantined |
| USO / oil expansion | Promising but not validated |
| ETH quarantine | Rejected |
| Oil + ETH combined expansion | Not validated |
| Phase 3A robustness | Complete |
| Research endpoint pinning | Fixed at 2026-05-01 |

---

# What Should Happen Next

Do **not** keep adding strategy variants immediately.

The correct next step is repository and documentation polish:

1. Ensure all tests pass.
2. Ensure `ruff` passes.
3. Update `README.md`.
4. Push the cleaned checkpoint to GitHub.
5. Tag this as the current validated research checkpoint.

Future research branches should be opened only after this checkpoint is documented.

Potential future branches:

1. Tax-aware analysis
2. Dynamic execution-cost model using stress/slippage assumptions
3. Second data-source cross-check with a more reliable ingestion path
4. Expanded walk-forward validation
5. Bootstrap confidence intervals
6. Behavioural/tracking-error regret analysis
7. BTC-specific quarantined research branch
8. Additional commodity or real-asset expansion only under strict holdout materiality gates
9. Sentiment/macro/ML layer, but only after the current price/risk system is documented
10. Production-readiness audit, if the project ever moves beyond research

---

# Final Conclusion

This project moved from simple backtesting to a structured research framework.

The final answer is not:

> We found the perfect strategy.

The real answer is:

> Simple systematic rules can improve the path of returns, but the winner depends on objective and regime.

The current best result is:

> **SPY Trend Regime Switch Overlay 3D Confirmed** is the best overall risk-adjusted system built so far.

It beats SPY 12M on full-period and holdout risk-adjusted performance, including holdout CAGR, Calmar, and max drawdown.

But:

> SPY buy-and-hold remains the raw wealth winner.

The current checkpoint also shows:

- the 3D overlay survives low/moderate slippage,
- the system is not dependent on cash yield,
- raw-close signal testing passes with caveat,
- USO/oil is promising but not validated,
- ETH is rejected,
- oil + ETH is not validated,
- all canonical results are pinned to 2026-05-01.

That distinction is the whole point of the project.
