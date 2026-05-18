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

The project now has several completed research phases:

| Phase | Focus | Status |
|---|---|---|
| Phase 1 | Single-asset ETF timing, SPY strategies, core-satellite structures, cross-asset classification | Complete |
| Phase 2 | Tactical relative-momentum allocation and regime-switch portfolio management | Validated checkpoint reached |
| Phase 3A | Robustness checks for the 3D confirmed regime-switch overlay | Complete |
| Phase 3B | Controlled asset expansion: oil and ETH quarantine diagnostics | Oil promising but not validated; ETH rejected |
| Phase 4 | Execution realism, dynamic stress slippage, switch-quality diagnostics, and guarded-switch validation | `deep_drawdown_guard` validated as execution-realistic baseline |
| Phase 5 | Breadth-confirmation diagnostics and materiality validation | Rejected for promotion |
| Phase 6 | SPY stress confirmation, offensive relief validation, and final candidate decision | `loose_relief` promoted as best execution-realistic candidate |
| Phase 7A | Final checkpoint integrity audit | Passed |
| Phase 7B | Lookahead / signal-execution audit | Passed |
| Phase 7C / 7C.2 | Secondary data-source reliability cross-check and difference attribution | Survived with caveat |
| Phase 7D | Bootstrap / statistical robustness audit | Passed |
| Phase 7E | Bootstrap stability audit across block lengths and seeds | Passed |
| Phase 7F | Rolling-window survivability audit | Failed overall; useful caveat documented |

The central conclusion is:

> No strategy dominates across all regimes on both return and risk.

However, the project identified two separate winners under different execution assumptions:

| Role | System |
|---|---|
| Original canonical risk-adjusted system | **SPY Trend Regime Switch Overlay 3D Confirmed** under flat 5 bps slippage |
| Best execution-realistic candidate | **SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief** under dynamic stress slippage |

This system keeps exposure to SPY when SPY is in a confirmed healthy trend regime and switches to a constrained tactical relative-momentum allocator after persistent trend deterioration.

It does **not** beat SPY buy-and-hold on raw terminal wealth. SPY buy-and-hold remains the raw wealth benchmark.

The original Phase 3 overlay beats SPY 12-month absolute momentum on full-period and holdout risk-adjusted performance under flat 5 bps slippage.

The final Phase 6C execution-realistic candidate also beats SPY 12M on the strict full-period triple gate and improves on the Phase 4 execution-realistic baseline, but it still does **not** beat SPY buy-and-hold on raw CAGR.

Phase 7 strengthened the checkpoint through integrity, lookahead, data-source, bootstrap, and bootstrap-stability audits. It also exposed an important limitation: rolling-window survivability failed overall, so the candidate's liveability claim must be kept narrow.

### Canonical Research Checkpoint

The canonical project endpoint is explicitly pinned:

```text
2026-05-01
```

This matters because the data cache previously refreshed to `2026-05-13` during later experiments. That refreshed run is treated as exploratory only. The official README numbers below use the pinned `2026-05-01` endpoint.

The current validated checkpoint is:

| Item | Value |
|---|---:|
| Canonical Phase 2/3/4/5/6/7 period | 2006-04-28 to 2026-05-01 |
| Raw wealth benchmark | SPY Buy & Hold |
| SPY Buy & Hold CAGR over same period | 10.90% |
| SPY Buy & Hold max drawdown | -55.19% |
| Simple defensive benchmark | SPY 12M Momentum |
| SPY 12M Momentum CAGR over same period | 9.68% |
| SPY 12M Momentum max drawdown | -33.72% |
| Original canonical overlay | SPY Trend Regime Switch Overlay 3D Confirmed |
| Original canonical overlay CAGR | 10.22% |
| Original canonical overlay Calmar | 0.429 |
| Original canonical overlay max drawdown | -23.83% / -23.84% depending report rounding |
| Validated execution-realistic baseline | 3D overlay + deep_drawdown_guard |
| Execution-realistic baseline CAGR | 9.93% |
| Execution-realistic baseline Calmar | 0.412 |
| Execution-realistic baseline max drawdown | -24.12% |
| Best execution-realistic candidate | 3D overlay + deep_drawdown_guard + loose_relief |
| Best execution-realistic candidate CAGR | 10.35% |
| Best execution-realistic candidate Calmar | 0.429 |
| Best execution-realistic candidate max drawdown | -24.12% |
| Best execution-realistic candidate end value | $71,779.16 |
| Best execution-realistic candidate metric trade count | 66 |
| Best execution-realistic candidate overlay switch count | 36 |
| Phase 7A checkpoint integrity audit | Passed |
| Phase 7B lookahead / signal-execution audit | Passed |
| Phase 7C secondary data-source audit | Survived with caveat |
| Phase 7D bootstrap robustness audit | Passed all bootstrap gates |
| Phase 7E bootstrap stability audit | Passed 9/9 bootstrap profiles |
| Phase 7F rolling-window survivability audit | Failed overall; 3Y/5Y vs SPY 12M mostly survived; 1Y and buy-and-hold rolling risk gates failed |

Strict endpoint checks are now part of the research discipline: generated reports should not contain `end_date` later than `2026-05-01` unless a deliberate new refreshed checkpoint is opened.

---

## Current Best Results

### Full-Period Comparison

Common period for the Phase 2+ system comparison:

```text
2006-04-28 to 2026-05-01
```

| Strategy | Role | End Value | CAGR | Calmar | Volatility | Max Drawdown | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| SPY Buy & Hold | Raw wealth benchmark | $79,306.63 | 10.90% | 0.197 | 19.41% | -55.19% | Highest raw terminal wealth |
| SPY 12M Absolute Momentum | Defensive timing benchmark | $63,497.24 | 9.68% | 0.287 | 15.05% | -33.72% | Strong simple benchmark |
| Top 3 Equal Weight Trend-Confirmed Relative Momentum | Best standalone balanced allocator | $58,401.74 | 9.22% | 0.317 | 16.29% | -29.06% | Useful standalone Phase 2 allocator |
| Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum | Best standalone defensive allocator | $52,197.16 | 8.61% | 0.351 | 13.35% | -24.54% | Strong defensive/liveability allocator |
| **SPY Trend Regime Switch Overlay 3D Confirmed** | **Original flat-slippage canonical system** | **$70,048.61** | **10.22%** | **0.429** | **13.58%** | **-23.84%** | **Original Phase 3 canonical system** |
| SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard | Validated execution-realistic baseline | $66,429.13 | 9.93% | 0.412 | 13.60% | -24.12% | Dynamic stress-slippage baseline |
| **SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief** | **Best execution-realistic candidate** | **$71,779.16** | **10.35%** | **0.429** | **13.50%** | **-24.12%** | **Final Phase 6C promoted candidate** |

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
| SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard | 11.62% | 0.482 | -24.12% | 13.60% |
| **SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief** | **12.05%** | **0.500** | **-24.12%** | **13.60%** |

Holdout conclusion:

> The 3D confirmed overlay beat SPY 12M in the holdout on CAGR, Calmar, max drawdown, volatility, Sharpe, and Sortino. SPY buy-and-hold still won raw CAGR, but with materially worse drawdown.

Final execution-realistic holdout conclusion:

> The Phase 6B `loose_relief` candidate improved on the Phase 4 execution-realistic baseline in the holdout, increasing CAGR from 11.62% to 12.05% and Calmar from 0.482 to 0.500, while leaving max drawdown unchanged at -24.12%.

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

The final Phase 6C candidate also uses price-derived refinements added after earlier diagnostics. It is a validated research candidate, not a production trading system.

---

## Final Project View

The project did **not** find a universal strategy that beats SPY buy-and-hold on raw wealth while also reducing drawdown.

What it found is more useful:

| Objective | Current Winner | Notes |
|---|---|---|
| Raw terminal wealth | SPY Buy and Hold | Highest raw compounding, but with the worst drawdown profile |
| Simple defensive timing benchmark | SPY 12M Absolute Momentum | Strong simple defensive benchmark |
| Highest gross SPY architecture | 60/40 Annual Rebalanced SPY Core-Satellite | Highest gross SPY architecture from Phase 1 |
| Best standalone balanced allocator | Top 3 Equal Weight Trend-Confirmed Relative Momentum | Best standalone allocator before overlay logic |
| Best standalone defensive allocator | Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum | Strongest standalone defensive/liveability allocator |
| Best overall risk-adjusted system | SPY Trend Regime Switch Overlay 3D Confirmed | Original Phase 3 canonical system under flat 5 bps slippage |
| Validated execution-realistic baseline | SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard | Validated under dynamic stress slippage; 9.93% CAGR, 0.412 Calmar, -24.12% max drawdown |
| Best execution-realistic overlay candidate | SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief | Final Phase 6C promoted candidate; 10.35% CAGR, 0.429 Calmar, -24.12% max drawdown |

Important distinction:

> The Phase 6B `loose_relief` candidate is the best execution-realistic candidate built so far. It is **not** the raw wealth winner. SPY buy-and-hold remains the raw CAGR and terminal-wealth benchmark.

The real answer is:

> Simple systematic rules can improve the path of returns, but the winner depends on objective, regime, and execution assumptions.

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
| Endpoint integrity | Whether reports are pinned to the official research date |
| Signal-execution audit | Whether signal state can be reconstructed without lookahead |
| Secondary-source reliability | Whether data-source disagreements are explained rather than ignored |
| Bootstrap robustness | Whether the candidate's risk-adjusted evidence survives return resampling |
| Bootstrap stability | Whether bootstrap conclusions survive different block lengths and seeds |
| Rolling-window survivability | Whether the strategy remains liveable across 1Y, 3Y, and 5Y windows |

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

The real SPY 12M result is not "alpha". The CAGR edge over buy-and-hold is tiny.

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

This strategy formally tested the original "buy more when it drops" idea.

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

# Phase 4: Execution Realism and Switch Quality

## Goal

Phase 4 tested whether the current best system, the **SPY Trend Regime Switch Overlay 3D Confirmed**, survives more realistic execution assumptions and whether its regime switches are genuinely adding value.

This phase was not about adding new assets, macro data, sentiment, or machine learning. It focused on the system's biggest known weakness:

> execution friction during regime switches.

---

## Phase 4A: Dynamic Stress Slippage

Phase 4A tested whether the 3D confirmed overlay survives a stress-aware execution-cost model.

The dynamic slippage model assumes:

| Market State | Overlay Slippage |
|---|---:|
| Normal regime | 5 bps |
| SPY below 200D | 15 bps |
| SPY drawdown below -10% | 25 bps |
| SPY drawdown below -20% | 50 bps |

Costs are applied only on overlay switch days.

### Result

| Scenario | CAGR | Calmar | Max Drawdown |
|---|---:|---:|---:|
| Flat 5 bps baseline | 10.22% | 0.429 | -23.84% |
| Dynamic stress slippage | 9.49% | 0.393 | -24.12% |

### Conclusion

Dynamic stress slippage reduced full-period CAGR by **0.73 percentage points** and Calmar by **0.036**.

The 3D overlay preserved its defensive profile versus SPY 12M, because Calmar and max drawdown remained materially stronger than the SPY 12M benchmark.

However, it failed the strict full-period SPY 12M triple gate because CAGR fell below SPY 12M's **9.68%** pinned benchmark.

Final Phase 4A verdict:

> Defensive profile survived, but wealth-growth edge weakened. Execution friction remained the main unresolved vulnerability.

---

## Phase 4B: Switch-Effectiveness Audit

Phase 4B tested whether individual regime switches added value versus the counterfactual of staying in the previous mode.

### Result

52 switches were audited under the dynamic stress-slippage model.

| Switch Group | Switch Count | Helped 5D % | Avg 5D Value Added |
|---|---:|---:|---:|
| All switches | 52 | 48.077% | +0.021 pts |
| 5 bps switches | 23 | 43.478% | +0.017 pts |
| 15 bps switches | 9 | 77.778% | +0.980 pts |
| 25 bps switches | 13 | 46.154% | -0.158 pts |
| 50 bps switches | 7 | 28.571% | -0.864 pts |

### Conclusion

Switch quality was weak/mixed.

The aggregate overlay remained defensively useful, but individual switch timing did not show a reliable event-level edge.

Final Phase 4B verdict:

> The system's aggregate defensive value is stronger than its event-level switch timing quality.

---

## Phase 4C: Switch-Failure Attribution

Phase 4C diagnosed where the bad switches were concentrated.

Switches were grouped by transition direction, dynamic slippage bucket, SPY drawdown bucket, and SPY distance from trend.

### Key Findings

| Bucket | Switch Count | Helped 5D % | Avg 5D Value Added |
|---|---:|---:|---:|
| Deep drawdown below -20% | 7 | 28.571% | -0.864 pts |
| 50 bps slippage | 7 | 28.571% | -0.864 pts |
| Mild drawdown -5% to -10% | 19 | 63.158% | +0.719 pts |
| Near highs 0% to -5% | 13 | 38.462% | -0.341 pts |

### Conclusion

Switch failures were concentrated enough to diagnose.

The clearest failure cluster was:

> high-friction / deep-drawdown switches.

This suggested that the system was often switching too late in deep drawdowns, when costs were highest and mean-reversion risk was elevated.

Final Phase 4C verdict:

> The switch rule is more useful during mild deterioration than during late deep-drawdown conditions.

---

## Phase 4D: Guarded Switch Diagnostic

Phase 4D tested targeted guarded switch rules derived from Phase 4C.

The main candidate was:

> **deep_drawdown_guard** — do not initiate new defensive switches when SPY is already below -20% drawdown.

### Result

| System | CAGR | Calmar | Max Drawdown | Switch Count |
|---|---:|---:|---:|---:|
| Dynamic no-guard baseline | 9.49% | 0.393 | -24.12% | 52 |
| deep_drawdown_guard | 9.93% | 0.412 | -24.12% | 46 |
| near_high_whipsaw_guard | 9.43% | 0.391 | -24.12% | 52 |
| combined guard | 9.87% | 0.409 | -24.12% | 46 |

### Conclusion

The **deep_drawdown_guard** was the best guarded-switch variant.

It improved full-period CAGR by **0.44 percentage points**, improved Calmar by **0.019**, reduced switch count from **52 to 46**, and did not worsen max drawdown.

Final Phase 4D verdict:

> deep_drawdown_guard improved the dynamic stress-slippage baseline, but was not yet ready for promotion.

---

## Phase 4E: Guard Validation and Removed-Switch Audit

Phase 4E tested whether deep_drawdown_guard improved results for the right reason.

It audited the switches removed by the guard.

### Removed Switch Summary

| Removed Switch Count | Avg Slippage | Avg SPY Drawdown | Avg 5D Value Added | 5D Helped % | Avg 20D Value Added | 20D Helped % |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 50 bps | -25.461% | -1.082 pts | 16.667% | -2.891 pts | 16.667% |

### Conclusion

The removed switches were genuinely harmful.

They occurred in deep drawdowns, carried high execution cost, and had strongly negative average value added.

Final Phase 4E verdict:

> deep_drawdown_guard improved the dynamic baseline by removing genuinely bad switches, not by randomly reducing activity.

---

## Phase 4F: Guard Promotion Validation

Phase 4F tested whether deep_drawdown_guard was robust enough to become the execution-realistic overlay candidate.

### Core Result

| System | CAGR | Calmar | Max Drawdown |
|---|---:|---:|---:|
| Dynamic no-guard baseline | 9.49% | 0.393 | -24.12% |
| Dynamic + deep_drawdown_guard | 9.93% | 0.412 | -24.12% |

### Validation Gates

| Gate | Status |
|---|---|
| Candidate beats pinned SPY 12M strict full-period triple gate | Passed |
| Candidate improves dynamic no-guard baseline | Passed |
| Candidate avoids holdout damage | Passed |
| Candidate avoids material episode-level damage | Passed |
| Candidate can be promoted to execution-realistic overlay candidate | Passed |

### Episode Validation

| Episode | Baseline CAGR / Calmar / Max DD | Guarded CAGR / Calmar / Max DD | Result |
|---|---:|---:|---|
| Crisis 2006–2010 | 7.62% / 0.401 / -18.99% | 9.49% / 0.543 / -17.49% | Improved |
| Post-crisis 2011–2015 | 7.01% / 0.362 / -19.39% | 7.01% / 0.362 / -19.39% | Unchanged |
| Bull/Covid 2016–2020 | 11.25% / 0.466 / -24.12% | 11.25% / 0.466 / -24.12% | Unchanged |
| Inflation 2021–2026 | 12.29% / 0.584 / -21.05% | 12.29% / 0.584 / -21.05% | Unchanged |

### Final Phase 4F Verdict

> deep_drawdown_guard is validated as the execution-realistic overlay candidate.

Important distinction:

| System | Role |
|---|---|
| SPY Trend Regime Switch Overlay 3D Confirmed | Original Phase 3 canonical system under flat 5 bps slippage |
| SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard | Phase 4 execution-realistic candidate under dynamic stress slippage |

The guarded version should **not** silently replace the original Phase 3 system. They answer different assumptions.

---

## Phase 4 Final Verdict

Phase 4 showed that execution friction is a real vulnerability, but also produced a targeted fix.

| System | CAGR | Calmar | Max Drawdown |
|---|---:|---:|---:|
| Flat 5 bps 3D overlay | 10.22% | 0.429 | -23.84% |
| Dynamic stress-slippage 3D overlay | 9.49% | 0.393 | -24.12% |
| Dynamic stress-slippage 3D overlay + deep_drawdown_guard | 9.93% | 0.412 | -24.12% |

Final Phase 4 conclusion:

> The original 3D overlay remains the Phase 3 canonical system. The deep_drawdown_guard variant is validated as the best execution-realistic overlay candidate.

---

# Phase 5: Breadth Confirmation Validation

## Phase 5A: Breadth Confirmation Diagnostic

Phase 5A tested whether a simple market-breadth confirmation layer could improve the Phase 4 execution-realistic candidate.

The benchmark was:

| System | CAGR | Calmar | Max Drawdown |
|---|---:|---:|---:|
| Phase 4 execution-realistic candidate | 9.93% | 0.412 | -24.12% |

Tested breadth variants:

- defensive breadth confirmation,
- offensive breadth confirmation,
- combined breadth confirmation.

### Result

| Variant | CAGR | Calmar | Max Drawdown | Holdout CAGR | Verdict |
|---|---:|---:|---:|---:|---|
| Phase 4 execution candidate | 9.93% | 0.412 | -24.12% | 11.62% | Benchmark |
| Defensive breadth confirmation | 9.99% | 0.414 | -24.12% | 11.62% | Marginal improvement |
| Offensive breadth confirmation | 9.33% | 0.386 | -24.20% | 10.52% | Rejected |
| Combined breadth confirmation | 9.39% | 0.389 | -24.20% | 10.52% | Rejected |

Phase 5A conclusion:

> Defensive breadth confirmation was marginally positive, but the improvement was too small for promotion. Offensive and combined breadth confirmation damaged performance.

---

## Phase 5B: Breadth Materiality Validation

Phase 5B tested whether the defensive breadth improvement was material or just noise.

Tested thresholds:

```text
0.33
0.50
0.67
```

### Result

| Variant | CAGR | Calmar | Max Drawdown | Holdout CAGR | Verdict |
|---|---:|---:|---:|---:|---|
| Phase 4 execution candidate | 9.93% | 0.412 | -24.12% | 11.62% | Benchmark |
| Breadth 0.33 | 9.70% | 0.402 | -24.12% | 11.22% | Worse |
| Breadth 0.50 | 9.99% | 0.414 | -24.12% | 11.62% | Tiny improvement, failed materiality |
| Breadth 0.67 | 9.93% | 0.412 | -24.12% | 11.62% | Same as benchmark |

The materiality gate required:

```text
Full CAGR improvement >= +0.15 pts
Full Calmar improvement >= +0.005
```

The best breadth result only achieved:

```text
+0.06 pts CAGR
+0.002 Calmar
```

Final Phase 5 verdict:

> Breadth confirmation is rejected for promotion. The improvement was too small and not worth adding complexity.

---

# Phase 6: Stress Confirmation and Final Candidate Decision

## Phase 6A: SPY Stress Confirmation Diagnostic

Phase 6A tested whether SPY-derived stress filters could improve the Phase 4 execution-realistic candidate.

Tested stress inputs:

- 20D realised volatility,
- 20D SPY return shock,
- SPY distance from 200D trend,
- offensive relief confirmation.

### Defensive Stress Results

| Variant | CAGR | Calmar | Max Drawdown | Verdict |
|---|---:|---:|---:|---|
| Phase 4 execution candidate | 9.93% | 0.412 | -24.12% | Benchmark |
| Defensive volatility stress | 9.25% | 0.310 | -29.83% | Rejected |
| Defensive return shock | 8.96% | 0.296 | -30.28% | Rejected |
| Defensive trend-distance stress | 9.84% | 0.408 | -24.12% | Rejected / not useful |
| Defensive composite stress | 9.81% | 0.407 | -24.12% | Rejected / not useful |

Defensive stress filters generally worsened performance and sometimes materially worsened drawdown.

### Offensive Relief Lead

| Variant | CAGR | Calmar | Max Drawdown | Holdout CAGR | Switch Count | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Offensive relief confirmation | 10.55% | 0.437 | -24.12% | 13.14% | 30 | Promising but not validated |

Phase 6A conclusion:

> Defensive stress confirmation is rejected. Offensive relief looked promising, but failed initial validation because it damaged the post-crisis 2011-2015 episode and reduced switch count too aggressively.

---

## Phase 6B: Offensive Relief Validation

Phase 6B tested whether offensive relief was genuinely useful or merely over-filtering re-entry.

Tested profiles:

| Profile | Rule Summary |
|---|---|
| `strict_relief` | vol <= 0.16, 20D return >= 0.00, trend distance >= 0.00 |
| `baseline_relief` | vol <= 0.18, 20D return >= -0.02, trend distance >= 0.00 |
| `loose_relief` | vol <= 0.20, 20D return >= -0.03, trend distance >= 0.00 |

### Result

| Variant | CAGR | Calmar | Max Drawdown | Switch Count | Gate Result |
|---|---:|---:|---:|---:|---|
| Phase 4 execution candidate | 9.93% | 0.412 | -24.12% | 46 | Benchmark |
| strict_relief | 10.20% | 0.423 | -24.12% | 30 | Failed |
| baseline_relief | 10.55% | 0.437 | -24.12% | 30 | Failed |
| loose_relief | 10.35% | 0.429 | -24.12% | 36 | Passed |

The initial Phase 6B gate logic incorrectly selected the highest headline-score candidate before checking all gates. That was fixed so every candidate is evaluated independently.

Corrected conclusion:

> `baseline_relief` remains rejected despite stronger headline CAGR because it damaged the post-crisis episode and reduced switches too aggressively. `loose_relief` passed all Phase 6B validation gates.

---

## Phase 6C: Final Candidate Decision

Phase 6C compared the final candidate set:

| Candidate | Role |
|---|---|
| SPY Buy & Hold | Raw wealth benchmark |
| SPY 12M Momentum | Simple defensive timing benchmark |
| Phase 3 flat 5 bps 3D overlay | Original canonical overlay |
| Phase 4 execution candidate | Validated execution-realistic baseline |
| Phase 6B loose_relief candidate | Enhanced execution-realistic candidate |

### Full-Period Final Comparison

| Candidate | CAGR | Calmar | Max Drawdown | End Value | Trade Count |
|---|---:|---:|---:|---:|---:|
| SPY Buy & Hold | 10.90% | 0.197 | -55.19% | $79,306.62 | 1 |
| SPY 12M Momentum | 9.68% | 0.287 | -33.72% | $63,497.30 | 17 |
| Phase 3 flat 5 bps 3D overlay | 10.22% | 0.429 | -23.84% | $70,048.61 | 52 |
| Phase 4 execution candidate | 9.93% | 0.412 | -24.12% | $66,429.13 | 46 |
| **Phase 6B loose_relief candidate** | **10.35%** | **0.429** | **-24.12%** | **$71,779.16** | **66 metric trades / 36 overlay switches** |

### Holdout Final Comparison

| Candidate | Holdout CAGR | Holdout Calmar | Holdout Max Drawdown |
|---|---:|---:|---:|
| SPY Buy & Hold | 15.03% | 0.446 | -33.72% |
| SPY 12M Momentum | 11.49% | 0.341 | -33.72% |
| Phase 3 flat 5 bps 3D overlay | 12.06% | 0.506 | -23.84% |
| Phase 4 execution candidate | 11.62% | 0.482 | -24.12% |
| **Phase 6B loose_relief candidate** | **12.05%** | **0.500** | **-24.12%** |

### Final Gates

| Gate | Status |
|---|---|
| Phase 6B candidate improves Phase 4 execution candidate full-period | Passed |
| Phase 6B candidate avoids holdout damage versus Phase 4 execution candidate | Passed |
| Phase 6B candidate avoids material episode-level damage | Passed |
| Phase 6B candidate beats pinned SPY 12M strict full-period triple gate | Passed |
| Phase 6B candidate beats SPY Buy & Hold on raw CAGR | Failed |
| Phase 3 flat 5 bps canonical overlay remains separately documented | Passed |
| Phase 6B candidate can be promoted as best execution-realistic candidate | Passed |

Final Phase 6C verdict:

> Phase 6B `loose_relief` is promoted as the best execution-realistic candidate.

Important distinction:

> The project still does **not** beat SPY Buy & Hold on raw wealth. The final promoted candidate is the best execution-realistic risk-adjusted system built so far, not a universal raw-return champion.

---

# Phase 7: Final Validation, Data Reliability, Bootstrap Robustness, and Rolling Survivability

Phase 7 did **not** add another strategy variant. It audited whether the Phase 6C checkpoint could be trusted as a research result.

The focus was:

1. internal checkpoint consistency,
2. signal/execution timing,
3. secondary data-source reliability,
4. bootstrap/statistical robustness,
5. rolling-window survivability.

Phase 7 deliberately did **not** optimise the strategy again. Its job was to narrow the claims, expose weaknesses, and decide whether the Phase 6C candidate deserved to be documented as the final research checkpoint.

---

## Phase 7A: Final Checkpoint Integrity Audit

Phase 7A checked whether the final checkpoint was internally consistent before tagging.

### Checks Performed

| Check | Result |
|---|---|
| No report endpoint drift beyond 2026-05-01 | Passed |
| All expected checkpoint reports exist | Passed |
| Final candidate headline metrics match configured checkpoint values | Passed |
| README contains final Phase 6C checkpoint story | Passed |
| Checkpoint ready to commit and tag | Passed |

### Important Trade Count Clarification

Phase 7A caught an important ambiguity:

| Concept | Value | Meaning |
|---|---:|---|
| Metric trade count | 66 | Trade count reported by the final metrics framework |
| Overlay switch count | 36 | Number of overlay regime switches in the `loose_relief` candidate |

These are not the same thing. The audit now checks them separately.

Phase 7A verdict:

> Final checkpoint integrity passed. The Phase 6C candidate metrics, endpoint pin, report existence, and README story are internally consistent.

---

## Phase 7B: Lookahead / Signal-Execution Audit

Phase 7B audited whether the final candidate’s signal and execution path could be reconstructed without obvious lookahead leakage.

### Checks Performed

| Check | Result |
|---|---|
| Required signal/execution columns exist | Passed |
| Trend SMA can be reconstructed from trailing `signal_price` | Passed |
| Raw 3D confirmation state can be reconstructed without future data | Passed |
| Switches occurred only after `trend_sma` availability | Passed |
| Slippage costs align with positive overlay turnover | Passed |
| No obvious lookahead issue found in audited final candidate | Passed |

### Key Numbers

| Audit | Result |
|---|---:|
| Trend SMA rows checked | 4,834 |
| Trend SMA mismatches | 0 |
| Trend SMA max absolute difference | 0.0 |
| Raw 3D confirmation rows checked | 5,034 |
| Raw confirmation mismatches | 0 |
| Mode switches | 36 |
| Slippage rows | 37 |
| Turnover rows | 37 |
| Slippage-without-turnover rows | 0 |

One expected diagnostic value was:

```text
positive_bps_without_cost_or_turnover_rows = 4,997
```

This is not a hidden-cost bug. It means the daily dynamic slippage schedule had a positive basis-point value on most days, but costs were only charged when turnover occurred. The important value is:

```text
slippage_without_turnover_rows = 0
```

Phase 7B verdict:

> No obvious lookahead issue was found in the audited final candidate. This strengthens the checkpoint materially, but it still does not make the system production-ready.

---

## Phase 7C: Secondary Data-Source Reliability Audit

Phase 7C compared the primary yfinance adjusted-close data against Stooq daily close data.

Stooq required API-key authentication, so the final working audit used a local environment variable:

```text
STOOQ_API_KEY
```

The key is not stored in the repository and should not be committed.

### Phase 7C Cross-Check Result

| Classification | Count |
|---|---:|
| Clean match | 4 |
| Acceptable difference | 4 |
| Review difference | 2 |
| Potential data issue | 2 |
| Authentication failures | 0 |
| Unavailable tickers | 0 |

Ticker-level classification:

| Ticker | Classification | Notes |
|---|---|---|
| QQQ | Clean match | Strong agreement |
| GLD | Clean match | Strong agreement |
| SLV | Clean match | Strong agreement |
| USO | Clean match | Strong agreement |
| SPY | Acceptable difference | Broadly aligned |
| IWM | Acceptable difference | Broadly aligned |
| EEM | Acceptable difference | Broadly aligned |
| DBC | Acceptable difference | Broadly aligned |
| EFA | Review difference | Larger CAGR divergence |
| TLT | Review difference | Distribution-sensitive ETF |
| AGG | Potential data issue | Distribution-heavy bond ETF; large CAGR divergence versus Stooq close |
| VNQ | Potential data issue | Distribution-heavy REIT ETF; large CAGR divergence versus Stooq close |

Initial Phase 7C conclusion:

> A usable secondary data-source cross-check was completed, but broad agreement did not fully pass before attribution because AGG and VNQ showed material differences and EFA/TLT required review.

That was not the end of the audit. The differences had to be attributed rather than ignored.

---

## Phase 7C.2: Secondary Source Difference Attribution

Phase 7C.2 investigated whether the Stooq/yfinance differences were true data issues or expected price-basis differences.

The main suspicion was:

> Stooq close data is not equivalent to yfinance adjusted-close total-return data, especially for distribution-heavy ETFs.

### Attribution Result

| Item | Count |
|---|---:|
| Tickers checked | 12 |
| No material data-source concern | 8 |
| Distribution / price-basis differences | 4 |
| Review differences unresolved | 0 |
| Unresolved potential data issues | 0 |

Final attribution status:

```text
Differences mostly attributable to price-basis/distributions
```

### Attribution by Ticker

| Ticker | Prior Cross-Check Classification | Attribution |
|---|---|---|
| SPY | Acceptable difference | No material data-source concern |
| QQQ | Clean match | No material data-source concern |
| IWM | Acceptable difference | No material data-source concern |
| EEM | Acceptable difference | No material data-source concern |
| GLD | Clean match | No material data-source concern |
| SLV | Clean match | No material data-source concern |
| DBC | Acceptable difference | No material data-source concern |
| USO | Clean match | No material data-source concern |
| EFA | Review difference | Likely distribution / price-basis difference |
| AGG | Potential data issue | Likely distribution / price-basis difference |
| TLT | Review difference | Likely distribution / price-basis difference |
| VNQ | Potential data issue | Likely distribution / price-basis difference |

### Phase 7C.2 Conclusion

| Claim | Status | Interpretation |
|---|---|---|
| Secondary-source differences were attributed rather than ignored | Survived | The report separates clean matches, likely price-basis differences, and unresolved issues |
| Distribution-heavy ETF differences are likely explained by price basis | Survived | EFA, AGG, TLT, and VNQ were classified as likely distribution/price-basis differences |
| No unresolved secondary-source data issues remain | Survived | No unresolved potential issues remained after attribution |
| Stooq close can fully validate yfinance adjusted-close total-return data | Failed | A close-price source cannot fully validate adjusted-close total-return data without matching adjustment methodology |
| The next step should be more strategy optimisation | Not yet | Data reliability and statistical robustness remain higher-priority than new signals |

Phase 7C final verdict:

> Secondary data-source reliability survived with caveat. Stooq confirms broad source agreement, but Stooq close is not a perfect validator of yfinance adjusted-close total-return data.

Important limitation:

> Stooq close is useful as a broad sanity check. It does **not** fully validate distribution-adjusted total-return backtests.

---

## Phase 7D: Bootstrap / Statistical Robustness Audit

Phase 7D tested whether the final Phase 6B `loose_relief` candidate remained robust under paired block bootstrap resampling of daily returns.

The audit used:

```text
500 bootstrap iterations
21-trading-day blocks
Pinned period: 2006-04-28 to 2026-05-01
```

The comparison set was:

- Phase 6B `loose_relief` candidate,
- SPY Buy & Hold,
- SPY 12M Absolute Momentum.

### Bootstrap Probability Results

| Claim | Probability | Gate | Result |
|---|---:|---:|---|
| Candidate beats SPY 12M on CAGR | 64.0% | >= 55% | Passed |
| Candidate beats SPY 12M on Calmar | 72.2% | >= 60% | Passed |
| Candidate has better max drawdown than SPY 12M | 74.0% | >= 60% | Passed |
| Candidate beats SPY Buy & Hold on CAGR | 42.0% | <= 50% hierarchy check | Passed |
| Candidate beats SPY Buy & Hold on Calmar | 77.8% | >= 60% | Passed |
| Candidate has better max drawdown than SPY Buy & Hold | 92.2% | >= 70% | Passed |

### Distribution Summary

| Metric | Candidate | SPY Buy & Hold | SPY 12M |
|---|---:|---:|---:|
| Mean CAGR | 10.42% | 10.88% | 9.70% |
| Median CAGR | 10.36% | 10.91% | 9.65% |
| Mean Calmar | 0.405 | 0.304 | 0.340 |
| Median Calmar | 0.366 | 0.283 | 0.312 |
| Mean max drawdown | -28.57% | -40.01% | -32.30% |
| Median max drawdown | -27.81% | -38.70% | -31.18% |

### Phase 7D Verdict

> The final candidate survived bootstrap robustness versus SPY 12M and preserved its risk-adjusted advantage versus SPY Buy & Hold.

However:

> The bootstrap did not justify replacing SPY Buy & Hold as the raw wealth benchmark.

The correct interpretation is:

> Bootstrap supports the final candidate's risk-adjusted edge, but it does not statistically prove the strategy and does not guarantee future performance.

---

## Phase 7E: Bootstrap Stability Audit

Phase 7E tested whether the Phase 7D bootstrap conclusion depended on one specific resampling setup.

The audit reran the paired block bootstrap across:

```text
block lengths: 5, 21, 63 trading days
random seeds: 7, 42, 123
bootstrap profiles: 9 total
iterations per profile: 300
```

### Bootstrap Stability Result

| Profile Group | Result |
|---|---:|
| Total bootstrap profiles | 9 |
| Profiles passing all gates | 9 |
| Profiles failing any gate | 0 |

### Probability Stability Summary

| Claim | Min Probability | Mean Probability | Max Probability | Result |
|---|---:|---:|---:|---|
| Candidate beats SPY 12M on CAGR | 59.67% | 63.70% | 68.33% | Passed |
| Candidate beats SPY 12M on Calmar | 67.67% | 72.78% | 77.00% | Passed |
| Candidate has better max drawdown than SPY 12M | 70.67% | 74.48% | 78.33% | Passed |
| Candidate beats SPY Buy & Hold on CAGR | 36.67% | 41.41% | 49.67% | Passed hierarchy check |
| Candidate beats SPY Buy & Hold on Calmar | 73.33% | 77.52% | 80.67% | Passed |
| Candidate has better max drawdown than SPY Buy & Hold | 92.33% | 93.30% | 94.33% | Passed |

### Phase 7E Verdict

> The Phase 7D bootstrap conclusion was stable across tested block lengths and random seeds.

The weakest buy-and-hold CAGR hierarchy profile was close to the gate:

```text
max probability candidate beats SPY Buy & Hold CAGR = 49.67%
gate = must remain <= 50%
```

That means the hierarchy survived, but the result should not be oversold. The final candidate remains a risk-adjusted candidate, not a raw-CAGR replacement for buy-and-hold.

---

## Phase 7F: Rolling-Window Survivability Audit

Phase 7F tested whether the final Phase 6B loose_relief candidate remained liveable across rolling 1Y, 3Y, and 5Y windows.

This audit used the Phase 7D input-return series and compared:

- the final Phase 6B loose_relief candidate,
- SPY Buy & Hold,
- SPY 12M Absolute Momentum.

### Rolling-Window Gate Result

| Window | Result | Interpretation |
|---|---|---|
| 1Y | Failed | Candidate did not consistently beat SPY 12M or Buy & Hold on short-window Calmar/drawdown |
| 3Y vs SPY 12M | Passed | Candidate beat SPY 12M on 3Y Calmar and drawdown often enough |
| 5Y vs SPY 12M | Passed | Candidate beat SPY 12M on 5Y Calmar and drawdown often enough |
| 3Y/5Y vs Buy & Hold | Failed | Candidate did not clear the rolling buy-and-hold risk gates |
| Worst 3Y/5Y CAGR | Passed | Candidate avoided negative worst rolling 3Y and 5Y CAGR windows |

### Key Rolling-Window Results

| Metric | 1Y | 3Y | 5Y |
|---|---:|---:|---:|
| Candidate beats SPY 12M on CAGR | 39.87% | 64.01% | 73.67% |
| Candidate beats SPY 12M on Calmar | 36.13% | 68.26% | 73.80% |
| Candidate beats SPY 12M on max drawdown | 37.26% | 65.46% | 69.77% |
| Candidate beats Buy & Hold on CAGR | 19.86% | 19.21% | 16.34% |
| Candidate beats Buy & Hold on Calmar | 20.82% | 37.91% | 52.45% |
| Candidate beats Buy & Hold on max drawdown | 39.35% | 61.53% | 67.52% |

### Worst Rolling Windows

| Window | Worst Candidate CAGR | Window |
|---|---:|---|
| 1Y | -15.42% | 2022-01-05 to 2023-01-05 |
| 3Y | 1.45% | 2017-03-17 to 2020-03-18 |
| 5Y | 1.73% | 2015-03-19 to 2020-03-19 |

### Phase 7F Verdict

> Rolling-window survivability failed overall.

The final candidate is not consistently superior across short rolling windows, and it does not reliably beat SPY Buy & Hold on rolling risk metrics.

However, the result is not a full strategy rejection. The candidate still preserved positive worst rolling 3Y and 5Y CAGR and retained a stronger 3Y/5Y profile versus SPY 12M.

The correct interpretation is:

> The final candidate has strong full-period, bootstrap, and medium/long-horizon evidence, but short-window liveability is mixed and should not be oversold.

---

# Methodology Notes

## Research Period Pinning

The canonical Phase 2/3/4/5/6/7 research endpoint is pinned in configuration:

```yaml
research_period:
  phase1_start_date: "1993-01-29"
  phase2_start_date: "2006-04-28"
  end_date: "2026-05-01"
```

This was added after a data-refresh drift caused some exploratory reports to extend to `2026-05-13`. The pinned endpoint prevents refreshed data from silently changing validated results.

Canonical README numbers should be read as **2026-05-01 pinned checkpoint results**.

## Lookahead Bias Controls

- Signals are generated using only data available at the signal date.
- Execution occurs on the next trading day.
- Positions are applied after execution, not on the signal day.
- Phase 7B reconstructed the trend SMA and raw 3D confirmation signal from trailing data and found zero mismatches.
- Phase 7B found no obvious lookahead issue in the audited final candidate.

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

The project ran raw-close signal sensitivity and a secondary-source comparison against Stooq close data.

The secondary-source audit found:

- broad agreement for most tickers,
- no unresolved source issues after attribution,
- larger differences in distribution-sensitive ETFs,
- Stooq close is not a full validator of yfinance adjusted-close total-return data.

## Slippage

A flat 5 basis points slippage is applied per trade in the baseline runs.

Phase 3A tested 10 bps, 25 bps, and 50 bps sensitivity. The strategy survived 10 bps, weakened at 25 bps, and failed the wealth-growth case at 50 bps.

Phase 4 introduced dynamic stress slippage, charging higher costs during deteriorating or stressed markets.

This is more realistic than a flat 5 bps assumption, but it still does not fully model bid-ask spreads, market impact, taxes, fund-level liquidity, or broker-specific execution.

## Cached Data

Price and cash-rate data are cached in `data/processed/`. The loaders include schema normalisation so older cached files remain compatible after refactors.

## Secondary Data-Source API Key

Phase 7C uses Stooq as a secondary data source.

Stooq requires API-key authentication for CSV downloads. The project expects the key through a local environment variable:

```text
STOOQ_API_KEY
```

The key should live in `.env` or the local shell environment, not in committed config files.

`.env` must remain ignored by Git.

---

# Known Limitations

This project is **not production-ready**.

Remaining concerns include:

- `yfinance` data reliability,
- adjusted-close retroactive adjustment,
- Stooq close is not a full adjusted-close total-return validator,
- no tax modelling,
- no bid-ask spread modelling during stress periods,
- no market-impact modelling,
- no FX cost modelling for non-USD investors,
- cash proxy may overstate retail-accessible yields,
- no bootstrap confidence intervals yet,
- no multiple-comparisons correction across strategy/asset combinations,
- no full walk-forward optimisation framework,
- limited out-of-sample testing,
- asset universe selection bias,
- BTC selection bias,
- ETH selection bias and shorter crypto history,
- USO/oil result is promising but not validated,
- strategy conclusions are regime-dependent,
- investor behaviour and tracking-error regret are not directly modelled,
- the 3D overlay confirmation rule was selected after auditing the full-period raw overlay,
- the holdout validation is a robustness check, not a perfectly clean out-of-sample experiment,
- execution friction is the main current vulnerability,
- dynamic stress slippage showed that execution friction can remove the 3D overlay's full-period CAGR edge over SPY 12M,
- breadth confirmation was tested and rejected for promotion after failing materiality validation,
- defensive SPY stress filters were tested and rejected after weakening performance or worsening drawdown,
- offensive relief improved the execution-realistic candidate, but remains a price-derived timing refinement, not proof of production readiness,
- Phase 6B `loose_relief` is the best execution-realistic candidate built so far, but it still trails SPY Buy & Hold on raw CAGR,
- Phase 7B found no obvious lookahead issue, but that does not prove the system is live-trading ready,
- Phase 7C attributed secondary-source differences, but Stooq close cannot fully validate yfinance adjusted-close total-return series,
- Phase 7D/7E bootstrap robustness passed, but bootstrap resampling is still not formal statistical proof and does not guarantee future performance,
- Phase 7F rolling-window survivability failed overall, meaning the final candidate has mixed short-window liveability and should not be described as consistently superior across all rolling windows.
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
- Phase 6B offensive-relief gate logic initially selected the highest headline-score candidate before checking all validation gates; fixed to evaluate all candidates independently and select the best passing candidate
- Phase 7A separated metric trade count from overlay switch count
- Phase 7B confirmed trend SMA and raw confirmation state could be reconstructed without mismatches
- Phase 7C fixed Stooq CSV authentication handling and API-key environment-variable support
- Phase 7C.2 attributed Stooq/yfinance differences to price-basis/distribution treatment rather than leaving them as unresolved source failures

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

Load local `.env` variables in PowerShell when running Stooq-authenticated data checks:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match "^\s*([^#][^=]+)=(.*)$") { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") } }
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

## Phase 4 Execution Realism Reports

```text
reports/regime_switch_overlay_dynamic_slippage_sensitivity.csv
reports/phase4_execution_realism_conclusion.csv
reports/regime_switch_overlay_trade_event_audit.csv
reports/regime_switch_overlay_switch_effectiveness_summary.csv
reports/regime_switch_overlay_switch_failure_attribution.csv
reports/regime_switch_overlay_guarded_switch_metrics.csv
reports/regime_switch_overlay_guard_validation_removed_switch_summary.csv
reports/regime_switch_overlay_guard_promotion_metrics.csv
reports/regime_switch_overlay_guard_promotion_gate_report.csv
reports/phase4f_guard_promotion_conclusion.csv
```

## Phase 5 Breadth Confirmation Reports

```text
reports/regime_switch_overlay_breadth_confirmation_metrics.csv
reports/regime_switch_overlay_breadth_confirmation_summary.csv
reports/regime_switch_overlay_breadth_confirmation_gate_report.csv
reports/phase5a_breadth_confirmation_conclusion.csv
reports/regime_switch_overlay_breadth_materiality_metrics.csv
reports/regime_switch_overlay_breadth_materiality_summary.csv
reports/regime_switch_overlay_breadth_materiality_gate_report.csv
reports/phase5b_breadth_materiality_conclusion.csv
```

## Phase 6 Stress / Relief / Final Candidate Reports

```text
reports/regime_switch_overlay_stress_confirmation_metrics.csv
reports/regime_switch_overlay_stress_confirmation_summary.csv
reports/regime_switch_overlay_stress_confirmation_gate_report.csv
reports/phase6a_stress_confirmation_conclusion.csv
reports/regime_switch_overlay_offensive_relief_metrics.csv
reports/regime_switch_overlay_offensive_relief_summary.csv
reports/regime_switch_overlay_offensive_relief_gate_report.csv
reports/phase6b_offensive_relief_conclusion.csv
reports/final_candidate_comparison.csv
reports/final_candidate_delta_vs_benchmarks.csv
reports/final_candidate_gate_report.csv
reports/final_project_decision.csv
reports/final_candidate_decision.md
```

## Phase 7 Integrity / Lookahead / Data Reliability / Robustness Reports

```text
reports/final_checkpoint_integrity_conclusion.csv
reports/final_checkpoint_claim_audit.csv
reports/report_endpoint_audit.csv
reports/expected_report_audit.csv
reports/readme_checkpoint_audit.csv
reports/lookahead_required_column_audit.csv
reports/lookahead_trend_sma_audit.csv
reports/lookahead_confirmation_reconstruction_audit.csv
reports/lookahead_switch_timing_audit.csv
reports/lookahead_slippage_turnover_audit.csv
reports/lookahead_signal_execution_conclusion.csv
reports/lookahead_signal_execution_audit.md
reports/secondary_data_source_cross_check_v2.csv
reports/secondary_data_source_cross_check_v2_summary.csv
reports/secondary_data_source_cross_check_v2_conclusion.csv
reports/secondary_data_source_cross_check_v2.md
reports/secondary_data_source_difference_basis_comparison.csv
reports/secondary_data_source_difference_attribution.csv
reports/secondary_data_source_difference_attribution_summary.csv
reports/secondary_data_source_difference_attribution_conclusion.csv
reports/secondary_data_source_difference_attribution.md
reports/phase7d_bootstrap_input_returns.csv
reports/phase7d_bootstrap_samples.csv
reports/phase7d_bootstrap_distribution_summary.csv
reports/phase7d_bootstrap_probability_report.csv
reports/phase7d_bootstrap_gate_report.csv
reports/phase7d_bootstrap_conclusion.csv
reports/phase7d_bootstrap_statistical_robustness.md
reports/phase7e_bootstrap_stability_profiles.csv
reports/phase7e_bootstrap_stability_probability_summary.csv
reports/phase7e_bootstrap_stability_gate_report.csv
reports/phase7e_bootstrap_stability_conclusion.csv
reports/phase7e_bootstrap_stability.md
reports/phase7f_rolling_window_metrics.csv
reports/phase7f_rolling_window_survivability_summary.csv
reports/phase7f_rolling_window_worst_windows.csv
reports/phase7f_rolling_window_gate_report.csv
reports/phase7f_rolling_window_conclusion.csv
reports/phase7f_rolling_window_survivability.md
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
- Dynamic stress-slippage execution realism diagnostics
- Switch-effectiveness audits
- Switch-failure attribution
- `deep_drawdown_guard` validation
- Breadth-confirmation diagnostics
- Breadth materiality validation
- SPY stress-confirmation diagnostics
- Offensive relief validation
- Final candidate comparison and promotion decision
- Final checkpoint integrity audit
- Lookahead / signal-execution audit
- Secondary data-source cross-check
- Secondary source difference attribution
- Bootstrap robustness audit
- Bootstrap stability audit
- Rolling-window survivability audit
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
| SPY 3D confirmed regime switch overlay | Original Phase 3 flat-slippage canonical system |
| SPY 3D confirmed regime switch overlay + deep_drawdown_guard + loose_relief | Best execution-realistic candidate |
| BTC | Quarantined |
| USO / oil expansion | Promising but not validated |
| ETH quarantine | Rejected |
| Oil + ETH combined expansion | Not validated |
| Phase 3A robustness | Complete |
| Research endpoint pinning | Fixed at 2026-05-01 |
| Phase 4A dynamic stress slippage | Completed — defensive profile survived, wealth-growth edge weakened |
| Phase 4B switch-effectiveness audit | Completed — switch quality was weak/mixed |
| Phase 4C switch-failure attribution | Completed — failures concentrated in high-friction/deep-drawdown switches |
| Phase 4D guarded switch diagnostic | Completed — `deep_drawdown_guard` improved dynamic baseline |
| Phase 4E guard validation | Completed — removed switches were genuinely harmful |
| Phase 4F guard promotion validation | Completed — `deep_drawdown_guard` validated as execution-realistic overlay candidate |
| Phase 5A breadth confirmation | Completed — defensive breadth was marginally positive; offensive and combined breadth rejected |
| Phase 5B breadth materiality validation | Completed — breadth confirmation failed stricter materiality gates and was rejected for promotion |
| Phase 6A stress confirmation | Completed — defensive stress filters rejected; offensive relief identified as promising but not validated |
| Phase 6B offensive relief validation | Completed — `loose_relief` passed validation gates; `baseline_relief` rejected despite stronger headline CAGR |
| Phase 6C final candidate decision | Completed — `loose_relief` promoted as best execution-realistic candidate |
| Phase 7A final checkpoint integrity audit | Completed — passed |
| Phase 7B lookahead / signal-execution audit | Completed — passed |
| Phase 7C secondary data-source cross-check | Completed — usable cross-check survived, but raw agreement needed attribution |
| Phase 7C.2 secondary source difference attribution | Completed — no unresolved source issues remained; Stooq close cannot fully validate adjusted-close data |
| Phase 7D bootstrap/statistical robustness audit | Completed — final candidate passed all bootstrap gates; SPY Buy & Hold remained raw wealth benchmark |
| Phase 7E bootstrap stability audit | Completed — all 9 bootstrap profiles passed across block lengths 5/21/63 and seeds 7/42/123 |
| Phase 7F rolling-window survivability audit | Completed — failed overall; 3Y/5Y versus SPY 12M mostly survived, but 1Y and buy-and-hold rolling risk gates failed |
---

# What Should Happen Next

Do **not** add more strategy variants immediately.

The correct next step is repository and documentation checkpointing:

1. Ensure all tests pass.
2. Ensure `ruff` passes.
3. Confirm `.env` is ignored and no API key is staged.
4. Commit the Phase 7A–7F validation/audit work.
5. Tag this as the current validated research checkpoint.
6. Freeze this branch before opening any new research branch.

The current checkpoint should be documented as:

> Final Phase 6B `loose_relief` candidate promoted as the best execution-realistic risk-adjusted candidate, with Phase 7A–7E strengthening the checkpoint and Phase 7F narrowing the liveability claim.

The key caveat is:

> Rolling-window survivability failed overall. The candidate is not consistently superior across short rolling windows and does not reliably beat SPY Buy & Hold on rolling risk metrics.

Future research branches should be opened only after this checkpoint is committed and tagged.

Potential future branches:

1. Tax-aware analysis
2. More realistic bid-ask / market-impact modelling during stress
3. Expanded walk-forward validation
4. Multiple-comparisons correction across strategy/asset combinations
5. Behavioural/tracking-error regret analysis
6. BTC-specific quarantined research branch
7. Additional commodity or real-asset expansion only under strict holdout materiality gates
8. Sentiment/macro/ML layer, but only after the final price/risk system is checkpointed
9. Production-readiness audit, if the project ever moves beyond research

Do **not** treat the failed Phase 7F rolling-window audit as an invitation to tune more thresholds. That would be overfitting. The failed audit is part of the final result.

---

# Final Conclusion

This project moved from simple backtesting to a structured research framework.

The final answer is not:

> We found the perfect strategy.

The real answer is:

> Simple systematic rules can improve the path of returns, but the winner depends on objective, regime, and execution assumptions.

The current final hierarchy is:

| Role | Winner |
|---|---|
| Raw wealth benchmark | SPY Buy & Hold |
| Simple defensive timing benchmark | SPY 12M Momentum |
| Original flat-slippage canonical overlay | SPY Trend Regime Switch Overlay 3D Confirmed |
| Validated execution-realistic baseline | SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard |
| Best execution-realistic candidate | SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief |
| Bootstrap robustness status | Phase 7D passed |
| Bootstrap stability status | Phase 7E passed |
| Rolling-window survivability status | Phase 7F failed overall; mixed liveability |

The best execution-realistic candidate is:

> **SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief**

Final pinned result:

| Metric | Value |
|---|---:|
| Period | 2006-04-28 to 2026-05-01 |
| End Value | $71,779.16 |
| CAGR | 10.35% |
| Calmar | 0.429 |
| Max Drawdown | -24.12% |
| Metric Trade Count | 66 |
| Overlay Switch Count | 36 |

It improves the Phase 4 execution-realistic baseline:

| Metric | Phase 4 baseline | Phase 6B loose_relief |
|---|---:|---:|
| CAGR | 9.93% | 10.35% |
| Calmar | 0.412 | 0.429 |
| Max Drawdown | -24.12% | -24.12% |

It also beats SPY 12M on the pinned full-period strict risk-adjusted gate.

But:

> SPY buy-and-hold remains the raw wealth winner.

The final candidate is therefore best described as:

> **The best execution-realistic risk-adjusted candidate built so far, with mixed rolling-window liveability.**

It should **not** be described as a universally liveable system or as a raw-CAGR replacement for buy-and-hold.

The current checkpoint shows:

- the original 3D overlay survives low/moderate slippage,
- the system is not dependent on cash yield,
- raw-close signal testing passes with caveat,
- USO/oil is promising but not validated,
- ETH is rejected,
- oil + ETH is not validated,
- execution friction is a real vulnerability,
- `deep_drawdown_guard` fixes the worst deep-drawdown/high-friction switch cluster,
- breadth confirmation was tested and rejected for promotion,
- defensive stress confirmation was tested and rejected,
- `loose_relief` improves offensive re-entry discipline and is now promoted as the best execution-realistic candidate,
- Phase 7A confirmed checkpoint integrity,
- Phase 7B found no obvious lookahead issue,
- Phase 7C confirmed secondary data-source reliability survived with caveat,
- Phase 7D bootstrap robustness passed,
- Phase 7E bootstrap stability passed across tested block lengths and seeds,
- Phase 7F rolling-window survivability failed overall and narrowed the liveability claim,
- all canonical results are pinned to 2026-05-01.

That distinction is the whole point of the project.