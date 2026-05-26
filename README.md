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
| Phase 8A | Simplified tax-drag diagnostic | Survived at 20% tax proxy with caveat; 30% proxy erased SPY 12M CAGR edge |
| Phase 8B | Bid-ask / market-impact stress diagnostic | Failed configured stress gate; candidate kept Calmar/drawdown edge but lost CAGR edge versus SPY 12M under stress |
| Phase 8C | Walk-forward / expanding-window validation audit | Failed / mixed evidence; candidate stayed positive in all forward windows and retained drawdown usefulness, but failed CAGR/Calmar consistency gates |
| Phase 8D | Behavioural / tracking-error regret audit | Failed / material behavioural regret; terminal wealth versus Buy & Hold remained tolerable, but relative drawdown and worst 3Y active CAGR failed gates |
| Phase 8E | Multiple-comparisons / research-degrees-of-freedom audit | Completed — claims narrowed; 11 research branches documented, 25 failed/rejected units, promoted share 15.38% |
| Phase 8F | Boundary-control / non-production boundary audit | Completed — research-only boundary documented; 7 critical blockers and 11 total boundary items documented |
| Phase 8G | Final Phase 8 checkpoint / README consistency audit | Completed — Phase 8 checkpoint consistent; README wording, config flags, report inventory, hierarchy, dates, and caveat stack passed |
| Phase 9A | Technical indicator expansion diagnostic | Completed — diagnostic only; 94.99% indicator coverage, 25 technical regime rows, 15 underperformance cluster rows, no strategy promotion |

The central conclusion is:

> No strategy dominates across all regimes on both return and risk.

However, the project identified two separate winners under different execution assumptions:

| Role | System |
|---|---|
| Original canonical risk-adjusted system | **SPY Trend Regime Switch Overlay 3D Confirmed** under flat 5 bps slippage |
| Best execution-realistic candidate | **SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard + loose_relief** under dynamic stress slippage |

This system keeps exposure to SPY when SPY is in a confirmed healthy trend regime and switches to a constrained tactical relative-momentum allocator after persistent trend deterioration.

It does **not** beat SPY buy-and-hold on raw terminal wealth. SPY buy-and-hold remains the raw wealth benchmark.

The short canonical final-candidate label is:

> **SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief**

The final candidate remains the best execution-realistic risk-adjusted candidate built so far, with mixed rolling-window liveability, meaningful spread/impact sensitivity, mixed walk-forward evidence, material behavioural-regret risk, an explicit research-degrees-of-freedom caveat, a documented research-only/non-production boundary, diagnostic-only Phase 9A technical-regime evidence, diagnostic-only Phase 9B cluster-stability evidence, a Phase 9C pre-registered technical-rule design spec, a failed Phase 9D pre-registered technical-rule test, and a Phase 9E technical-extension closeout with no rule promotion. Phase 10A selected macro/rates/inflation as the first non-price feature family to audit, but no macro data was ingested, no model was trained, no strategy was tested, and no candidate was promoted. Phase 10B completed a macro/rates/inflation data-source leakage feasibility audit and allowed Phase 10C only as a source reliability and point-in-time alignment audit. No macro signal, strategy test, model, or candidate promotion exists yet. Phase 10C completed a macro source reliability and point-in-time alignment audit, loading and aligning UNRATE, DGS2, DGS10, and CPIAUCSL with conservative lagging. Phase 10D completed diagnostic-only macro/rates/inflation regime analysis. It found descriptive regime patterns but did not create a macro signal, allocation rule, model feature, strategy test, or candidate promotion. Phase 10E pre-registered two macro hypotheses for a possible Phase 10F test. No macro signal, allocation overlay, model feature, strategy test, or candidate promotion exists yet. Phase 10F failed: no pre-registered macro rule passed all configured gates. Macro/rates/inflation evidence remains diagnostic only; no macro signal, allocation overlay, model feature, strategy successor, or candidate promotion exists. Phase 10G closed the macro/rates/inflation extension branch without promotion. Macro evidence was feasible and diagnostically informative, but the pre-registered macro-rule test failed and no macro successor candidate exists. Phase 10H completed the final Phase 10 checkpoint. The macro/rates/inflation branch is closed without promotion: macro evidence was feasible and diagnostically informative, but the pre-registered macro-rule test failed and no macro successor candidate exists. Phase 11A completed an architecture review after both technical and macro rule-extension branches failed. Simple if/then overlays are no longer the preferred immediate next architecture; the next recommended step is a design-only regime-scoring architecture spec. Phase 11C completed a regime-scoring rulebook spec. No regime score, score weights, signal, allocation rule, strategy test, model, new data ingestion, or candidate promotion exists yet. Phase 11D completed a diagnostic-panel design for future regime-scoring work. No regime score, score weights, signal, allocation rule, strategy test, model, new data ingestion, or candidate promotion exists yet. Phase 11E completed a diagnostic-panel template implementation audit. Schema-compliant panel templates now exist, but no regime score, score weights, signal, allocation rule, strategy test, model, new data ingestion, or candidate promotion exists yet. Phase 12A/12B locked the future diagnostic score-calculation design and readiness boundary. No regime score, score value, empirical weight, signal, allocation rule, strategy test, model, new data ingestion, candidate promotion, or final-candidate change exists yet. Phase 12C/12D calculated and audited a categorical diagnostic regime score. The current diagnostic score is fragile, reflecting neutral technical evidence, neutral macro evidence, and fragile validation-risk context. This is diagnostic only and does not create a trading signal, allocation rule, strategy backtest, model, empirical weight, new data ingestion, candidate promotion, or final-candidate change. Phase 12 is closed. The project calculated, audited, interpreted, and bounded a fragile categorical diagnostic regime score. The score reflects neutral technical evidence, neutral macro evidence, and fragile validation-risk context. It remains diagnostic-only and does not create a signal, allocation rule, backtest, empirical weighting system, model, new data ingestion, candidate promotion, or final-candidate change. Any future score-to-signal work requires a separate pre-registration phase. The SPY regime-switch arc is now frozen as the baseline research framework. It produced benchmarks, validation infrastructure, friction/liveability/regret diagnostics, closeout discipline, and a fragile diagnostic score. It did not build the full intended multi-factor decision model. Phase 13A/13B therefore opened a new architecture path for technical, macro, fundamental, sentiment, dissertation-methodology, walk-forward, visual reporting, and eventual paper-trading work. Phase 13C/13D moved the multi-factor path from broad architecture into feature-source inventory and contract readiness. Technical and macro families are contract-feasible, with macro requiring strict lag/revision controls. Fundamental and sentiment are deliberately present in the roadmap but blocked until dedicated audits. No feature ingestion, feature calculation, signal, model, backtest, paper-trading deployment, candidate promotion, or final-candidate change exists yet.

SPY Buy & Hold remains the raw wealth benchmark. SPY 12M Momentum remains the simple defensive timing benchmark.

Market Strats Lab remains research-only. It is not production-ready, not live-tradable, not financial advice, and not a live-trading recommendation.

The original Phase 3 overlay beats SPY 12-month absolute momentum on full-period and holdout risk-adjusted performance under flat 5 bps slippage.

The final Phase 6C execution-realistic candidate also beats SPY 12M on the strict full-period triple gate and improves on the Phase 4 execution-realistic baseline, but it still does **not** beat SPY buy-and-hold on raw CAGR.

Phase 7 strengthened the checkpoint through integrity, lookahead, data-source, bootstrap, and bootstrap-stability audits. It also exposed an important limitation: rolling-window survivability failed overall, so the candidate's liveability claim must be kept narrow.

Phase 8A added a simplified tax-drag diagnostic. The candidate survived the benchmark 20% tax proxy versus SPY 12M on CAGR, Calmar, and max drawdown, but the CAGR edge was thin and disappeared under the harsher 30% proxy.

### Canonical Research Checkpoint

The canonical project endpoint is explicitly pinned:

```text
2026-05-01
```

This matters because the data cache previously refreshed to `2026-05-13` during later experiments. That refreshed run is treated as exploratory only. The official README numbers below use the pinned `2026-05-01` endpoint.

The current validated checkpoint is:

| Item | Value |
|---|---:|
| Canonical Phase 2+ / Phase 9A checkpoint period | 2006-04-28 to 2026-05-01 |
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
| Phase 8A simplified tax-drag diagnostic | Survived at 20% tax proxy; candidate CAGR edge over SPY 12M disappeared at 30% proxy |
| Phase 8B bid-ask / market-impact diagnostic | Failed configured stress gate; candidate CAGR fell to 8.17% under stress versus SPY 12M at 9.38%, while Calmar/drawdown edge survived |
| Phase 8C walk-forward validation audit | Failed / mixed evidence; 5 forward windows generated, candidate positive-CAGR rate 100%, but beat SPY 12M on CAGR and Calmar only 40% of windows |
| Phase 8D behavioural regret audit | Failed / material behavioural regret; terminal relative wealth vs Buy & Hold was 0.905, but relative drawdown vs Buy & Hold reached -57.38% and worst 3Y active CAGR was -18.17% |
| Phase 8E research-degrees-of-freedom audit | Completed — claims narrowed; documented 11 branches, 25 failed/rejected units, promoted share 15.38%, and preserved narrow final-candidate wording |
| Phase 8F boundary-control / non-production boundary audit | Completed — research-only boundary documented; confirmed the project is not production-ready, not a live-trading system, and not financial advice |
| Phase 8G final Phase 8 checkpoint audit | Completed — Phase 8 checkpoint consistent; required README wording passed, forbidden overclaiming phrases absent, config flags matched permanent checkpoint state, Phase 8 report artefacts present, and canonical hierarchy/dates documented |
| Phase 9A technical indicator expansion diagnostic | Completed — diagnostic only; 94.99% indicator coverage, 25 technical regime rows, 15 underperformance cluster rows, no strategy promotion |

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

### Simplified Tax-Drag Snapshot

Phase 8A applied a simple turnover-based realised-gain tax proxy at 0%, 10%, 20%, and 30%.

At the benchmark 20% tax proxy:

| Strategy | Tax Rate | CAGR | Calmar | Max Drawdown | Avg Annual Tax Drag | Trade Count |
|---|---:|---:|---:|---:|---:|---:|
| Final candidate | 20% | 9.83% | 0.386 | -25.48% | 0.4851 pts | 66 |
| SPY Buy & Hold | 20% | 10.90% | 0.197 | -55.19% | 0.0000 pts | 0 |
| SPY 12M Momentum | 20% | 9.66% | 0.286 | -33.72% | 0.0183 pts | 14 |

Tax-drag conclusion:

> The final candidate survived the simplified 20% tax-drag diagnostic, but the edge over SPY 12M was thin. At the harsher 30% proxy, final-candidate CAGR fell to 9.57% versus SPY 12M at 9.65%, so the strategy should not be described as tax-proof.


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
| Tax-drag-adjusted candidate status | Same final candidate | Survived 20% simplified tax proxy; 30% proxy erased SPY 12M CAGR edge |

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
| Tax-drag sensitivity | Whether turnover-based tax drag destroys the candidate's edge |
| Bid-ask / market-impact sensitivity | Whether spread and impact assumptions destroy the candidate's edge |
| Walk-forward evidence | Whether candidate behaviour survives sequential forward windows |
| Behavioural / tracking-error regret | Whether the strategy remains tolerable versus major benchmarks |
| Research-degrees-of-freedom discipline | Whether final claims are narrowed after many tested branches |
| Technical-regime diagnostics | Whether technical indicator clusters explain where the candidate helps or lags |

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


# Phase 8: Real-World Friction Diagnostics

Phase 8 moved beyond backtest-path validation and tested whether the final candidate remained credible under real-world friction, sequential validation, behavioural-regret, research-degrees-of-freedom, and non-production boundary audits.

This phase did **not** add a new alpha signal or optimise the `loose_relief` rule. It narrowed the already-promoted Phase 6B final candidate by testing tax-drag sensitivity, bid-ask / market-impact stress, walk-forward evidence, tracking-error regret, research flexibility, and research-only boundary discipline.

---

## Phase 8A: Simplified Tax-Drag Diagnostic

Phase 8A tested whether the final Phase 6B `loose_relief` candidate survived a simple turnover-based taxable-account drag model.

This was not a production tax engine. It did not model tax lots, wash-sale rules, dividend taxation, final liquidation, holding-period rules, jurisdiction-specific treatment, or investor-specific circumstances.

The purpose was narrower:

> Does the final candidate obviously collapse once turnover creates a simple realised-gain tax drag?

The tested tax-rate proxies were:

```text
0%, 10%, 20%, 30%
```

The benchmark gate used the 20% tax-rate proxy.

### Tax-Adjusted Metrics

| Strategy | Tax Rate | CAGR | Calmar | Max Drawdown | Avg Annual Tax Drag | Trade Count |
|---|---:|---:|---:|---:|---:|---:|
| Final candidate | 0% | 10.35% | 0.429 | -24.12% | 0.0000 pts | 66 |
| Final candidate | 10% | 10.09% | 0.407 | -24.80% | 0.2426 pts | 66 |
| Final candidate | 20% | 9.83% | 0.386 | -25.48% | 0.4851 pts | 66 |
| Final candidate | 30% | 9.57% | 0.366 | -26.16% | 0.7277 pts | 66 |
| SPY Buy & Hold | 0% | 10.90% | 0.197 | -55.19% | 0.0000 pts | 0 |
| SPY Buy & Hold | 10% | 10.90% | 0.197 | -55.19% | 0.0000 pts | 0 |
| SPY Buy & Hold | 20% | 10.90% | 0.197 | -55.19% | 0.0000 pts | 0 |
| SPY Buy & Hold | 30% | 10.90% | 0.197 | -55.19% | 0.0000 pts | 0 |
| SPY 12M Momentum | 0% | 9.68% | 0.287 | -33.72% | 0.0000 pts | 14 |
| SPY 12M Momentum | 10% | 9.67% | 0.287 | -33.72% | 0.0091 pts | 14 |
| SPY 12M Momentum | 20% | 9.66% | 0.286 | -33.72% | 0.0183 pts | 14 |
| SPY 12M Momentum | 30% | 9.65% | 0.286 | -33.72% | 0.0274 pts | 14 |

### Benchmark 20% Tax-Proxy Gate Result

| Gate | Result |
|---|---|
| Candidate beats SPY 12M after tax on CAGR | Passed |
| Candidate beats SPY 12M after tax on Calmar | Passed |
| Candidate has better after-tax max drawdown than SPY 12M | Passed |
| Candidate is not promoted as after-tax raw-CAGR winner over Buy & Hold | Passed |
| Candidate beats Buy & Hold after tax on Calmar | Passed |
| Candidate has better after-tax max drawdown than Buy & Hold | Passed |

At the 20% tax proxy:

| Comparison | Value |
|---|---:|
| Candidate minus SPY 12M CAGR | +0.17 pts |
| Candidate minus SPY 12M Calmar | +0.100 |
| Candidate drawdown advantage vs SPY 12M | +8.24 pts |
| Candidate minus Buy & Hold CAGR | -1.07 pts |
| Candidate Calmar advantage vs Buy & Hold | +0.189 |
| Candidate drawdown advantage vs Buy & Hold | +29.71 pts |

### Phase 8A Verdict

> The final candidate survived the simplified 20% tax-drag diagnostic.

At the 20% proxy, the candidate still beat SPY 12M on CAGR, Calmar, and max drawdown, while preserving SPY Buy & Hold as the raw-CAGR benchmark.

However:

> The tax-adjusted CAGR edge over SPY 12M is thin.

At the 30% tax proxy, the candidate's CAGR fell to 9.57%, slightly below SPY 12M at 9.65%. Therefore, the strategy should not be described as tax-proof.

The correct interpretation is:

> The final candidate remains credible under a simplified moderate tax-drag proxy, but tax sensitivity is now a documented implementation risk.

### Phase 8A Limitations

The tax model is deliberately simple. It does not include:

- tax-lot accounting,
- long-term versus short-term gain treatment,
- dividend taxation,
- final liquidation taxation,
- wash-sale rules,
- jurisdiction-specific tax treatment,
- account-type differences,
- investor-specific tax circumstances.

Therefore, Phase 8A should be read as a first-pass research diagnostic, not a production-grade after-tax backtest.

## Phase 8B: Bid-Ask / Market-Impact Stress Diagnostic

Phase 8B tested whether the final Phase 6B `loose_relief` candidate survived additional scenario-based spread and market-impact costs on turnover days.

This was not a production execution simulator. It did not model order books, intraday liquidity, broker routing, partial fills, fund-level liquidity, or real broker execution. It mechanically applied scenario-based spread and impact costs to turnover days.

The tested scenarios were:

| Scenario | Spread bps | Impact bps per 100% turnover | Stress multiplier | Deep-stress multiplier |
|---|---:|---:|---:|---:|
| No extra cost | 0.0 | 0.0 | 1.0 | 1.0 |
| Moderate | 2.5 | 5.0 | 2.0 | 3.0 |
| Stress | 5.0 | 10.0 | 3.0 | 5.0 |
| Severe | 10.0 | 20.0 | 4.0 | 8.0 |

### Phase 8B Metrics

| Strategy | Scenario | CAGR | Calmar | Max Drawdown | Total Turnover | Trade Count | Avg Annual Extra Drag |
|---|---|---:|---:|---:|---:|---:|---:|
| Final candidate | No extra cost | 10.35% | 0.429 | -24.12% | 93.27 | 66 | 0.00 pts |
| Final candidate | Moderate | 9.52% | 0.389 | -24.49% | 93.27 | 66 | 0.76 pts |
| Final candidate | Stress | 8.17% | 0.324 | -25.21% | 93.27 | 66 | 2.00 pts |
| Final candidate | Severe | 4.96% | 0.147 | -33.81% | 93.27 | 66 | 4.95 pts |
| SPY Buy & Hold | Stress | 10.90% | 0.198 | -55.19% | 0.00 | 0 | 0.00 pts |
| SPY 12M Momentum | Stress | 9.38% | 0.278 | -33.72% | 14.00 | 14 | 0.27 pts |

### Phase 8B Gate Result

| Gate | Result |
|---|---|
| Candidate beats SPY 12M on CAGR under stress | Failed |
| Candidate beats SPY 12M on Calmar under stress | Passed |
| Candidate has better max drawdown than SPY 12M under stress | Passed |
| Candidate does not become raw-CAGR winner over Buy & Hold | Passed |
| Candidate beats Buy & Hold on Calmar under stress | Passed |
| Candidate has better max drawdown than Buy & Hold under stress | Passed |
| Candidate CAGR degradation versus no-extra-cost case is not excessive | Failed |

### Phase 8B Verdict

> The final candidate failed the configured Phase 8B stress gate.

Under the stress scenario, final-candidate CAGR fell to 8.17% versus SPY 12M at 9.38%. The candidate still preserved better Calmar and max drawdown than SPY 12M and SPY Buy & Hold, but the wealth-growth edge versus SPY 12M did not survive added spread/impact stress.

The correct interpretation is:

> The final candidate remains a risk-adjusted path-improvement candidate, but it is meaningfully sensitive to spread/impact assumptions because its turnover is much higher than SPY 12M.

This should narrow the execution-realistic claim. It should not trigger immediate threshold tuning.

## Phase 8C: Walk-Forward / Expanding-Window Validation Audit

Phase 8C tested the final fixed Phase 6B `loose_relief` candidate across sequential forward windows after an expanding training-history period.

This was not a full prospective model-selection test. The final candidate had already been selected. The audit tested sequential robustness, not whether the rule would have been discovered in real time.

The configured structure used:

| Setting | Value |
|---|---:|
| Initial expanding-history period | 5 years |
| Forward test window | 3 years |
| Step size | 3 years |
| Minimum test length | 2 years |
| Forward windows generated | 5 |

### Phase 8C Forward-Window Summary

| Metric | Result |
|---|---:|
| Test windows | 5 |
| Candidate positive CAGR rate | 100% |
| Candidate beats SPY 12M on CAGR | 40% |
| Candidate beats SPY 12M on Calmar | 40% |
| Candidate has better drawdown than SPY 12M | 80% |
| Candidate beats Buy & Hold on CAGR | 0% |
| Candidate beats Buy & Hold on Calmar | 20% |
| Candidate has better drawdown than Buy & Hold | 60% |
| Worst candidate forward-window CAGR | 5.38% |

### Phase 8C Gate Result

| Gate | Result |
|---|---|
| Enough forward windows were generated | Passed |
| Candidate beats SPY 12M on CAGR often enough | Failed |
| Candidate beats SPY 12M on Calmar often enough | Failed |
| Candidate has better drawdown than SPY 12M often enough | Passed |
| Candidate keeps positive CAGR often enough | Passed |
| Candidate does not warrant raw-CAGR promotion over Buy & Hold | Passed |
| Candidate beats Buy & Hold on Calmar often enough | Failed |
| Candidate has better drawdown than Buy & Hold often enough | Passed |
| Worst candidate forward-window CAGR remains positive | Passed |

### Phase 8C Verdict

> Phase 8C failed / produced mixed walk-forward evidence.

The final candidate stayed positive in every forward window and preserved useful drawdown characteristics, but it did not beat SPY 12M on CAGR or Calmar often enough, and it beat Buy & Hold on Calmar in only 20% of forward windows.

Correct interpretation:

> Phase 8C narrows the validation claim. The candidate has useful path-improvement properties, but its sequential forward-window evidence is mixed and should not be described as clean prospective validation.

## Phase 8D: Behavioural / Tracking-Error Regret Audit

Phase 8D tested how painful the final Phase 6B `loose_relief` candidate would feel versus SPY Buy & Hold and SPY 12M Momentum.

This was not a new strategy and did not tune the final candidate. It measured terminal relative wealth, time spent lagging benchmarks, relative drawdown, longest lagging streaks, and rolling active underperformance.

### Phase 8D Summary

| Benchmark | Terminal Relative Wealth | Candidate CAGR | Benchmark CAGR | Candidate Minus Benchmark CAGR |
|---|---:|---:|---:|---:|
| SPY Buy & Hold | 0.905 | 10.35% | 10.90% | -0.55 pts |
| SPY 12M Momentum | 1.130 | 10.35% | 9.68% | +0.67 pts |

### Phase 8D Rolling Regret Snapshot

| Benchmark | Window | Underperformance Rate | Mean Active CAGR | Median Active CAGR | Worst Active CAGR |
|---|---:|---:|---:|---:|---:|
| SPY Buy & Hold | 1Y | 68.76% | -1.20 pts | -0.65 pts | -46.51 pts |
| SPY Buy & Hold | 3Y | 78.04% | -0.76 pts | -3.31 pts | -18.17 pts |
| SPY Buy & Hold | 5Y | 78.45% | -1.34 pts | -3.11 pts | -11.03 pts |
| SPY 12M Momentum | 1Y | 50.49% | +0.73 pts | 0.00 pts | -19.58 pts |
| SPY 12M Momentum | 3Y | 35.87% | +0.89 pts | +0.72 pts | -7.13 pts |
| SPY 12M Momentum | 5Y | 24.78% | +1.02 pts | +1.21 pts | -3.58 pts |

### Phase 8D Gate Result

| Gate | Result |
|---|---|
| Terminal relative wealth versus Buy & Hold remains tolerable | Passed |
| Time lagging Buy & Hold is not excessive | Passed |
| Relative drawdown versus Buy & Hold is not excessive | Failed |
| Longest lagging streak versus Buy & Hold is tolerable | Passed |
| Terminal relative wealth versus SPY 12M remains favourable | Passed |
| Time lagging SPY 12M is not excessive | Passed |
| 3Y rolling underperformance versus Buy & Hold is not excessive | Passed |
| Worst 3Y active CAGR versus Buy & Hold is tolerable | Failed |

### Phase 8D Verdict

> Phase 8D failed / showed material behavioural regret.

The final candidate remained favourable versus SPY 12M on terminal relative wealth and lagged SPY 12M only rarely over the full period. However, versus SPY Buy & Hold, it suffered a large relative drawdown and a poor worst 3Y active CAGR.

Correct interpretation:

> The final candidate is defensively useful, but behavioural regret versus Buy & Hold is material. Lower absolute drawdown does not automatically mean the strategy is easy to hold.

## Phase 8E: Multiple-Comparisons / Research-Degrees-of-Freedom Audit

Phase 8E documented the number of strategy families, diagnostics, branches, and caveated results that contributed to the final project state.

This was not a formal multiple-comparisons correction. Inventory counts are research-ledger units, not independent statistical trials. The purpose was to narrow the claim and prevent the final candidate from being overstated.

### Phase 8E Summary

| Metric | Result |
|---|---:|
| Research branches documented | 11 |
| Total tested units | 52 |
| Total promoted units | 8 |
| Failed/rejected units | 25 |
| Mixed/caveated units | 19 |
| Promoted share of tested units | 15.38% |
| Claim strength after audit | Narrow / heavily caveated |

### Phase 8E Gate Result

| Gate | Result |
|---|---|
| Inventory contains tested research branches | Passed |
| Failed/rejected branches are documented | Passed |
| Promoted share of tested units is not excessive | Passed |
| Multiple-comparisons caveat is produced | Passed |
| Raw wealth hierarchy is preserved | Passed |
| Final claim is narrow rather than overpromoted | Passed |

### Phase 8E Verdict

> Phase 8E completed the research-degrees-of-freedom audit and narrowed the claim.

Correct interpretation:

> The final candidate emerged after many tested branches, rejected ideas, caveated diagnostics, and validation filters. It should therefore be described as the best execution-realistic risk-adjusted candidate built so far, not as a broadly proven market-beating system.

## Phase 8F: Boundary-Control / Non-Production Boundary Audit

Phase 8F documented why Market Strats Lab remains a research-grade systematic strategy lab rather than a production trading system.

This was not a production approval. It did not make the strategy live-tradable. A pass meant the non-production boundary was documented clearly.

### Phase 8F Summary

| Metric | Result |
|---|---:|
| Total boundary items | 11 |
| Critical items | 7 |
| Major items | 4 |
| Blocker items | 7 |
| Gap items | 3 |
| Caveat items | 1 |
| Categories documented | 9 |
| Production-ready after audit | False |
| Live-trading claim | False |

### Phase 8F Boundary Categories

| Category | Items | Critical | Major | Blockers | Gaps | Caveats |
|---|---:|---:|---:|---:|---:|---:|
| Data | 2 | 2 | 0 | 2 | 0 | 0 |
| Execution | 2 | 1 | 1 | 1 | 1 | 0 |
| Tax | 1 | 1 | 0 | 1 | 0 | 0 |
| Portfolio | 1 | 0 | 1 | 0 | 1 | 0 |
| Monitoring | 1 | 1 | 0 | 1 | 0 | 0 |
| Operations | 1 | 0 | 1 | 0 | 1 | 0 |
| Validation | 1 | 0 | 1 | 0 | 0 | 1 |
| Governance | 1 | 1 | 0 | 1 | 0 | 0 |
| Compliance | 1 | 1 | 0 | 1 | 0 | 0 |

### Phase 8F Gate Result

| Gate | Result |
|---|---|
| Audit explicitly preserves non-production status | Passed |
| Audit makes no live-trading claim | Passed |
| Critical production blockers are documented | Passed |
| Data risk is documented | Passed |
| Execution risk is documented | Passed |
| Tax risk is documented | Passed |
| Operational/configuration risk is documented | Passed |
| Monitoring risk is documented | Passed |
| Human review / governance boundary is documented | Passed |
| Boundary statement is produced | Passed |

### Phase 8F Verdict

> Phase 8F documented the research-only boundary.

Correct interpretation:

> The project documented why the final candidate remains research-only and not production-ready. This is a boundary-control pass, not a production approval.



## Phase 8G: Final Phase 8 Checkpoint / README Consistency Audit

Phase 8G checked that the README, config flags, local Phase 8 report artefacts, final hierarchy, canonical dates, and research-only boundary were internally consistent after Phases 8A–8F.

This was not a strategy test and not production approval. It did not make the strategy production-ready, live-tradable, or financial advice.

### Phase 8G Audit Scope

| Check Area | Result |
|---|---|
| README contains all required Phase 8 wording | Passed |
| README contains no forbidden overclaiming phrases | Passed |
| Config flags match permanent checkpoint state | Passed |
| Expected Phase 8 report artefacts are present locally | Passed |
| Canonical hierarchy and dates are documented | Passed |
| Final candidate wording includes full caveat stack | Passed |

### Phase 8G Verdict

> Phase 8G completed the final Phase 8 checkpoint audit.

Correct interpretation:

> Phase 8G confirmed that Phase 8 is internally consistent as a research checkpoint. This closes Phase 8 documentation/config consistency, but it is not production approval and does not change the strategy hierarchy.

# Phase 9
## Phase 9A: Technical Indicator Expansion Diagnostic

Phase 9A tested whether additional price-derived technical indicators helped explain where the final candidate helped or failed.

This was diagnostic only. It did not create, tune, or promote a new trading rule.

### Phase 9A Summary

| Metric | Result |
|---|---:|
| Start date | 2006-04-28 |
| End date | 2026-05-01 |
| Rows | 5,034 |
| Indicator coverage rate | 94.99% |
| Technical regime rows | 25 |
| Underperformance cluster rows | 15 |
| Candidate underperforms Buy & Hold daily-return rate | 10.91% |
| Candidate underperforms SPY 12M daily-return rate | 11.62% |

### Phase 9A Main Diagnostic Findings

The diagnostic found that candidate underperformance versus Buy & Hold was most concentrated in intermediate drawdowns, near-long-SMA transition zones, mild drawdowns, high-volatility regimes, and overbought regimes.

The candidate’s defensive usefulness was more visible in deep bear states, below-long-SMA regimes, negative 12-month momentum regimes, and oversold regimes.

### Phase 9A Gate Result

| Gate | Result |
|---|---|
| Indicator coverage is sufficient | Passed |
| Technical regime rows were generated | Passed |
| Underperformance clusters were reported | Passed |
| Diagnostic does not promote a new strategy | Passed |
| Diagnostic role remains bounded | Passed |

### Phase 9A Verdict

> Phase 9A completed as a diagnostic-only technical indicator expansion.

Correct interpretation:

> Phase 9A produced interpretable technical-regime evidence but did not change the final candidate hierarchy. The results can inform future hypotheses, but they are not validated trading rules.

## Phase 9B: Technical Regime Cluster Stability Audit

Phase 9B tested whether the Phase 9A technical-regime clusters were stable across subperiods and episodes.

This was diagnostic only. It did not create, tune, validate, or promote a new trading rule.

### Phase 9B Summary

| Metric | Result |
|---|---:|
| Cluster episode metric rows | 110 |
| Stability rows | 25 |
| Stable across both benchmarks | 6 |
| Unstable rows | 19 |
| Instability report rows | 15 |
| Helpful stability report rows | 13 |
| Mean direction consistency vs Buy & Hold | 79.33% |
| Mean direction consistency vs SPY 12M | 61.33% |

### Phase 9B Main Diagnostic Findings

Phase 9B showed that Phase 9A’s technical-regime evidence is useful but mixed.

The most stable helpful cluster was `rsi_bucket = oversold_below_30`, which helped versus both Buy & Hold and SPY 12M with full direction consistency across covered episodes.

`long_momentum_state = negative_12m_momentum` also remained useful, especially versus SPY 12M.

However, many clusters were unstable across episodes. Only 6 of 25 stability rows were stable across both benchmarks. This means Phase 9A/9B evidence should inform future hypotheses, not directly become trading rules.

### Phase 9B Gate Result

| Gate | Result |
|---|---|
| Cluster stability rows were generated | Passed |
| Instability report was produced | Passed |
| Helpful stability report was produced | Passed |
| Diagnostic does not promote a new strategy | Passed |
| Diagnostic role remains bounded | Passed |

### Phase 9B Verdict

> Phase 9B completed as a diagnostic-only technical regime cluster stability audit.

Correct interpretation:

> Phase 9B documented which Phase 9A technical clusters were more stable or unstable across episodes. It did not validate a new trading rule and did not change the final candidate hierarchy.

## Phase 9C: Pre-Registered Technical Rule Design Spec

Phase 9C pre-registered the only technical-rule hypotheses allowed to move into a later Phase 9D test.

This was not a strategy test, not a backtest, not parameter optimisation, and not strategy promotion.

### Phase 9C Summary

| Metric | Result |
|---|---:|
| Spec role | Pre-registered design spec only |
| Proposed test phase | Phase 9D |
| Hypothesis count | 2 |
| Allowed input rows | 8 |
| Allowed inputs all registered | True |
| Forbidden keyword rows | 32 |
| Forbidden keywords absent from testable hypothesis text | True |
| Validation gate rows | 18 |
| Forbidden action rows | 6 |

### Phase 9C Hypotheses

| Hypothesis | Description |
|---|---|
| `H1_oversold_rsi_reentry_relief` | Oversold RSI re-entry relief hypothesis |
| `H2_negative_12m_momentum_defensive_confirmation` | Negative 12M momentum defensive confirmation hypothesis |

### Phase 9C Gate Result

| Gate | Result |
|---|---|
| Hypothesis count is bounded | Passed |
| Source evidence is documented | Passed |
| Allowed inputs are documented | Passed |
| Forbidden inputs are documented | Passed |
| Proposed rule logic is documented | Passed |
| Validation gates are documented | Passed |
| Failure conditions are documented | Passed |
| README wording outcomes are documented | Passed |
| Promotion constraints are documented | Passed |
| Allowed inputs stay inside registry | Passed |
| Forbidden keywords are absent from allowed hypothesis text | Passed |
| Spec does not allow strategy testing | Passed |
| Spec does not allow parameter optimisation | Passed |
| Spec does not allow strategy promotion | Passed |
| Spec role is correct | Passed |

### Phase 9C Verdict

> Phase 9C completed as a pre-registered technical rule design spec.

Correct interpretation:

> Phase 9C pre-registered the only technical-rule hypotheses allowed for a later Phase 9D test. It did not run performance tests, tune parameters, or promote a strategy.

## Phase 9D: Pre-Registered Technical Rule Test

Phase 9D tested only the two Phase 9C pre-registered technical-rule hypotheses:

1. `H1_oversold_rsi_reentry_relief`
2. `H2_negative_12m_momentum_defensive_confirmation`

This was not an open-ended indicator search. It did not add new inputs, search thresholds, or promote a strategy.

### Phase 9D Summary

| Rule | Full CAGR | Full Calmar | Result |
|---|---:|---:|---|
| H1 oversold RSI re-entry relief | 5.52% | 0.102 | Failed |
| H2 negative 12M momentum defensive confirmation | 8.66% | 0.266 | Failed |
| Baseline final candidate | 10.35% | 0.429 | Existing benchmark |

### Phase 9D Gate Result

Both pre-registered rules failed the configured validation gates. They failed on full-period CAGR, full-period Calmar, max drawdown, holdout performance, episode damage, stress-friction performance, and behavioural relative drawdown versus Buy & Hold.

The only gates they passed were discipline gates confirming that the rules were not promoted and remained bounded as candidates for further validation only.

### Phase 9D Verdict

> Phase 9D failed. No pre-registered technical rule passed.

Correct interpretation:

> Phase 9A/9B technical-regime evidence was useful diagnostically, but the two Phase 9C pre-registered rule implementations failed validation. No technical rule should be promoted or tuned around this result.

## Phase 9E: Technical Extension Closeout / Failure Documentation Audit

Phase 9E closed the Phase 9 technical-extension branch after the Phase 9D pre-registered rule test failed. 

This did not create a new rule, tune a failed rule, or promote a successor candidate.

### Phase 9E Summary

| Metric | Result |
|---|---|
| Branch | Phase 9 technical indicator extension |
| Status | Closed — no rule promoted |
| Successor candidate created | False |
| Final candidate changed | False |
| Rule promotion allowed | False |
| Next allowed step | Phase 9 final README/checkpoint consistency or pause |

### Phase 9E Gate Result

| Gate | Result |
|---|---|
| Expected Phase 9 reports are present | Passed |
| Config flags match closeout state | Passed |
| Phase 9D failure is documented | Passed |
| No Phase 9D rule passed all gates | Passed |
| No strategy promotion occurred | Passed |
| No successor candidate was created | Passed |
| Technical branch is closed without promotion | Passed |

### Phase 9E Verdict

> Phase 9E completed the technical-extension closeout audit.

Correct interpretation:

> Phase 9A/9B technical-regime evidence remained diagnostic, Phase 9C pre-registered two hypotheses, Phase 9D rejected both pre-registered rule implementations, and no technical rule was promoted.

The final candidate hierarchy is unchanged.

## Phase 9F: Final Phase 9 Checkpoint / README Consistency Audit

Phase 9F checked that the README, config flags, local Phase 9 report artefacts, final hierarchy, canonical dates, and technical-extension closeout were internally consistent after Phases 9A–9E.

This was not a strategy test and not production approval.

### Phase 9F Gate Result

| Gate | Result |
|---|---|
| README contains all required Phase 9 wording | Passed |
| README contains no forbidden overclaiming phrases | Passed |
| Config flags match permanent checkpoint state | Passed |
| Expected Phase 9 report artefacts are present locally | Passed |
| Canonical hierarchy and dates are documented | Passed |
| Phase 9 closeout is documented | Passed |
| No technical rule was promoted | Passed |
| No successor candidate was created | Passed |

### Phase 9F Verdict

> Phase 9F completed the final Phase 9 checkpoint audit.

Correct interpretation:

> Phase 9A/9B diagnostic evidence, Phase 9C pre-registration, Phase 9D failure, and Phase 9E closeout were documented consistently. No technical rule was promoted and the final candidate hierarchy remains unchanged.

# Phase 10
## Phase 10A: Feature-Family Feasibility Spec

Phase 10A evaluated which non-price feature family should enter the framework first.

This was a feasibility specification only. It did not ingest data, train a model, test a strategy, or promote a candidate.

### Phase 10A Summary

| Metric | Result |
|---|---:|
| Spec role | Feature-family feasibility spec only |
| Proposed next phase | Phase 10B |
| Feature-family count | 4 |
| Data requirement rows | 4 |
| Leakage control rows | 15 |
| Validation requirement rows | 12 |
| Scorecard rows | 4 |
| Recommended family | macro_rates_inflation |
| Matches expected first family | True |

### Phase 10A Feature-Family Ranking

| Rank | Feature family | Interpretation |
|---:|---|---|
| 1 | Macro / rates / inflation | Selected as first non-price family to audit |
| 2 | Fundamental / valuation | Future candidate; slower-moving and timing-sensitive |
| 3 | Sentiment / narrative | Future candidate; noisy and high overfit risk |
| 4 | ML / ensemble modelling | Long-term branch only; premature without clean features |

### Phase 10A Gate Result

| Gate | Result |
|---|---|
| Feature-family count is bounded | Passed |
| Recommended family matches expected first family | Passed |
| Recommended family has no active disqualifier | Passed |
| Each family documents data requirements | Passed |
| Each family documents leakage controls | Passed |
| Each family documents validation requirements | Passed |
| Scorecard exists for all families | Passed |
| Spec does not allow data ingestion | Passed |
| Spec does not allow model training | Passed |
| Spec does not allow strategy testing | Passed |
| Spec does not allow strategy promotion | Passed |
| Spec role is correct | Passed |

### Phase 10A Verdict

> Phase 10A completed as a feature-family feasibility spec.

Correct interpretation:

> Phase 10A selected macro/rates/inflation as the first non-price feature family to audit in Phase 10B. It did not ingest data, train a model, test a strategy, or promote a candidate.

## Phase 10B: Macro / Rates / Inflation Data-Source & Leakage Feasibility Audit

Phase 10B audited whether macro/rates/inflation data sources were feasible enough for a later point-in-time data-source audit.

This did not download data, engineer features, create signals, train models, test strategies, or promote candidates.

### Phase 10B Summary

| Metric | Result |
|---|---:|
| Audit role | Data-source and leakage feasibility audit only |
| Recommended family | macro_rates_inflation |
| Proposed next phase | Phase 10C |
| Source candidate count | 5 |
| Release-policy ready count | 5 |
| Revision-policy ready count | 5 |
| Leakage-controls ready count | 5 |
| Vintage-capable source count | 1 |
| Recommended source count for Phase 10C audit | 3 |

### Phase 10B Recommended Sources for Phase 10C Audit

| Source | Role |
|---|---|
| `fred_alfred_macro_vintage` | General macro / vintage-capable candidate |
| `treasury_rates_yield_curve` | Rates and yield-curve candidate |
| `bls_cpi_inflation` | Inflation candidate |

BEA growth/activity and NBER recession dates remain documented but constrained. BEA-style data has revision-treatment risk, and NBER recession dates are suitable only for ex-post labelling/diagnostics, not live decision inputs.

### Phase 10B Gate Result

| Gate | Result |
|---|---|
| Source candidate count is sufficient | Passed |
| Recommended family is macro/rates/inflation | Passed |
| No data download is allowed in Phase 10B | Passed |
| No feature engineering is allowed in Phase 10B | Passed |
| No signal creation is allowed in Phase 10B | Passed |
| No model training is allowed in Phase 10B | Passed |
| No strategy test is allowed in Phase 10B | Passed |
| No strategy promotion is allowed in Phase 10B | Passed |
| Each source has a release-date policy | Passed |
| Each source has a revision policy | Passed |
| Each source has leakage controls | Passed |
| At least one source has vintage/revision support | Passed |
| At least one rates source is present | Passed |
| At least one inflation source is present | Passed |
| No source is allowed for strategy testing now | Passed |
| Phase 10C boundary is data-audit only | Passed |
| Audit role is correct | Passed |

### Phase 10B Verdict

> Phase 10B completed as a macro/rates/inflation data-source leakage feasibility audit.

Correct interpretation:

> Phase 10B found that selected macro/rates/inflation data-source candidates are feasible enough to audit in Phase 10C. Phase 10C is allowed only as a data-source reliability and point-in-time alignment audit, not as a macro signal or strategy test.

## Phase 10C: Macro Source Reliability & Point-in-Time Alignment Audit

Phase 10C loaded/fetched selected macro/rates/inflation sources and checked source reliability, historical coverage, conservative trading-day lagging, revision/vintage risk documentation, missingness, and Phase 10D readiness.

This did not create macro signals, allocation rules, predictive model features, model training, strategy tests, or candidate promotion.

### Phase 10C Summary

| Metric | Result |
|---|---:|
| Audit role | Macro source reliability and point-in-time alignment audit only |
| Recommended family | macro_rates_inflation |
| Proposed next phase | Phase 10D |
| Selected source count | 3 |
| Series count | 4 |
| Loaded series count | 4 |
| Phase 10D ready series count | 4 |
| Phase 10D allowed | True |

### Phase 10C Loaded Series

| Series | Role | Raw rows | Aligned rows | Non-missing aligned rows |
|---|---|---:|---:|---:|
| `UNRATE` | General macro / labour proxy | 940 | 5034 | 5008 |
| `DGS2` | 2-year Treasury yield / rates proxy | 13038 | 5034 | 4961 |
| `DGS10` | 10-year Treasury yield / rates proxy | 16798 | 5034 | 4969 |
| `CPIAUCSL` | CPI / inflation proxy | 952 | 5034 | 4996 |

### Phase 10C Gate Result

| Gate | Result |
|---|---|
| Selected source count is sufficient | Passed |
| Remote/local macro series load succeeded | Passed |
| Release-date policies are documented | Passed |
| Revision/vintage policies are documented | Passed |
| Aligned series meet missingness threshold | Passed |
| Conservative trading-day lag is applied | Passed |
| Revision risk is documented for every series | Passed |
| Rates series is ready for diagnostic audit | Passed |
| Inflation series is ready for diagnostic audit | Passed |
| Macro series is ready for diagnostic audit | Passed |
| No macro signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No model feature creation is allowed | Passed |
| No model training is allowed | Passed |
| No strategy test is allowed | Passed |
| No strategy promotion is allowed | Passed |
| Phase 10D boundary is diagnostic-only | Passed |
| Enough series are ready to allow Phase 10D diagnostic-only analysis | Passed |
| Audit role is correct | Passed |

### Phase 10C Verdict

> Phase 10C completed as a macro source reliability and point-in-time alignment audit.

Correct interpretation:

> Phase 10C loaded and aligned the selected macro/rates/inflation sources with conservative trading-day lagging and documented revision risk. Phase 10D is allowed only as diagnostic macro regime analysis, not as a macro signal, model, strategy test, or candidate promotion.

## Phase 10D: Diagnostic-Only Macro Regime Analysis

Phase 10D analysed whether macro/rates/inflation regimes help explain where the final candidate behaves better or worse versus SPY Buy & Hold and SPY 12M Momentum.

This did not create macro signals, allocation rules, predictive model features, model training, strategy tests, or candidate promotion.

### Phase 10D Summary

| Metric | Result |
|---|---:|
| Diagnostic role | Diagnostic-only macro regime analysis |
| Proposed next phase | Phase 10E |
| Macro panel rows | 5,033 |
| Regime family count | 5 |
| Regime metric rows | 15 |
| Helpful regime rows | 9 |
| Weak regime rows | 4 |
| Phase 10E boundary passed | True |

### Phase 10D Diagnostic Observations

Phase 10D found that macro/rates/inflation regimes are diagnostically informative, but not strategy-promotional.

The final candidate looked comparatively more useful in several lower-rate, lower-inflation, and improving-labour-market regimes, including:

| Regime | Diagnostic interpretation |
|---|---|
| `low_short_rates_below_1_5` | Helpful versus both benchmarks on risk-adjusted / drawdown-style diagnostics |
| `low_inflation_below_2` | Helpful versus both benchmarks on risk-adjusted / drawdown-style diagnostics |
| `unemployment_falling` | Helpful versus both benchmarks |
| `normal_unemployment_4_to_6` | Helpful versus both benchmarks |
| `yield_curve_inverted` | Helpful versus both benchmarks, but must be treated cautiously because inversion regimes are economically complex |

The final candidate looked weaker or mixed in several regimes, especially:

| Regime | Diagnostic interpretation |
|---|---|
| `high_short_rates_above_4` | Weak versus both benchmarks |
| `high_unemployment_above_6` | Mixed/weak, especially versus SPY 12M |
| `unemployment_stable` | Weak versus both benchmarks on the configured weak-regime criteria |
| `low_unemployment_below_4` | Weak versus both benchmarks on the configured weak-regime criteria |

### Phase 10D Gate Result

| Gate | Result |
|---|---|
| Macro panel loaded | Passed |
| UNRATE is present | Passed |
| DGS2 is present | Passed |
| DGS10 is present | Passed |
| CPIAUCSL is present | Passed |
| Regime family count is sufficient | Passed |
| Regime metrics were generated | Passed |
| No macro signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No model feature creation is allowed | Passed |
| No model training is allowed | Passed |
| No strategy test is allowed | Passed |
| No strategy promotion is allowed | Passed |
| Phase 10E boundary is spec-only | Passed |
| Diagnostic role is correct | Passed |

### Phase 10D Verdict

> Phase 10D completed as diagnostic-only macro regime analysis.

Correct interpretation:

> Phase 10D produced macro/rates/inflation regime diagnostics that may justify pre-registering macro hypotheses in Phase 10E. It did not create a macro signal, allocation rule, model feature, strategy test, or candidate promotion.

## Phase 10E: Pre-Registered Macro Hypothesis Design Spec

Phase 10E pre-registered the only macro hypotheses allowed to move into a later Phase 10F macro-rule test.

This did not create macro signals, allocation overlays, predictive model features, model training, strategy tests, or candidate promotion.

### Phase 10E Summary

| Metric | Result |
|---|---:|
| Spec role | Pre-registered macro hypothesis design spec only |
| Proposed test phase | Phase 10F |
| Hypothesis count | 2 |
| Allowed input rows | 13 |
| Allowed inputs all registered | True |
| Forbidden input rows | 14 |
| Validation gate rows | 16 |
| Failure condition rows | 10 |

### Phase 10E Pre-Registered Hypotheses

| Hypothesis | Description | Max allowed role after Phase 10F |
|---|---|---|
| `H1_supportive_low_rate_low_inflation_relief` | Tests a fixed low-rate / low-inflation supportive macro-relief hypothesis derived from Phase 10D diagnostics | Candidate for further validation only |
| `H2_high_rate_high_unemployment_stress_guard` | Tests a fixed high-rate / high-unemployment macro stress-guard hypothesis derived from Phase 10D diagnostics | Candidate for further validation only |

### Phase 10E Gate Result

| Gate | Result |
|---|---|
| Hypothesis count is bounded | Passed |
| Source evidence is documented | Passed |
| Allowed macro inputs are documented | Passed |
| Allowed macro inputs stay inside registry | Passed |
| Forbidden inputs are documented | Passed |
| Fixed thresholds are documented | Passed |
| Validation gates are documented | Passed |
| Failure conditions are documented | Passed |
| README wording outcomes are documented | Passed |
| Phase 10F boundary is pre-registered-test only | Passed |
| Spec does not allow macro signal creation | Passed |
| Spec does not allow allocation rule creation | Passed |
| Spec does not allow model feature creation | Passed |
| Spec does not allow model training | Passed |
| Spec does not allow strategy testing | Passed |
| Spec does not allow strategy promotion | Passed |
| Spec role is correct | Passed |

### Phase 10E Verdict

> Phase 10E completed as a pre-registered macro hypothesis design spec.

Correct interpretation:

> Phase 10E pre-registered the only macro hypotheses allowed for a later Phase 10F test. It did not create a macro signal, allocation rule, model feature, strategy test, or candidate promotion.

## Phase 10F: Pre-Registered Macro Rule Test

Phase 10F tested only the two Phase 10E pre-registered macro hypotheses:

1. `H1_supportive_low_rate_low_inflation_relief`
2. `H2_high_rate_high_unemployment_stress_guard`

This did not add new inputs, thresholds, sentiment, fundamentals, ML, optimisation, or candidate promotion.

### Phase 10F Summary

| Metric | Result |
|---|---:|
| Discipline gates passed | True |
| Any rule passed | False |
| Passed rules | None |
| Strategy promotion | False |
| Verdict | Failed / no pre-registered macro rule passed |

### Phase 10F Rule Outcomes

| Rule | Result | Interpretation |
|---|---|---|
| `H1_supportive_low_rate_low_inflation_relief` | Failed | Higher CAGR but worse Calmar, worse drawdown, holdout drawdown damage, episode damage, stress-friction failure, and raw-CAGR overclaim versus Buy & Hold |
| `H2_high_rate_high_unemployment_stress_guard` | Failed | Better headline CAGR/Calmar and preserved drawdown, but failed episode damage control and stress-friction survival |

### Phase 10F Gate Interpretation

H1 failed because it improved raw return at the cost of materially worse drawdown and weaker robustness. This is not acceptable under the project’s risk-adjusted validation discipline.

H2 produced more interesting evidence, but it still failed the pre-registered episode-damage and stress-friction gates. It therefore cannot be promoted, softened, or tuned around.

### Phase 10F Verdict

> Phase 10F failed. No pre-registered macro rule passed all configured gates.

Correct interpretation:

> Phase 10F validly tested the two pre-registered macro hypotheses from Phase 10E. Neither rule passed all gates. The macro branch remains diagnostically useful, but no macro signal, allocation overlay, model feature, strategy successor, or candidate promotion exists.

## Phase 10G: Macro Branch Closeout / Failure Documentation Audit

Phase 10G closed the Phase 10 macro/rates/inflation branch after the Phase 10F pre-registered macro-rule test failed.

This was not a new strategy test. It confirmed that no macro rule was promoted, no successor candidate was created, and the final candidate hierarchy remained unchanged.

### Phase 10G Summary

| Metric | Result |
|---|---|
| Branch | Phase 10 macro/rates/inflation extension |
| Status | Closed — no macro rule promoted |
| Next allowed step | Phase 10H final Phase 10 checkpoint audit or architecture review |
| Successor candidate created | False |
| Final candidate changed | False |

### Phase 10G Phase 10F Failure Check

| Check | Result |
|---|---|
| Phase 10F conclusion report exists | Passed |
| Phase 10F conclusion documents failure | Passed |
| Phase 10F conclusion says no rule passed | Passed |
| No Phase 10F rule passed from rule gate report | Passed |
| No Phase 10F rule passed from comparison summary | Passed |
| Phase 10F discipline gates passed | Passed |
| Phase 10F did not promote a strategy | Passed |

### Phase 10G Gate Result

| Gate | Result |
|---|---|
| Expected Phase 10 reports are present | Passed |
| Config flags match closeout state | Passed |
| Phase 10F failure is documented | Passed |
| No Phase 10F rule passed all gates | Passed |
| Phase 10F discipline gates passed | Passed |
| No strategy promotion occurred | Passed |
| No successor candidate was created | Passed |
| Final candidate remains unchanged | Passed |
| Macro branch is closed without promotion | Passed |
| Audit role is correct | Passed |

### Phase 10G Verdict

> Phase 10G completed the macro extension closeout without promotion.

Correct interpretation:

> Phase 10A–10D showed that macro/rates/inflation data was feasible and diagnostically informative, but Phase 10F failed as a pre-registered macro-rule test. No macro rule was promoted, no successor candidate was created, and the final hierarchy remains unchanged.

## Phase 10H: Final Phase 10 Checkpoint / README-Config-Report Consistency Audit

Phase 10H verified the final Phase 10 record after the macro/rates/inflation branch was closed without promotion.

This was not a new strategy test. It checked README wording, config flags, report inventory, Phase 10G closeout, Phase 10F failure documentation, canonical hierarchy, and promotion boundaries.

### Phase 10H Summary

| Metric | Result |
|---|---|
| README required Phase 10 phrases present | True |
| README forbidden overclaim phrases absent | True |
| Expected Phase 10 reports present | True |
| Config flags clean | True |
| Phase 10G closeout passed | True |
| Phase 10F failure locked | True |
| No successor candidate created | True |
| Final candidate unchanged | True |
| Canonical hierarchy present | True |
| Strategy promotion | False |

### Phase 10H Gate Result

| Gate | Result |
|---|---|
| README required Phase 10 phrases are present | Passed |
| README forbidden overclaim phrases are absent | Passed |
| Expected Phase 10 reports are present | Passed |
| Config flags match final Phase 10 checkpoint state | Passed |
| Phase 10G closeout passed | Passed |
| Phase 10F failure remains locked | Passed |
| No successor candidate was created | Passed |
| Final candidate remains unchanged | Passed |
| Canonical hierarchy is present | Passed |
| No strategy promotion occurred | Passed |
| Audit role is correct | Passed |

### Phase 10H Verdict

> Phase 10H completed the final Phase 10 checkpoint.

Correct interpretation:

> Phase 10 is now closed cleanly. Macro/rates/inflation evidence was feasible and diagnostically informative, but the pre-registered macro-rule test failed. Phase 10G closed the branch without promotion, Phase 10H verified README/config/report consistency, and the final hierarchy remains unchanged.

# Phase 11
## Phase 11A: Architecture Review for Richer Information Layers

Phase 11A reviewed the next research architecture after both the technical-indicator extension and macro/rates/inflation extension produced useful diagnostic evidence but failed as pre-registered rule overlays.

This was not a new strategy test. It did not create a new indicator rule, macro retry, sentiment feed, fundamental feature, model, backtest, allocation rule, or candidate promotion.

### Phase 11A Summary

| Metric | Result |
|---|---:|
| Review role | Architecture review for richer information layers only |
| Phase branch | Phase 11 architecture review |
| Proposed next phase | Phase 11B |
| Prior branch count | 2 |
| Failed rule-extension count | 2 |
| Closed-without-promotion count | 2 |
| Architecture candidate count | 6 |
| Simple overlay rejected as next step | True |
| Preferred architecture | `A2_regime_scoring_layer` |
| Recommended next phase | Phase 11B |
| Next step is spec-only | True |
| Strategy test allowed next | False |

### Phase 11A Architecture Candidates

| Architecture | Immediate next-step role |
|---|---|
| `A1_continue_simple_rule_overlays` | Rejected as immediate next step |
| `A2_regime_scoring_layer` | Preferred next architecture-spec candidate |
| `A3_probabilistic_allocation_confidence` | Secondary architecture candidate |
| `A4_explainable_ensemble_decision_layer` | Long-term candidate, not next |
| `A5_separate_successor_architecture` | Architecture-review candidate |
| `A6_freeze_spy_overlay_arc` | Valid pause option |

### Phase 11A Gate Result

| Gate | Result |
|---|---|
| Prior rule-extension failures are documented | Passed |
| Architecture candidates are documented | Passed |
| Simple overlay continuation is rejected as immediate next step | Passed |
| Preferred architecture is identified | Passed |
| Next step is spec-only | Passed |
| No new indicator rule is allowed | Passed |
| No macro rule retry is allowed | Passed |
| No sentiment ingestion is allowed | Passed |
| No fundamental ingestion is allowed | Passed |
| No model training is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Review role is correct | Passed |

### Phase 11A Verdict

> Phase 11A completed the richer-information architecture review.

Correct interpretation:

> The project should not continue immediately with simple if/then overlays. After failed technical and macro rule-extension branches, the next step should be Phase 11B: a regime-scoring architecture spec. This should remain design-only and should not create a strategy test, allocation rule, model, or promoted candidate.

## Phase 11B: Regime Scoring Architecture Spec

Phase 11B defined the design boundaries for a future regime-scoring layer after both technical and macro rule-overlay extensions failed validation.

This was not a score implementation. It did not calculate scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 11B Summary

| Metric | Result |
|---|---:|
| Spec role | Regime scoring architecture spec only |
| Phase branch | Phase 11 architecture review |
| Proposed next phase | Phase 11C |
| Source architecture decision present | True |
| Simple overlay rejected | True |
| Scoring principle count | 6 |
| Required scoring principle count | 6 |
| Component family count | 5 |
| Validation-risk context present | True |
| Future data families blocked | True |
| Score states non-trading | True |
| Future validation requirement count | 6 |
| Phase 11C boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 11B Component Registry

| Component | Family | Role | Phase 11C spec allowed |
|---|---|---|---|
| `technical_regime_context` | technical | diagnostic candidate | True |
| `macro_regime_context` | macro/rates/inflation | diagnostic candidate | True |
| `validation_risk_context` | validation risk | required control layer | True |
| `future_fundamental_context` | fundamental / valuation | future candidate, not active | False |
| `future_sentiment_context` | sentiment / narrative | future candidate, not active | False |

### Phase 11B Gate Result

| Gate | Result |
|---|---|
| Source architecture decision is documented | Passed |
| Scoring principles are documented | Passed |
| Component families are documented | Passed |
| Validation-risk context is included | Passed |
| Future unaudited data families are blocked | Passed |
| Score states are non-trading concepts | Passed |
| Future validation requirements are documented | Passed |
| Phase 11C boundary is spec-only | Passed |
| No score calculation is allowed | Passed |
| No score weights are allowed | Passed |
| No signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No model training is allowed | Passed |
| No new data ingestion is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Spec role is correct | Passed |

### Phase 11B Verdict

> Phase 11B completed the regime scoring architecture spec.

Correct interpretation:

> Phase 11B defined a design-only regime-scoring architecture. It did not calculate scores, create weights, create signals, run backtests, ingest new data, train models, or promote a candidate. Phase 11C may only define the score rulebook/spec.

## Phase 11C: Regime Scoring Rulebook Spec

Phase 11C defined the future regime-scoring rulebook grammar after Phase 11B established the regime-scoring architecture.

This was not a score implementation. It did not calculate scores, assign empirical weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 11C Summary

| Metric | Result |
|---|---:|
| Spec role | Regime scoring rulebook spec only |
| Phase branch | Phase 11 architecture review |
| Source phase | Phase 11B |
| Proposed next phase | Phase 11D |
| Source architecture present | True |
| Component count | 5 |
| Active required components present | True |
| Future unaudited families blocked | True |
| Conceptual direction count | 6 |
| Conceptual directions non-trading | True |
| Missingness rule count | 5 |
| Weighting principle count | 5 |
| Score states non-trading | True |
| Audit output count | 5 |
| Future validation gate count | 6 |
| Phase 11D boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 11C Component Rulebook

| Component | Family | Role | Status | Conceptual directions |
|---|---|---|---|---:|
| `technical_regime_context` | technical | active conceptual component | conceptual only | 2 |
| `macro_regime_context` | macro/rates/inflation | active conceptual component | conceptual only | 2 |
| `validation_risk_context` | validation risk | required control component | conceptual only | 2 |
| `future_fundamental_context` | fundamental / valuation | blocked future component | blocked | 0 |
| `future_sentiment_context` | sentiment / narrative | blocked future component | blocked | 0 |

### Phase 11C Gate Result

| Gate | Result |
|---|---|
| Source architecture is documented | Passed |
| Component rulebook is documented | Passed |
| Technical, macro, and validation components are present | Passed |
| Future unaudited families are blocked | Passed |
| Conceptual directions are documented and non-trading | Passed |
| Missingness rules are documented | Passed |
| Weighting principles are documented | Passed |
| Score states are non-trading concepts | Passed |
| Audit output spec is documented | Passed |
| Future validation gates are documented | Passed |
| Phase 11D boundary is design-only | Passed |
| No score calculation is allowed | Passed |
| No numeric score weights are allowed | Passed |
| No empirical return weights are allowed | Passed |
| No signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No model training is allowed | Passed |
| No new data ingestion is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Spec role is correct | Passed |

### Phase 11C Verdict

> Phase 11C completed the regime scoring rulebook spec.

Correct interpretation:

> Phase 11C defined the regime-scoring rulebook only. It documented conceptual component directions, missingness rules, weighting principles, audit outputs, and future validation gates, but did not calculate a score, create a signal, test a strategy, train a model, ingest new data, or promote a candidate.

## Phase 11D: Regime Scoring Diagnostic Panel Design

Phase 11D designed the future diagnostic panel structure for the regime-scoring architecture.

This was not a score implementation. It did not calculate scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 11D Summary

| Metric | Result |
|---|---:|
| Design role | Regime scoring diagnostic panel design only |
| Phase branch | Phase 11 architecture review |
| Source phase | Phase 11C |
| Proposed next phase | Phase 11E |
| Source rulebook present | True |
| Panel section count | 6 |
| Required column rows | 42 |
| Required columns present | True |
| Component availability rows | 5 |
| Conceptual direction rows | 3 |
| Conceptual directions non-trading | True |
| Missingness policy count | 5 |
| Weighting policy count | 5 |
| Weighting non-empirical | True |
| Blocked family count | 2 |
| Blocked families clean | True |
| All panels avoid returns usage | True |
| All panels are non-signal panels | True |
| Phase 11E boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 11D Diagnostic Panel Sections

| Panel | Report | Uses returns | Creates signal | Required columns |
|---|---|---:|---:|---:|
| `component_availability_panel` | `component_availability_report` | False | False | 8 |
| `conceptual_direction_panel` | `component_direction_report` | False | False | 8 |
| `missingness_panel` | `missingness_report` | False | False | 8 |
| `weighting_policy_panel` | `weighting_policy_report` | False | False | 7 |
| `blocked_family_panel` | `blocked_family_report` | False | False | 6 |
| `boundary_panel` | `boundary_report` | False | False | 5 |

### Phase 11D Gate Result

| Gate | Result |
|---|---|
| Source rulebook is documented | Passed |
| Diagnostic panel sections are documented | Passed |
| Required columns are documented | Passed |
| Component availability spec is documented | Passed |
| Conceptual direction spec is documented | Passed |
| Missingness policy spec is documented | Passed |
| Weighting policy spec is documented | Passed |
| Blocked family spec is documented | Passed |
| All panels are non-signal panels | Passed |
| All panels avoid returns usage | Passed |
| Phase 11E boundary is implementation-audit only | Passed |
| No score calculation is allowed | Passed |
| No numeric score weights are allowed | Passed |
| No empirical return weights are allowed | Passed |
| No signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No model training is allowed | Passed |
| No new data ingestion is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Design role is correct | Passed |

### Phase 11D Verdict

> Phase 11D completed the regime scoring diagnostic panel design.

Correct interpretation:

> Phase 11D designed the diagnostic panel structure and report schemas for future regime-scoring work. It did not implement a score, assign weights, create a signal, run a strategy test, ingest new data, train a model, or promote a candidate.

## Phase 11E: Regime Scoring Diagnostic Panel Template Implementation Audit

Phase 11E created schema-compliant diagnostic panel templates from the Phase 11D design.

This was not a score implementation. It did not calculate regime scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 11E Summary

| Metric | Result |
|---|---:|
| Implementation role | Regime scoring diagnostic panel template implementation audit only |
| Phase branch | Phase 11 architecture review |
| Source phase | Phase 11D |
| Proposed next phase | Phase 11F |
| Source design reports present | True |
| Template report count | 6 |
| Template inventory rows | 6 |
| Schema compliance passed | True |
| Component availability rows | 5 |
| Direction rows | 9 |
| Missingness rows | 5 |
| Weighting-policy rows | 5 |
| Blocked-family rows | 2 |
| Boundary rows | 9 |
| Direction non-signal | True |
| Missingness blocks return inference | True |
| Weighting non-empirical | True |
| Blocked families clean | True |
| Boundary report passed | True |
| Phase 11F boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 11E Template Inventory

| Report | Rows | Columns |
|---|---:|---:|
| `component_availability_report` | 5 | 8 |
| `component_direction_report` | 9 | 8 |
| `missingness_report` | 5 | 8 |
| `weighting_policy_report` | 5 | 7 |
| `blocked_family_report` | 2 | 6 |
| `boundary_report` | 9 | 5 |

### Phase 11E Schema Compliance

| Report | Expected columns | Actual columns | Missing columns | Rows | Result |
|---|---:|---:|---:|---:|---|
| `component_availability_report` | 8 | 8 | 0 | 5 | Passed |
| `component_direction_report` | 8 | 8 | 0 | 9 | Passed |
| `missingness_report` | 8 | 8 | 0 | 5 | Passed |
| `weighting_policy_report` | 7 | 7 | 0 | 5 | Passed |
| `blocked_family_report` | 6 | 6 | 0 | 2 | Passed |
| `boundary_report` | 5 | 5 | 0 | 9 | Passed |

### Phase 11E Gate Result

| Gate | Result |
|---|---|
| Source design reports are present | Passed |
| Template reports are generated | Passed |
| Template schemas are compliant | Passed |
| Component availability template rows exist | Passed |
| Direction template rows exist | Passed |
| Missingness template rows exist | Passed |
| Weighting-policy template rows exist | Passed |
| Blocked-family template rows exist | Passed |
| Boundary template rows exist | Passed |
| Templates are non-signal | Passed |
| Templates do not use returns | Passed |
| Weighting templates are non-empirical | Passed |
| Blocked-family templates are clean | Passed |
| Boundary report passes | Passed |
| Phase 11F boundary is content-audit only | Passed |
| No score calculation is allowed | Passed |
| No numeric score weights are allowed | Passed |
| No empirical return weights are allowed | Passed |
| No signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No model training is allowed | Passed |
| No new data ingestion is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Implementation role is correct | Passed |

### Phase 11E Verdict

> Phase 11E completed the regime scoring diagnostic panel template implementation audit.

Correct interpretation:

> Phase 11E created schema-compliant diagnostic panel templates and verified required columns, blocked-family rows, boundary rows, and non-signal/non-return constraints. It did not calculate regime scores, assign weights, create signals, ingest new data, run strategy tests, train models, or promote a candidate.

## Phase 11F: Regime Scoring Diagnostic Panel Content Audit

Phase 11F audited the content of the regime-scoring diagnostic panel templates created in Phase 11E.

This was not a score implementation. It did not calculate regime scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 11F Summary

| Metric | Result |
|---|---:|
| Audit role | Regime scoring diagnostic panel content audit only |
| Phase branch | Phase 11 architecture review |
| Source phase | Phase 11E |
| Proposed next phase | Phase 11G |
| Source templates present | True |
| Source template count | 9 |
| Phase 11E result passed | True |
| Component content passed | True |
| Direction content passed | True |
| Missingness content passed | True |
| Weighting content passed | True |
| Blocked-family content passed | True |
| Boundary content passed | True |
| Phase 11G boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 11F Content Checks

| Check area | Result |
|---|---|
| Expected components present | Passed |
| Blocked components flagged | Passed |
| Active components not blocked | Passed |
| Technical regime directions complete | Passed |
| Macro regime directions complete | Passed |
| Validation-risk directions complete | Passed |
| Direction rows non-signal/non-trading | Passed |
| Missingness blocks return inference | Passed |
| Missingness blocks silent fill | Passed |
| Numeric weights blocked | Passed |
| Empirical return weights blocked | Passed |
| Cutoff search blocked | Passed |
| Pre-registration required | Passed |
| Blocked families present | Passed |
| Blocked families not usable currently | Passed |
| Blocked families cannot be score components | Passed |
| Boundary items present | Passed |
| Boundary allowed values all false | Passed |
| Boundary rows passed | Passed |

### Phase 11F Gate Result

| Gate | Result |
|---|---|
| Source templates are present | Passed |
| Phase 11E template audit remains passed | Passed |
| Schema compliance remains passed | Passed |
| Component content is consistent | Passed |
| Direction content is consistent | Passed |
| Missingness content is consistent | Passed |
| Weighting content is consistent | Passed |
| Blocked-family content is consistent | Passed |
| Boundary content is consistent | Passed |
| Phase 11G boundary is closeout-only | Passed |
| No score calculation is allowed | Passed |
| No numeric score weights are allowed | Passed |
| No empirical return weights are allowed | Passed |
| No signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No model training is allowed | Passed |
| No new data ingestion is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Audit role is correct | Passed |

### Phase 11F Verdict

> Phase 11F completed the regime-scoring diagnostic panel content audit.

Correct interpretation:

> Phase 11F confirmed that the diagnostic panel template content is internally consistent with the Phase 11E templates and Phase 11D design. No regime score, score weight, signal, allocation rule, strategy test, model, new data ingestion, or candidate promotion exists.

## Phase 11G: Final Phase 11 Regime Scoring Closeout / Checkpoint Audit

Phase 11G closed the Phase 11 regime-scoring architecture and diagnostic-panel branch.

This was not a score implementation. It did not calculate regime scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 11G Summary

| Metric | Result |
|---|---:|
| Audit role | Final Phase 11 regime scoring closeout/checkpoint audit only |
| Phase branch | Phase 11 regime scoring architecture and diagnostic panel branch |
| Checkpoint status | Phase 11 closed — regime scoring architecture and diagnostic panel prepared without scoring |
| Next allowed step | Phase 12A score-calculation pre-registration spec only |
| Report prefixes present | True |
| Markdown reports present | True |
| Config flags clean for closeout run | True |
| Phase conclusions passed | True |
| Phase gate reports passed | True |
| Boundary reports passed | True |
| Branch closure clean | True |
| Phase 12A boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 11G Closure Claims

| Claim | Result |
|---|---|
| Regime score exists | False |
| Signal exists | False |
| Allocation rule exists | False |
| Strategy test exists | False |
| Model exists | False |
| New data ingested | False |
| Candidate promoted | False |
| Final candidate changed | False |

### Phase 11G Gate Result

| Gate | Result |
|---|---|
| Expected Phase 11 report prefixes are present | Passed |
| Expected Phase 11 markdown reports are present | Passed |
| Config flags are clean for closeout run | Passed |
| Phase 11 conclusions passed | Passed |
| Phase 11 gate reports passed | Passed |
| Phase 11F is locked as passed | Passed |
| Boundary reports passed | Passed |
| No score, signal, model, strategy, or promotion exists | Passed |
| Phase 12A boundary is pre-registration-spec only | Passed |
| No score calculation is allowed | Passed |
| No numeric score weights are allowed | Passed |
| No empirical return weights are allowed | Passed |
| No signal creation is allowed | Passed |
| No allocation rule creation is allowed | Passed |
| No strategy backtest is allowed | Passed |
| No model training is allowed | Passed |
| No new data ingestion is allowed | Passed |
| No candidate promotion is allowed | Passed |
| Audit role is correct | Passed |

### Phase 11G Verdict

> Phase 11G completed the final Phase 11 regime-scoring checkpoint.

Correct interpretation:

> Phase 11 is now closed cleanly. The project has prepared a regime-scoring architecture, rulebook, diagnostic-panel design, schema-compliant templates, and content audits, but no regime score, score weights, signal, allocation rule, strategy test, model, new data ingestion, candidate promotion, or final-candidate change exists.

# Phase 12
## Phase 12B: Score-Calculation Readiness Audit

Phase 12B verified that Phase 12A was complete and locked before any diagnostic score calculation.

This was not a score-calculation phase. It did not calculate regime scores, assign empirical weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Phase 12B Summary

| Metric | Result |
|---|---:|
| Audit role | Score-calculation readiness audit only |
| Phase branch | Phase 12 regime score calculation preparation |
| Source phase | Phase 12A |
| Proposed next phase | Phase 12C |
| Phase 12A reports present | True |
| Phase 12A result passed | True |
| Config flags clean for combined run | True |
| Readiness claims locked | True |
| Phase 12C boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 12B Readiness Claims

| Claim | Result |
|---|---|
| Pre-registration exists | Passed |
| Eligible components locked | Passed |
| Blocked components locked | Passed |
| Formula structure locked | Passed |
| Weighting policy locked | Passed |
| Missingness policy locked | Passed |
| Failure conditions locked | Passed |
| Score calculated | False |
| Signal created | False |
| Backtest run | False |
| Model trained | False |
| New data ingested | False |
| Candidate promoted | False |

### Phase 12C Boundary

| Boundary | Result |
|---|---|
| Allowed next step | Diagnostic score calculation only |
| Forbidden next step | Trading signal creation, allocation rule, strategy backtest, model training, new data ingestion, or candidate promotion |
| May calculate diagnostic scores | True |
| May assign empirical weights | False |
| May create signal | False |
| May test strategy | False |
| May train model | False |
| May ingest new data | False |
| May promote candidate | False |

### Phase 12B Gate Result

| Gate | Result |
|---|---|
| Phase 12A reports are present | Passed |
| Phase 12A conclusion and gates passed | Passed |
| Config flags are clean for combined run | Passed |
| Readiness claims are locked | Passed |
| Phase 12C boundary is diagnostic-only | Passed |
| No score output/signal/backtest/model/data/promotion is allowed | Passed |
| Audit role is correct | Passed |

### Phase 12B Verdict

> Phase 12B completed the score-calculation readiness audit.

Correct interpretation:

> Phase 12B verified that the score-calculation pre-registration is complete and locked. No score, empirical weight, signal, strategy test, model, new data ingestion, or candidate promotion exists. Phase 12C may only calculate diagnostic scores.

## Phase 12C: Diagnostic Score Calculation

Phase 12C calculated the first categorical diagnostic regime score using the pre-registered Phase 12A grammar.

This was not a trading-signal phase. It did not create an allocation rule, run a strategy backtest, assign empirical weights, ingest new data, train a model, promote a candidate, or change the final candidate.

### Phase 12C Summary

| Metric | Result |
|---|---:|
| Calculation role | Diagnostic score calculation only |
| Phase branch | Phase 12 regime score calculation |
| Source phase | Phase 12B |
| Proposed next phase | Phase 12D |
| Source reports present | True |
| Phase 12B result passed | True |
| Component count | 3 |
| Component states allowed | True |
| Aggregate score allowed | True |
| Blocked components excluded | True |
| Existing project sources only | True |
| Component rows non-signal | True |
| No empirical weights | True |
| No numeric weights | True |
| No returns used | True |
| No signal/backtest/promotion | True |
| Phase 12D boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 12C Diagnostic Score Inputs

| Component | Diagnostic state | Role |
|---|---|---|
| `technical_regime_context` | Neutral | Eligible component state |
| `macro_regime_context` | Neutral | Eligible component state |
| `validation_risk_context` | Fragile | Eligible control state |

### Phase 12C Aggregate Score

| Item | Result |
|---|---|
| Score ID | `pre_registered_three_component_regime_score` |
| Calculation scope | Static branch-level diagnostic score |
| Aggregation method | Categorical equal vote with validation-risk control |
| Supportive components | 0 |
| Neutral components | 2 |
| Fragile components | 1 |
| Raw vote state | Neutral |
| Final diagnostic score state | Fragile |
| Validation-risk override | Fragile validation risk without supportive majority |
| Empirical weights allowed | False |
| Numeric weights allowed | False |
| Returns used | False |
| Trading signal created | False |
| Strategy backtest run | False |
| Candidate promoted | False |

### Phase 12C Verdict

> Phase 12C completed the diagnostic score calculation.

Correct interpretation:

> Phase 12C calculated a categorical diagnostic regime score from the pre-registered Phase 12A grammar. The resulting score is diagnostic only. It is not a trading signal, allocation rule, strategy test, model, candidate promotion, or final-candidate change.

## Phase 12D: Diagnostic Score Distribution / Content Audit

Phase 12D audited the Phase 12C diagnostic score distribution and content quality.

This was not a trading-signal phase. It did not create an allocation rule, run a strategy backtest, assign empirical weights, ingest new data, train a model, promote a candidate, or change the final candidate.

### Phase 12D Summary

| Metric | Result |
|---|---:|
| Audit role | Diagnostic score distribution and content audit only |
| Phase branch | Phase 12 regime score calculation |
| Source phase | Phase 12C |
| Proposed next phase | Phase 12E |
| Phase 12C reports present | True |
| Phase 12C result passed | True |
| Distribution check passed | True |
| Forbidden-column check passed | True |
| Phase 12E boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |

### Phase 12D Forbidden-Column Audit

| Frame | Forbidden group | Result |
|---|---|---|
| `component_state_panel` | Numeric score columns | Passed |
| `component_state_panel` | Signal columns | Passed |
| `component_state_panel` | Backtest columns | Passed |
| `component_state_panel` | Empirical weight columns | Passed |
| `aggregate_score` | Numeric score columns | Passed |
| `aggregate_score` | Signal columns | Passed |
| `aggregate_score` | Backtest columns | Passed |
| `aggregate_score` | Empirical weight columns | Passed |

### Phase 12D Gate Result

| Gate | Result |
|---|---|
| Phase 12C reports are present | Passed |
| Phase 12C conclusion passed | Passed |
| Score distribution and aggregate content are valid | Passed |
| No forbidden score/signal/backtest/weight columns exist | Passed |
| Phase 12E boundary is interpretation-audit only | Passed |
| Audit role is correct | Passed |

### Phase 12D Verdict

> Phase 12D completed the diagnostic score distribution audit.

Correct interpretation:

> Phase 12D confirmed that the Phase 12C diagnostic score is categorical, content-consistent, and bounded. No numeric trading score, signal, allocation rule, strategy backtest, empirical weight, model, new data ingestion, candidate promotion, or final-candidate change exists.

## Phase 12E: Diagnostic Score Interpretation / Closeout Audit

Phase 12E interpreted the Phase 12C diagnostic score and closed the score-interpretation branch.

This was not a trading-signal phase. It did not create an allocation rule, run a strategy backtest, assign empirical weights, ingest new data, train a model, promote a candidate, or change the final candidate.

### Phase 12E Summary

| Metric | Result |
|---|---:|
| Audit role | Diagnostic score interpretation and closeout audit only |
| Phase branch | Phase 12 diagnostic regime score branch |
| Source phase | Phase 12D |
| Proposed next phase | Phase 12F |
| Source score reports present | True |
| Phase 12D result passed | True |
| Aggregate state | Fragile |
| Aggregate state allowed | True |
| Aggregate state matches expected fragile state | True |
| Interpretation created | True |
| Interpretation diagnostic-only | True |
| Closeout claims locked | True |
| Phase 12F boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 12E Interpretation

| Item | Result |
|---|---|
| Diagnostic score state | Fragile |
| Interpretation role | Diagnostic-only research interpretation |
| Interpretation | The diagnostic regime score is fragile because technical and macro evidence are neutral while validation-risk context is fragile. |
| Permitted use | Document research context and caveat stack only. |
| Prohibited use | Trading signal, allocation rule, strategy backtest, empirical weighting, model training, live-trading recommendation, candidate promotion, or final-candidate change. |

### Phase 12E Closeout Claims

| Claim | Result |
|---|---|
| Diagnostic score interpreted | True |
| Score-to-signal created | False |
| Allocation rule created | False |
| Strategy backtest run | False |
| Empirical weights assigned | False |
| Model trained | False |
| New data ingested | False |
| Candidate promoted | False |
| Final candidate changed | False |

### Phase 12E Gate Result

| Gate | Result |
|---|---|
| Source score reports are present | Passed |
| Phase 12D remains passed | Passed |
| Aggregate score state is allowed | Passed |
| Aggregate score state matches expected fragile state | Passed |
| Diagnostic interpretation was created | Passed |
| Interpretation remains diagnostic-only | Passed |
| Closeout claims are locked | Passed |
| Phase 12F boundary is checkpoint-only | Passed |
| No signal/allocation/backtest/model/data/promotion/change is allowed | Passed |
| Audit role is correct | Passed |

### Phase 12E Verdict

> Phase 12E completed the diagnostic score interpretation closeout.

Correct interpretation:

> Phase 12E interpreted the fragile diagnostic score as research-only context. It did not convert the score into a trading signal, allocation rule, strategy test, model, empirical weighting system, candidate promotion, or final-candidate change.

## Phase 12F: Final Phase 12 Diagnostic Score Checkpoint Audit

Phase 12F closed the Phase 12 diagnostic regime-score branch.

This was not a trading-signal phase. It did not create an allocation rule, run a strategy backtest, assign empirical weights, ingest new data, train a model, promote a candidate, or change the final candidate.

### Phase 12F Summary

| Metric | Result |
|---|---:|
| Audit role | Final Phase 12 diagnostic score checkpoint audit only |
| Phase branch | Phase 12 diagnostic regime score branch |
| Checkpoint status | Phase 12 closed — diagnostic regime score calculated, audited, interpreted, and bounded |
| Next allowed step | Separate future score-to-signal pre-registration spec only, if pursued |
| Report prefixes present | True |
| Markdown reports present | True |
| Config flags clean for checkpoint run | True |
| Phase conclusions passed | True |
| Phase gate reports passed | True |
| Branch closure claims locked | True |
| Future Phase 13 boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 12F Branch Closure Claims

| Claim | Result |
|---|---|
| Diagnostic score exists | True |
| Diagnostic score interpreted | True |
| Score-to-signal created | False |
| Allocation rule created | False |
| Strategy backtest run | False |
| Empirical weights assigned | False |
| Model trained | False |
| New data ingested | False |
| Candidate promoted | False |
| Final candidate changed | False |

### Phase 12F Future Phase 13 Boundary

| Boundary | Result |
|---|---|
| Allowed next step | Separate score-to-signal pre-registration spec only, if pursued |
| Forbidden next step | Direct signal creation, allocation rule, strategy backtest, empirical weighting, model training, new data ingestion, candidate promotion, or final-candidate change |
| May define signal spec | True |
| May create signal immediately | False |
| May test strategy | False |
| May assign empirical weights | False |
| May train model | False |
| May ingest new data | False |
| May promote candidate | False |
| May change final candidate | False |

### Phase 12F Gate Result

| Gate | Result |
|---|---|
| Expected Phase 12 report prefixes are present | Passed |
| Expected Phase 12 markdown reports are present | Passed |
| Config flags are clean for checkpoint run | Passed |
| Phase 12 conclusions passed | Passed |
| Phase 12 gate reports passed | Passed |
| Branch closure claims are locked | Passed |
| Future Phase 13 boundary is pre-registration-only | Passed |
| No signal/allocation/backtest/model/data/promotion/change is allowed | Passed |
| Audit role is correct | Passed |

### Phase 12F Verdict

> Phase 12F completed the final Phase 12 diagnostic score checkpoint.

Correct interpretation:

> Phase 12 is now closed. The diagnostic regime-score branch calculated, audited, interpreted, and bounded a fragile diagnostic score. No score-to-signal conversion, allocation rule, backtest, empirical weighting, model, new data ingestion, candidate promotion, or final-candidate change exists. Any future score-to-signal work requires a separate pre-registration phase.

## Phase 13A: Baseline SPY Research Arc Freeze / Transition Spec

Phase 13A froze the SPY regime-switch arc as a baseline research framework and opened the new multi-factor model architecture path.

This phase did not convert the fragile diagnostic score into a signal, create an allocation rule, run a backtest, train a model, ingest new data, promote a candidate, or change the final candidate.

### Phase 13A Summary

| Metric | Result |
|---|---:|
| Spec role | Baseline SPY research arc freeze and transition spec only |
| Phase branch | Phase 13 multi-factor model architecture planning |
| Source phase | Phase 12F |
| Proposed next phase | Phase 13B |
| Source reports present | True |
| Phase 12F result passed | True |
| Baseline arc frozen | True |
| Baseline role is not final project endpoint | True |
| Diagnostic score state | Fragile |
| Score-to-signal created | False |
| Candidate promoted | False |
| Hierarchy changed | False |
| Transition to multi-factor path | True |
| Direct score-to-signal rejected | True |
| Phase 13B boundary passed | True |
| Strategy promotion | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 13A Baseline Freeze

| Item | Result |
|---|---|
| Baseline arc | SPY regime-switch baseline research framework |
| Baseline status | Frozen as benchmark and validation infrastructure |
| Final candidate | Phase 6B/6C 3D + deep_drawdown_guard + loose_relief |
| Final candidate role | Best execution-realistic risk-adjusted candidate built so far, not final project endpoint |
| Diagnostic score state | Fragile |
| Diagnostic score role | Baseline research diagnostic, not signal |
| Hierarchy changed | False |
| Candidate promoted | False |
| Score-to-signal created | False |

### Phase 13A Transition Decision

| Item | Decision |
|---|---|
| Decision | Open a new multi-factor model architecture branch |
| Reason | The baseline arc produced a robust validation framework but did not build the intended technical + macro + fundamental + sentiment long-term decision model |
| Rejected next step | Direct score-to-signal conversion from fragile Phase 12 score |
| Accepted next step | Multi-factor model architecture roadmap spec |
| Burden of proof | Any future signal/backtest requires separate pre-registration and out-of-sample validation |

### Phase 13A Gate Result

| Gate | Result |
|---|---|
| Phase 12F remains passed | Passed |
| Baseline arc is frozen | Passed |
| Baseline is not treated as final project endpoint | Passed |
| Transition decision opens multi-factor architecture path | Passed |
| Direct fragile-score-to-signal conversion is rejected | Passed |
| No hierarchy change or candidate promotion occurred | Passed |
| Phase 13B boundary is architecture-only | Passed |
| Scope boundary blocks signal/backtest/model/data/promotion/change | Passed |
| Spec role is correct | Passed |

### Phase 13A Verdict

> Phase 13A completed the baseline research arc freeze and transition spec.

Correct interpretation:

> The SPY regime-switch arc is now frozen as a reusable baseline framework. It is not the final project endpoint. The project now moves toward the original multi-factor model goal through a separate architecture path.

## Phase 13B: Multi-Factor Long-Term Decision Model Architecture Roadmap Spec

Phase 13B created the roadmap for the actual long-term multi-factor decision-model path.

This phase did not ingest features, create signals, create allocation rules, run strategy backtests, assign empirical weights, train models, deploy paper trading, promote a candidate, or change the final candidate.

### Phase 13B Summary

| Metric | Result |
|---|---:|
| Spec role | Multi-factor long-term decision model architecture roadmap spec only |
| Phase branch | Phase 13 multi-factor model architecture planning |
| Source phase | Phase 13A |
| Proposed next phase | Phase 13C |
| Ultimate goal present | True |
| Phase 13A result passed | True |
| Feature family count | 5 |
| Required families present | True |
| Architecture candidate count | 4 |
| Dissertation integration items | 4 |
| Walk-forward design present | True |
| Visual report count | 6 |
| Paper-trading gate count | 6 |
| Phase 13C boundary passed | True |
| Feature ingestion | False |
| Signal creation | False |
| Strategy backtest | False |
| Model training | False |
| Paper-trading deployment | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 13B Feature Families

| Family | Status | Role |
|---|---|---|
| Technical | Eligible for future feature-source audit | Trend, momentum, volatility, breadth, drawdown, and market-structure context |
| Macro | Eligible with existing Phase 10 foundation | Rates, inflation, labour, curve, liquidity, and regime context |
| Fundamental | Not yet audited | Valuation, earnings, margins, profitability, quality, and index-level fundamentals |
| Sentiment | Not yet audited | Risk appetite, news tone, narrative pressure, positioning proxies, and crowding context |
| Dissertation integration | Methodology candidate only | Optimisation, decision-support, reporting, and governance methodology, not direct alpha unless separately justified |

### Phase 13B Architecture Candidates

| Architecture | Role | Status |
|---|---|---|
| A1 interpretable regime score + exposure policy | Transparent baseline multi-factor decision layer | Roadmap only |
| A2 walk-forward probabilistic classifier | Probabilistic long-term exposure confidence model | Future after data contracts |
| A3 ensemble decision layer | Blend interpretable score, probabilistic model, and risk controls | Future |
| A4 visual decision dashboard | Human-readable buy/sell/exposure decision system | Required reporting layer |

### Phase 13B Dissertation Integration

| Item | Integration type | Planned use |
|---|---|---|
| D1 optimisation brain | Methodological | Use optimisation discipline for exposure constraints and decision policy design, not curve-fitted alpha |
| D2 visual decision support | Reporting | Translate model outputs into visual decision dashboards similar to operational decision-support systems |
| D3 validation framework | Governance | Reuse dissertation-style evaluation discipline for scenario comparisons, constraints, and robustness checks |
| D4 direct market feature | Blocked | Do not force dissertation variables into markets unless a genuine market-data mapping exists |

### Phase 13B Walk-Forward Design

| Item | Decision |
|---|---|
| Design | Long-horizon walk-forward model design |
| Train window policy | Anchored and rolling windows to be compared later |
| Validation policy | Walk-forward only after feature contracts are locked |
| Test policy | Holdout period must remain untouched until model choices are pre-registered |
| Rebalance policy | Monthly or weekly to be pre-registered later |
| Leakage controls | Point-in-time data availability, release-date lagging, revision/vintage handling, no future index membership leakage, no return-derived feature selection without pre-registration, no post-hoc threshold tuning |

### Phase 13B Visual Reporting Plan

| Report | Purpose |
|---|---|
| Exposure timeline | Show model-recommended exposure through time |
| Decision rationale panel | Show technical/macro/fundamental/sentiment state behind each decision |
| Trade marker chart | Show buy/sell/rebalance markers on SPY or S&P 500 price |
| Equity curve comparison | Compare model, SPY Buy & Hold, SPY 12M, and baseline overlay only after backtest phase is allowed |
| Drawdown comparison | Show risk behaviour versus benchmarks only after backtest phase is allowed |
| Paper-trading journal | Track future paper decisions, rationale, drift, and realised outcomes |

### Phase 13B Paper-Trading Readiness Plan

| Gate | Requirement |
|---|---|
| PTR1 feature contracts locked | All feature families must have source, leakage, missingness, and timing contracts |
| PTR2 walk-forward results exist | Walk-forward validation must exist before paper trading |
| PTR3 visual reports exist | Visual decision and exposure reports must be generated reproducibly |
| PTR4 no live-money claim | Paper trading must remain non-production and non-financial-advice |
| PTR5 broker execution not assumed | Paper fills and live fills must not be treated as equivalent |
| PTR6 freeze model before paper | The paper-trading model must be frozen before paper-trading starts |

### Phase 13B Gate Result

| Gate | Result |
|---|---|
| Phase 13A passed | Passed |
| Ultimate goal is documented | Passed |
| Feature family registry is complete enough | Passed |
| Technical, macro, fundamental, and sentiment families are present | Passed |
| Architecture candidates are documented | Passed |
| Dissertation integration plan exists | Passed |
| Walk-forward design is documented | Passed |
| Visual reporting plan is documented | Passed |
| Paper-trading readiness plan is documented | Passed |
| Phase 13C boundary is feature-inventory only | Passed |
| No feature/signal/backtest/model/paper-trading/promotion exists | Passed |
| Spec role is correct | Passed |

### Phase 13B Verdict

> Phase 13B completed the multi-factor model architecture roadmap spec.

Correct interpretation:

> The project has now pivoted from the frozen SPY baseline arc to the actual multi-factor model path. The roadmap covers technical, macro, fundamental, sentiment, dissertation-methodology integration, walk-forward design, visual reporting, and paper-trading readiness. No data ingestion, model, signal, backtest, paper-trading deployment, candidate promotion, or final-candidate change exists yet.

## Phase 13C: Multi-Factor Feature-Source Inventory / Leakage-Feasibility Spec

Phase 13C defined the first feature-source inventory and leakage-feasibility contract for the multi-factor model path.

This phase did not ingest features, calculate features, create signals, create allocation rules, run strategy backtests, assign empirical weights, train models, deploy paper trading, promote a candidate, or change the final candidate.

### Phase 13C Summary

| Metric | Result |
|---|---:|
| Spec role | Multi-factor feature-source inventory and leakage-feasibility spec only |
| Phase branch | Phase 13 multi-factor model architecture planning |
| Source phase | Phase 13B |
| Proposed next phase | Phase 13D |
| Source reports present | True |
| Phase 13B result passed | True |
| Feature family count | 5 |
| Required families present | True |
| Contract requirement count | 8 |
| Contract requirements required | True |
| Leakage control count | 6 |
| Leakage controls required | True |
| Fundamental blocked now | True |
| Sentiment blocked now | True |
| Blocked-family policy clean | True |
| Phase 13D boundary passed | True |
| Feature ingestion | False |
| Feature calculation | False |
| Signal creation | False |
| Strategy backtest | False |
| Model training | False |
| Paper-trading deployment | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 13C Feature-Source Inventory

| Family | Status | Decision |
|---|---|---|
| Technical | Source contract feasible | Eligible for contract design |
| Macro | Source contract feasible with existing Phase 10 foundation | Eligible for contract design with strict lagging |
| Fundamental | Requires source audit before use | Blocked until dedicated fundamental source/leakage audit |
| Sentiment | Requires source audit before use | Blocked until dedicated sentiment source/leakage/noise audit |
| Dissertation integration | Methodology only | Allowed as methodology, not direct market feature |

### Phase 13C Contract Requirements

| Requirement | Result |
|---|---|
| Source identity | Required |
| Timestamp policy | Required |
| Lag policy | Required |
| Revision policy | Required |
| Missingness policy | Required |
| Transform policy | Required |
| No return-based feature selection | Required |
| Audit output | Required |

### Phase 13C Leakage Controls

| Control | Result |
|---|---|
| No same-day macro/fundamental/sentiment use unless timestamp-proven | Required |
| No vintage-blind macro use | Required |
| No future index membership leakage | Required |
| No post-hoc feature selection | Required |
| No signal before feature contracts | Required |
| No model before data audit | Required |

### Phase 13C Gate Result

| Gate | Result |
|---|---|
| Phase 13B passed | Passed |
| Feature-source inventory is complete enough | Passed |
| Technical, macro, fundamental, and sentiment are present | Passed |
| Feature contract requirements are documented | Passed |
| Leakage controls are documented | Passed |
| Fundamental family remains blocked until audit | Passed |
| Sentiment family remains blocked until audit | Passed |
| Blocked-family policy is clean | Passed |
| Phase 13D boundary is readiness-only | Passed |
| Scope blocks feature/model/signal/backtest/paper-trading/promotion | Passed |
| Spec role is correct | Passed |

### Phase 13C Verdict

> Phase 13C completed the feature-source inventory and leakage-feasibility spec.

Correct interpretation:

> Phase 13C moved the project towards the real multi-factor model path by defining feature-source families, contracts, leakage controls, and blocked-family policy. It did not ingest or calculate features, create a signal, run a backtest, train a model, deploy paper trading, promote a candidate, or change the final candidate.

## Phase 13D: Feature Contract / Data Availability Readiness Audit

Phase 13D audited the Phase 13C feature-source inventory and contract-readiness state.

This phase did not ingest features, calculate features, create signals, create allocation rules, run strategy backtests, assign empirical weights, train models, deploy paper trading, promote a candidate, or change the final candidate.

### Phase 13D Summary

| Metric | Result |
|---|---:|
| Audit role | Feature contract and data availability readiness audit only |
| Phase branch | Phase 13 multi-factor model architecture planning |
| Source phase | Phase 13C |
| Proposed next phase | Phase 13E |
| Phase 13C reports present | True |
| Phase 13C result passed | True |
| Config flags clean for run | True |
| Readiness claims locked | True |
| Contract coverage passed | True |
| Blocked families respected | True |
| Phase 13E boundary passed | True |
| Feature ingestion | False |
| Feature calculation | False |
| Signal creation | False |
| Strategy backtest | False |
| Model training | False |
| Paper-trading deployment | False |
| Candidate promotion | False |
| Final candidate changed | False |

### Phase 13D Contract Coverage

| Check | Result |
|---|---|
| Required feature families present | Passed |
| Contract requirements present | Passed |
| Leakage controls present | Passed |
| Technical is not blocked | Passed |
| Macro is not blocked but requires strict lagging | Passed |

### Phase 13D Blocked Family Check

| Family | Present | Blocked now | Result |
|---|---:|---:|---|
| Fundamental | True | True | Passed |
| Sentiment | True | True | Passed |

### Phase 13D Gate Result

| Gate | Result |
|---|---|
| Phase 13C reports are present | Passed |
| Phase 13C conclusion and gates passed | Passed |
| Config flags are clean for run | Passed |
| Readiness claims are locked | Passed |
| Contract coverage passed | Passed |
| Blocked families are respected | Passed |
| Phase 13E boundary is schema-only | Passed |
| Scope blocks feature/model/signal/backtest/paper-trading/promotion | Passed |
| Audit role is correct | Passed |

### Phase 13D Verdict

> Phase 13D completed the feature contract readiness audit.

Correct interpretation:

> Phase 13D verified that the feature-source inventory and leakage controls are ready for schema design. Technical and macro may proceed to schema design. Fundamental and sentiment remain blocked until dedicated audits. No feature ingestion, feature calculation, signal, backtest, model, paper-trading deployment, promotion, or final-candidate change exists.

---

# Methodology Notes

## Research Period Pinning

The canonical Phase 2+ research endpoint is pinned in configuration:

```yaml
research_period:
  phase1_start_date: "1993-01-29"
  phase2_start_date: "2006-04-28"
  end_date: "2026-05-01"
```

This was added after a data-refresh drift caused some exploratory reports to extend to `2026-05-13`. The pinned endpoint prevents refreshed data from silently changing validated results.

Canonical README numbers, including Phase 8 and Phase 9A diagnostics, should be read as **2026-05-01 pinned checkpoint results** unless a deliberately refreshed checkpoint is opened.

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
- simplified tax-drag modelling only; no production-grade tax engine,
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
- Phase 8A used a simplified turnover-based tax proxy only. It does not model tax lots, dividends, final liquidation, wash-sale rules, holding-period rules, jurisdiction-specific treatment, or investor-specific tax circumstances.
- The final candidate survived the 20% tax-drag proxy, but its CAGR edge over SPY 12M disappeared under the harsher 30% proxy.
- Phase 8B used scenario-based bid-ask / market-impact stress only. It does not model order books, intraday liquidity, broker routing, partial fills, or production execution.
- Phase 8B failed the configured stress gate: the final candidate kept its Calmar and drawdown edge but lost its CAGR edge versus SPY 12M under stress.
- Phase 8B added scenario-based bid-ask / market-impact stress testing, but the project still lacks production-grade execution modelling, including order books, intraday liquidity, routing, partial fills, broker-specific fills, and real execution reconciliation.
- The final candidate is materially more sensitive to added execution friction than SPY 12M because it has higher turnover.
- Phase 8C was a walk-forward / expanding-window audit, not a full prospective model-selection framework. The final candidate had already been selected before the audit.
- Phase 8C failed / produced mixed evidence: the candidate stayed positive in all forward windows and often improved drawdown, but it did not beat SPY 12M on CAGR or Calmar often enough.
- Phase 8D failed / showed material behavioural regret. The final candidate remained ahead of SPY 12M on terminal relative wealth, but relative drawdown versus SPY Buy & Hold reached -57.38% and worst 3Y active CAGR versus Buy & Hold was -18.17%.
- Lower absolute drawdown does not mean the strategy is behaviourally easy to hold; tracking-error regret versus SPY Buy & Hold remains a material liveability risk.
- Phase 8E documented research degrees of freedom across 11 research branches. This is not a formal multiple-comparisons correction, but it reinforces that final-candidate claims must remain narrow.
- The final candidate emerged after many tested and rejected branches, so it should not be described as a broadly proven or statistically definitive market-beating system.
- Phase 8F confirmed the non-production boundary. Market Strats Lab remains a research-grade systematic strategy lab, not a production trading system, not financial advice, and not a live-trading recommendation.
- Phase 8F documented 7 critical production blockers across data, execution, tax, monitoring, governance, and compliance.
- A Phase 8F pass means the boundary was documented clearly; it does not mean the strategy is production-ready.
- Phase 8G was a final checkpoint / README consistency audit. It confirmed that Phase 8 documentation, config flags, report artefacts, hierarchy, dates, and caveat wording were internally consistent. It was not a strategy test, not production approval, and did not make the final candidate live-tradable.
- Phase 9A was diagnostic only. It identified technical-regime clusters where the final candidate helped or lagged, but it did not create, tune, validate, or promote a new trading rule.
- Any future technical indicator rule must be pre-defined and separately validated. Phase 9A cluster evidence cannot be treated as proof of a new strategy.
- Phase 9B was diagnostic only. It showed that some technical clusters, especially oversold RSI and negative 12-month momentum regimes, were more stable, but most clusters were not stable across both benchmarks. Phase 9A/9B cluster evidence should not be treated as a validated trading rule.
- Phase 9C was a pre-registration step only. It did not test, tune, validate, or promote any technical rule. Phase 9D must follow this spec exactly or be rejected as post-hoc rule design.
- Phase 9D showed that diagnostic technical-regime evidence did not translate into a validated rule. Both pre-registered technical rules failed, so Phase 9A/9B cluster evidence should remain diagnostic rather than promotional.
- Phase 9E closed the technical-extension branch without promotion. This confirms that the Phase 9A/9B diagnostic evidence did not translate into a validated technical rule through the Phase 9C/9D pre-registration path.
- Phase 9F confirmed Phase 9 was internally consistent after closeout, but it did not create a new strategy, validate a technical rule, or change the final candidate hierarchy.
- Phase 10A was a feasibility specification only. It selected macro/rates/inflation as the first non-price feature family to audit, but did not ingest data, train a model, test a strategy, or promote any candidate.
- Phase 10B was a feasibility audit only. It identified macro/rates/inflation sources suitable for a later Phase 10C source reliability and point-in-time alignment audit, but did not download data, create macro features, test allocation rules, train models, or promote any candidate.
- Phase 10C loaded and aligned selected macro/rates/inflation data, but it remained an audit only. Current/revised macro values may still carry revision risk, and no macro signal, model feature, strategy test, allocation rule, or candidate promotion was created.
- Phase 10D was diagnostic only. Macro/rates/inflation regimes helped describe where the final candidate looked stronger or weaker, but no macro rule, signal, model feature, allocation overlay, strategy test, or candidate promotion was created.
- Phase 10E only pre-registered macro hypotheses. It did not test whether the hypotheses work, create a macro strategy, add an allocation overlay, train a model, or promote any candidate.
- Phase 10F failed. The two pre-registered macro hypotheses did not pass all validation gates. H1 improved headline CAGR but worsened drawdown and created raw-CAGR overclaim risk; H2 looked more promising but failed episode-damage and stress-friction gates. No macro rule was promoted and no tuning around the failure is allowed.
- Phase 10G closed the macro/rates/inflation branch without promotion. Macro evidence was feasible and diagnostically informative, but the pre-registered macro-rule test failed. No macro rule, allocation overlay, model feature, strategy successor, or promoted candidate exists.
- Phase 10H closed the Phase 10 macro/rates/inflation record cleanly. Macro data was feasible and diagnostically informative, but no macro rule survived pre-registered validation and no macro successor candidate exists.
- Phase 11A was architecture review only. It did not create a richer-information model, regime score, strategy test, allocation rule, or candidate promotion. It only concluded that the next research step should be architecture-led rather than another simple rule overlay.
- Phase 11B was architecture-spec only. It defined the regime-scoring structure conceptually but did not calculate scores, choose weights, create signals, test allocation rules, ingest new data, train models, or promote any candidate.
- Phase 11C was rulebook-spec only. It defined conceptual scoring directions, missingness rules, weighting principles, audit outputs, and future validation gates, but no regime score, signal, allocation rule, strategy test, model, new data ingestion, or promoted candidate exists.
- Phase 11D was diagnostic-panel design only. It defined future report layouts and required columns but did not implement a regime score, assign weights, create signals, run strategy tests, ingest new data, train models, or promote any candidate.
- Phase 11E was a diagnostic-panel template implementation audit only. It created schema-compliant reporting templates but did not calculate regime scores, assign weights, create signals, run strategy tests, ingest new data, train models, or promote any candidate.
- Phase 11F was a diagnostic-panel content audit only. It verified template content consistency but did not calculate regime scores, assign weights, create signals, run strategy tests, ingest new data, train models, or promote any candidate.
- Phase 11G closed the regime-scoring preparation branch only. Phase 11 prepared the architecture, rulebook, diagnostic panels, templates, and content audits, but no regime score, score weights, signal, strategy test, model, new data ingestion, or promoted candidate exists.
- Phase 12A and Phase 12B prepared and locked the diagnostic score-calculation design only. No regime score, score values, empirical weights, signal, allocation rule, strategy test, model, new data ingestion, or promoted candidate exists yet.
- Phase 12C/12D calculated and audited a categorical diagnostic regime score only. The score is not a trading signal, allocation rule, strategy backtest, empirical model, live-trading input, candidate promotion, or final-candidate change.
- Phase 12E/12F closed the diagnostic score branch only. The project now has a calculated and interpreted fragile diagnostic regime score, but it is not a trading signal, allocation rule, strategy backtest, empirical model, live-trading input, candidate promotion, or final-candidate change.
- Phase 13A/13B are architecture-planning phases only. They freeze the SPY regime-switch arc as a baseline framework and define the multi-factor model roadmap, but no new features have been ingested, no model has been trained, no signal has been created, no backtest has been run, no paper-trading system exists, and no candidate has been promoted.
- Phase 13C/13D defined and audited feature-source inventory and contract readiness only. No features have been ingested or calculated, no model has been trained, no signal or allocation rule exists, no backtest has been run, no paper-trading system exists, and no candidate has been promoted.
- Fundamental and sentiment families remain blocked until dedicated source/leakage/noise audits pass.
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
- Phase 8A tax-drag test used approximate float assertions after floating-point precision caused an exact equality test failure

---

# Project Structure

```text
Market-strats-lab/
├── configs/
│   └── spy_sma10.yaml
├── data/
│   ├── processed/
│   └── raw/
├── experiments/
├── reports/
├── src/
│   └── market_strats/
│       ├── __init__.py
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

## Phase 8A Tax-Drag Reports

```text
reports/phase8a_tax_drag_metrics.csv
reports/phase8a_tax_drag_daily_returns.csv
reports/phase8a_tax_drag_summary.csv
reports/phase8a_tax_drag_gate_report.csv
reports/phase8a_tax_drag_conclusion.csv
reports/phase8a_tax_drag_diagnostic.md
```

## Phase 8B Bid-Ask / Market-Impact Reports

```text
reports/phase8b_bid_ask_market_impact_daily_returns.csv
reports/phase8b_bid_ask_market_impact_metrics.csv
reports/phase8b_bid_ask_market_impact_summary.csv
reports/phase8b_bid_ask_market_impact_gate_report.csv
reports/phase8b_bid_ask_market_impact_conclusion.csv
reports/phase8b_bid_ask_market_impact_diagnostic.md
```

## Phase 8C Walk-Forward Validation Reports

```text
reports/phase8c_walk_forward_windows.csv
reports/phase8c_walk_forward_metrics.csv
reports/phase8c_walk_forward_summary.csv
reports/phase8c_walk_forward_gate_report.csv
reports/phase8c_walk_forward_conclusion.csv
reports/phase8c_walk_forward_validation_audit.md
```

## Phase 8D Behavioural Regret Reports

```text
reports/phase8d_behavioural_regret_daily.csv
reports/phase8d_behavioural_regret_summary.csv
reports/phase8d_behavioural_regret_rolling_windows.csv
reports/phase8d_behavioural_regret_rolling_summary.csv
reports/phase8d_behavioural_regret_gate_report.csv
reports/phase8d_behavioural_regret_conclusion.csv
reports/phase8d_behavioural_regret_audit.md
```

## Phase 8E Research Degrees-of-Freedom Reports

```text
reports/phase8e_research_degrees_of_freedom_inventory.csv
reports/phase8e_research_degrees_of_freedom_summary.csv
reports/phase8e_research_degrees_of_freedom_claim_adjustment.csv
reports/phase8e_research_degrees_of_freedom_gate_report.csv
reports/phase8e_research_degrees_of_freedom_conclusion.csv
reports/phase8e_research_degrees_of_freedom_audit.md
```

## Phase 8F Research-Only Boundary Reports

```text
reports/phase8f_production_boundary_blocker_inventory.csv
reports/phase8f_production_boundary_category_summary.csv
reports/phase8f_production_boundary_summary.csv
reports/phase8f_production_boundary_statement.csv
reports/phase8f_production_boundary_gate_report.csv
reports/phase8f_production_boundary_conclusion.csv
reports/phase8f_production_readiness_boundary_audit.md
```

## Phase 8G Final Phase 8 Checkpoint Reports

```text
reports/phase8g_final_checkpoint_readme_phrase_check.csv
reports/phase8g_final_checkpoint_config_flag_check.csv
reports/phase8g_final_checkpoint_report_inventory_check.csv
reports/phase8g_final_checkpoint_canonical_check.csv
reports/phase8g_final_checkpoint_gate_report.csv
reports/phase8g_final_checkpoint_conclusion.csv
reports/phase8g_final_phase8_checkpoint_audit.md
```

## Phase 9A Technical Indicator Diagnostic Reports

```text
reports/phase9a_technical_indicator_frame.csv
reports/phase9a_technical_regime_frame.csv
reports/phase9a_technical_indicator_analysis_frame.csv
reports/phase9a_technical_regime_summary.csv
reports/phase9a_technical_underperformance_clusters.csv
reports/phase9a_technical_indicator_summary.csv
reports/phase9a_technical_indicator_gate_report.csv
reports/phase9a_technical_indicator_conclusion.csv
reports/phase9a_technical_indicator_expansion_diagnostic.md
```

## Phase 9B Technical Regime Cluster Stability Reports

```text
reports/phase9b_technical_cluster_analysis_frame.csv
reports/phase9b_technical_cluster_episode_frame.csv
reports/phase9b_technical_cluster_episode_metrics.csv
reports/phase9b_technical_cluster_stability_summary.csv
reports/phase9b_technical_cluster_instability_report.csv
reports/phase9b_technical_cluster_helpful_stability_report.csv
reports/phase9b_technical_cluster_summary.csv
reports/phase9b_technical_cluster_gate_report.csv
reports/phase9b_technical_cluster_conclusion.csv
reports/phase9b_technical_regime_cluster_stability_audit.md
```

## Phase 9C Pre-Registered Technical Rule Design Spec Reports

```text
reports/phase9c_preregistered_rule_hypothesis_spec.csv
reports/phase9c_preregistered_rule_allowed_inputs.csv
reports/phase9c_preregistered_rule_forbidden_inputs.csv
reports/phase9c_preregistered_rule_validation_gates.csv
reports/phase9c_preregistered_rule_forbidden_actions.csv
reports/phase9c_preregistered_rule_summary.csv
reports/phase9c_preregistered_rule_gate_report.csv
reports/phase9c_preregistered_rule_conclusion.csv
reports/phase9c_preregistered_technical_rule_design_spec.md
```

## Phase 9D Pre-Registered Technical Rule Test Reports

```text
reports/phase9d_preregistered_rule_returns.csv
reports/phase9d_preregistered_rule_metrics.csv
reports/phase9d_preregistered_rule_stress_metrics.csv
reports/phase9d_preregistered_rule_behavioural_metrics.csv
reports/phase9d_preregistered_rule_comparison_summary.csv
reports/phase9d_preregistered_rule_gate_report.csv
reports/phase9d_preregistered_rule_conclusion.csv
reports/phase9d_preregistered_technical_rule_test.md
```

## Phase 9E Technical Extension Closeout Reports

```text
reports/phase9e_technical_extension_report_inventory_check.csv
reports/phase9e_technical_extension_config_flag_check.csv
reports/phase9e_technical_extension_phase9d_failure_check.csv
reports/phase9e_technical_extension_closeout_summary.csv
reports/phase9e_technical_extension_gate_report.csv
reports/phase9e_technical_extension_conclusion.csv
reports/phase9e_technical_extension_closeout_audit.md
```

## Phase 9F Final Phase 9 Checkpoint Reports

```text
reports/phase9f_final_checkpoint_readme_phrase_check.csv
reports/phase9f_final_checkpoint_config_flag_check.csv
reports/phase9f_final_checkpoint_report_inventory_check.csv
reports/phase9f_final_checkpoint_canonical_check.csv
reports/phase9f_final_checkpoint_closeout_check.csv
reports/phase9f_final_checkpoint_summary.csv
reports/phase9f_final_checkpoint_gate_report.csv
reports/phase9f_final_checkpoint_conclusion.csv
reports/phase9f_final_phase9_checkpoint_audit.md
```

## Phase 10A Feature-Family Feasibility Reports

```text
reports/phase10a_feature_family_spec.csv
reports/phase10a_feature_family_data_requirements.csv
reports/phase10a_feature_family_leakage_controls.csv
reports/phase10a_feature_family_validation_requirements.csv
reports/phase10a_feature_family_scorecard.csv
reports/phase10a_feature_family_recommendation.csv
reports/phase10a_feature_family_summary.csv
reports/phase10a_feature_family_gate_report.csv
reports/phase10a_feature_family_conclusion.csv
reports/phase10a_feature_family_feasibility_spec.md
```

## Phase 10B Macro Data-Source Leakage Feasibility Reports

```text
reports/phase10b_macro_source_catalog.csv
reports/phase10b_macro_timing_revision_check.csv
reports/phase10b_macro_leakage_control_check.csv
reports/phase10b_macro_source_recommendation.csv
reports/phase10b_macro_phase10c_boundary_check.csv
reports/phase10b_macro_summary.csv
reports/phase10b_macro_gate_report.csv
reports/phase10b_macro_conclusion.csv
reports/phase10b_macro_data_source_leakage_audit.md
```

## Phase 10C Macro Source Reliability / Alignment Reports

```text
reports/phase10c_macro_source_catalog.csv
reports/phase10c_macro_series_catalog.csv
reports/phase10c_macro_raw_series.csv
reports/phase10c_macro_load_report.csv
reports/phase10c_macro_aligned_series.csv
reports/phase10c_macro_coverage_alignment_summary.csv
reports/phase10c_macro_phase10d_readiness.csv
reports/phase10c_macro_phase10d_boundary_check.csv
reports/phase10c_macro_summary.csv
reports/phase10c_macro_gate_report.csv
reports/phase10c_macro_conclusion.csv
reports/phase10c_macro_source_reliability_alignment_audit.md
```

## Phase 10D Diagnostic Macro Regime Reports

```text
reports/phase10d_macro_panel.csv
reports/phase10d_macro_regime_frame.csv
reports/phase10d_macro_analysis_frame.csv
reports/phase10d_macro_regime_metrics.csv
reports/phase10d_macro_helpful_regime_report.csv
reports/phase10d_macro_weak_regime_report.csv
reports/phase10d_macro_phase10e_boundary_check.csv
reports/phase10d_macro_summary.csv
reports/phase10d_macro_gate_report.csv
reports/phase10d_macro_conclusion.csv
reports/phase10d_diagnostic_macro_regime_analysis.md
```

## Phase 10E Pre-Registered Macro Hypothesis Reports

```text
reports/phase10e_macro_input_registry.csv
reports/phase10e_macro_hypothesis_spec.csv
reports/phase10e_macro_allowed_inputs.csv
reports/phase10e_macro_forbidden_inputs.csv
reports/phase10e_macro_validation_gates.csv
reports/phase10e_macro_failure_conditions.csv
reports/phase10e_macro_phase10f_boundary_check.csv
reports/phase10e_macro_summary.csv
reports/phase10e_macro_gate_report.csv
reports/phase10e_macro_conclusion.csv
reports/phase10e_preregistered_macro_hypothesis_spec.md
```

## Phase 10F Pre-Registered Macro Rule Test Reports

```text
reports/phase10f_macro_panel.csv
reports/phase10f_macro_rule_activation_frame.csv
reports/phase10f_macro_rule_returns.csv
reports/phase10f_macro_rule_metrics.csv
reports/phase10f_macro_benchmark_metrics.csv
reports/phase10f_macro_episode_metrics.csv
reports/phase10f_macro_behavioural_metrics.csv
reports/phase10f_macro_rule_gate_report.csv
reports/phase10f_macro_rule_comparison_summary.csv
reports/phase10f_macro_discipline_gate_report.csv
reports/phase10f_macro_conclusion.csv
reports/phase10f_preregistered_macro_rule_test.md
```

## Phase 10G Macro Extension Closeout Reports

```text
reports/phase10g_macro_closeout_report_inventory_check.csv
reports/phase10g_macro_closeout_config_flag_check.csv
reports/phase10g_macro_closeout_phase10f_failure_check.csv
reports/phase10g_macro_closeout_summary.csv
reports/phase10g_macro_closeout_gate_report.csv
reports/phase10g_macro_closeout_conclusion.csv
reports/phase10g_macro_extension_closeout_audit.md
```

## Phase 10H Final Phase 10 Checkpoint Reports

```text
reports/phase10h_final_checkpoint_readme_phrase_check.csv
reports/phase10h_final_checkpoint_config_flag_check.csv
reports/phase10h_final_checkpoint_report_inventory_check.csv
reports/phase10h_final_checkpoint_phase10g_closeout_check.csv
reports/phase10h_final_checkpoint_canonical_hierarchy_check.csv
reports/phase10h_final_checkpoint_summary.csv
reports/phase10h_final_checkpoint_gate_report.csv
reports/phase10h_final_checkpoint_conclusion.csv
reports/phase10h_final_phase10_checkpoint_audit.md
```

## Phase 11A Richer-Information Architecture Review Reports

```text
reports/phase11a_architecture_prior_branch_findings.csv
reports/phase11a_architecture_candidates.csv
reports/phase11a_architecture_risk_matrix.csv
reports/phase11a_architecture_recommendation.csv
reports/phase11a_architecture_boundary_check.csv
reports/phase11a_architecture_summary.csv
reports/phase11a_architecture_gate_report.csv
reports/phase11a_architecture_conclusion.csv
reports/phase11a_richer_information_architecture_review.md
```

## Phase 11B Regime Scoring Architecture Spec Reports

```text
reports/phase11b_regime_scoring_source_decision.csv
reports/phase11b_regime_scoring_principles.csv
reports/phase11b_regime_scoring_component_registry.csv
reports/phase11b_regime_scoring_state_design.csv
reports/phase11b_regime_scoring_validation_requirements.csv
reports/phase11b_regime_scoring_phase11c_boundary_check.csv
reports/phase11b_regime_scoring_scope_boundary_check.csv
reports/phase11b_regime_scoring_summary.csv
reports/phase11b_regime_scoring_gate_report.csv
reports/phase11b_regime_scoring_conclusion.csv
reports/phase11b_regime_scoring_architecture_spec.md
```

## Phase 11C Regime Scoring Rulebook Spec Reports

```text
reports/phase11c_regime_scoring_source_architecture.csv
reports/phase11c_regime_scoring_component_rulebook.csv
reports/phase11c_regime_scoring_conceptual_direction_rulebook.csv
reports/phase11c_regime_scoring_missingness_rules.csv
reports/phase11c_regime_scoring_weighting_principles.csv
reports/phase11c_regime_scoring_state_rulebook.csv
reports/phase11c_regime_scoring_audit_output_spec.csv
reports/phase11c_regime_scoring_future_validation_gates.csv
reports/phase11c_regime_scoring_phase11d_boundary_check.csv
reports/phase11c_regime_scoring_scope_boundary_check.csv
reports/phase11c_regime_scoring_summary.csv
reports/phase11c_regime_scoring_gate_report.csv
reports/phase11c_regime_scoring_conclusion.csv
reports/phase11c_regime_scoring_rulebook_spec.md
```

## Phase 11D Regime Scoring Diagnostic Panel Design Reports

```text
reports/phase11d_diagnostic_panel_source_rulebook.csv
reports/phase11d_diagnostic_panel_layout_spec.csv
reports/phase11d_diagnostic_panel_required_columns_spec.csv
reports/phase11d_diagnostic_panel_component_availability_spec.csv
reports/phase11d_diagnostic_panel_conceptual_direction_spec.csv
reports/phase11d_diagnostic_panel_missingness_policy_spec.csv
reports/phase11d_diagnostic_panel_weighting_policy_spec.csv
reports/phase11d_diagnostic_panel_blocked_family_spec.csv
reports/phase11d_diagnostic_panel_phase11e_boundary_check.csv
reports/phase11d_diagnostic_panel_scope_boundary_check.csv
reports/phase11d_diagnostic_panel_summary.csv
reports/phase11d_diagnostic_panel_gate_report.csv
reports/phase11d_diagnostic_panel_conclusion.csv
reports/phase11d_regime_scoring_diagnostic_panel_design.md
```

## Phase 11E Regime Scoring Diagnostic Panel Template Audit Reports

```text
reports/phase11e_template_component_availability_report.csv
reports/phase11e_template_component_direction_report.csv
reports/phase11e_template_missingness_report.csv
reports/phase11e_template_weighting_policy_report.csv
reports/phase11e_template_blocked_family_report.csv
reports/phase11e_template_boundary_report.csv
reports/phase11e_template_source_design_inventory.csv
reports/phase11e_template_inventory.csv
reports/phase11e_template_schema_compliance.csv
reports/phase11e_template_phase11f_boundary_check.csv
reports/phase11e_template_summary.csv
reports/phase11e_template_gate_report.csv
reports/phase11e_template_conclusion.csv
reports/phase11e_regime_scoring_diagnostic_panel_template_audit.md
```

## Phase 11F Regime Scoring Diagnostic Panel Content Audit Reports

```text
reports/phase11f_content_source_template_inventory.csv
reports/phase11f_content_phase11e_result_check.csv
reports/phase11f_content_component_check.csv
reports/phase11f_content_direction_check.csv
reports/phase11f_content_missingness_check.csv
reports/phase11f_content_weighting_check.csv
reports/phase11f_content_blocked_family_check.csv
reports/phase11f_content_boundary_check.csv
reports/phase11f_content_phase11g_boundary_check.csv
reports/phase11f_content_scope_boundary_check.csv
reports/phase11f_content_summary.csv
reports/phase11f_content_gate_report.csv
reports/phase11f_content_conclusion.csv
reports/phase11f_regime_scoring_diagnostic_panel_content_audit.md
```

## Phase 11G Final Regime Scoring Checkpoint Reports

```text
reports/phase11g_final_checkpoint_report_inventory_check.csv
reports/phase11g_final_checkpoint_config_flag_check.csv
reports/phase11g_final_checkpoint_phase_conclusion_check.csv
reports/phase11g_final_checkpoint_phase_gate_report_check.csv
reports/phase11g_final_checkpoint_boundary_report_check.csv
reports/phase11g_final_checkpoint_branch_closure_check.csv
reports/phase11g_final_checkpoint_phase12a_boundary_check.csv
reports/phase11g_final_checkpoint_scope_boundary_check.csv
reports/phase11g_final_checkpoint_summary.csv
reports/phase11g_final_checkpoint_gate_report.csv
reports/phase11g_final_checkpoint_conclusion.csv
reports/phase11g_final_regime_scoring_checkpoint_audit.md
```

## Phase 12A Score-Calculation Pre-Registration Reports

```text
reports/phase12a_prereg_source_input_check.csv
reports/phase12a_prereg_eligible_components.csv
reports/phase12a_prereg_blocked_components.csv
reports/phase12a_prereg_formula_structure.csv
reports/phase12a_prereg_weighting_policy.csv
reports/phase12a_prereg_missingness_policy.csv
reports/phase12a_prereg_score_state_interpretation.csv
reports/phase12a_prereg_future_validation_gates.csv
reports/phase12a_prereg_failure_conditions.csv
reports/phase12a_prereg_phase12b_boundary_check.csv
reports/phase12a_prereg_scope_boundary_check.csv
reports/phase12a_prereg_summary.csv
reports/phase12a_prereg_gate_report.csv
reports/phase12a_prereg_conclusion.csv
reports/phase12a_score_calculation_preregistration_spec.md
```

## Phase 12B Score-Calculation Readiness Audit Reports
```text
reports/phase12b_readiness_report_inventory_check.csv
reports/phase12b_readiness_phase12a_result_check.csv
reports/phase12b_readiness_config_flag_check.csv
reports/phase12b_readiness_readiness_claims_check.csv
reports/phase12b_readiness_phase12c_boundary_check.csv
reports/phase12b_readiness_scope_boundary_check.csv
reports/phase12b_readiness_summary.csv
reports/phase12b_readiness_gate_report.csv
reports/phase12b_readiness_conclusion.csv
reports/phase12b_score_calculation_readiness_audit.md
```

## Phase 12C Diagnostic Score Calculation Reports

```text
reports/phase12c_score_source_report_check.csv
reports/phase12c_score_phase12b_result_check.csv
reports/phase12c_score_component_state_panel.csv
reports/phase12c_score_component_state_distribution.csv
reports/phase12c_score_aggregate_score.csv
reports/phase12c_score_phase12d_boundary_check.csv
reports/phase12c_score_scope_boundary_check.csv
reports/phase12c_score_summary.csv
reports/phase12c_score_gate_report.csv
reports/phase12c_score_conclusion.csv
reports/phase12c_diagnostic_score_calculation.md
```
## Phase 12D Diagnostic Score Distribution Audit Reports

```text
reports/phase12d_audit_source_score_report_check.csv
reports/phase12d_audit_phase12c_result_check.csv
reports/phase12d_audit_distribution_check.csv
reports/phase12d_audit_forbidden_column_check.csv
reports/phase12d_audit_phase12e_boundary_check.csv
reports/phase12d_audit_summary.csv
reports/phase12d_audit_gate_report.csv
reports/phase12d_audit_conclusion.csv
reports/phase12d_diagnostic_score_distribution_audit.md
```

## Phase 12E Diagnostic Score Interpretation / Closeout Reports

```text
reports/phase12e_interpretation_source_report_check.csv
reports/phase12e_interpretation_phase12d_result_check.csv
reports/phase12e_interpretation_score_interpretation.csv
reports/phase12e_interpretation_closeout_claims_check.csv
reports/phase12e_interpretation_phase12f_boundary_check.csv
reports/phase12e_interpretation_scope_boundary_check.csv
reports/phase12e_interpretation_summary.csv
reports/phase12e_interpretation_gate_report.csv
reports/phase12e_interpretation_conclusion.csv
reports/phase12e_diagnostic_score_interpretation_closeout.md
```

## Phase 12F Final Diagnostic Score Checkpoint Reports

```text
reports/phase12f_final_report_inventory_check.csv
reports/phase12f_final_config_flag_check.csv
reports/phase12f_final_phase_conclusion_check.csv
reports/phase12f_final_phase_gate_report_check.csv
reports/phase12f_final_branch_closure_claims_check.csv
reports/phase12f_final_future_phase13_boundary_check.csv
reports/phase12f_final_scope_boundary_check.csv
reports/phase12f_final_summary.csv
reports/phase12f_final_gate_report.csv
reports/phase12f_final_conclusion.csv
reports/phase12f_final_diagnostic_score_checkpoint_audit.md
```

## Phase 13A Baseline Research Arc Freeze Reports

```text
reports/phase13a_baseline_freeze_source_report_check.csv
reports/phase13a_baseline_freeze_phase12f_result_check.csv
reports/phase13a_baseline_freeze_baseline_freeze_report.csv
reports/phase13a_baseline_freeze_transition_decision_report.csv
reports/phase13a_baseline_freeze_phase13b_boundary_check.csv
reports/phase13a_baseline_freeze_scope_boundary_check.csv
reports/phase13a_baseline_freeze_summary.csv
reports/phase13a_baseline_freeze_gate_report.csv
reports/phase13a_baseline_freeze_conclusion.csv
reports/phase13a_baseline_research_arc_freeze_spec.md
```

## Phase 13B Multi-Factor Model Architecture Roadmap Reports

```text
reports/phase13b_roadmap_phase13a_result_check.csv
reports/phase13b_roadmap_feature_family_registry.csv
reports/phase13b_roadmap_architecture_candidates.csv
reports/phase13b_roadmap_dissertation_integration_plan.csv
reports/phase13b_roadmap_walk_forward_design.csv
reports/phase13b_roadmap_visual_reporting_plan.csv
reports/phase13b_roadmap_paper_trading_readiness_plan.csv
reports/phase13b_roadmap_phase13c_boundary_check.csv
reports/phase13b_roadmap_scope_boundary_check.csv
reports/phase13b_roadmap_summary.csv
reports/phase13b_roadmap_gate_report.csv
reports/phase13b_roadmap_conclusion.csv
reports/phase13b_multifactor_model_architecture_roadmap_spec.md
```

## Phase 13C Feature-Source Inventory Reports

```text
reports/phase13c_inventory_source_report_check.csv
reports/phase13c_inventory_phase13b_result_check.csv
reports/phase13c_inventory_feature_source_inventory.csv
reports/phase13c_inventory_feature_contract_requirements.csv
reports/phase13c_inventory_leakage_control_policy.csv
reports/phase13c_inventory_blocked_family_policy.csv
reports/phase13c_inventory_phase13d_boundary_check.csv
reports/phase13c_inventory_scope_boundary_check.csv
reports/phase13c_inventory_summary.csv
reports/phase13c_inventory_gate_report.csv
reports/phase13c_inventory_conclusion.csv
reports/phase13c_multifactor_feature_source_inventory_spec.md
```

## Phase 13D Feature Contract Readiness Reports

```text
reports/phase13d_contract_report_inventory_check.csv
reports/phase13d_contract_phase13c_result_check.csv
reports/phase13d_contract_config_flag_check.csv
reports/phase13d_contract_readiness_claims_check.csv
reports/phase13d_contract_contract_coverage_check.csv
reports/phase13d_contract_blocked_family_check.csv
reports/phase13d_contract_phase13e_boundary_check.csv
reports/phase13d_contract_scope_boundary_check.csv
reports/phase13d_contract_summary.csv
reports/phase13d_contract_gate_report.csv
reports/phase13d_contract_conclusion.csv
reports/phase13d_feature_contract_readiness_audit.md
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
- Simplified tax-drag diagnostic
- Bid-ask / market-impact stress diagnostic
- Walk-forward / expanding-window validation audit
- Behavioural / tracking-error regret audit
- Multiple-comparisons / research-degrees-of-freedom audit
- Research-only / non-production boundary audit
- Final Phase 8 checkpoint / README consistency audit
- Technical indicator expansion diagnostic
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
| Phase 8A simplified tax-drag diagnostic | Completed — survived at 20% tax proxy with caveat; CAGR edge over SPY 12M disappeared under 30% proxy |
| Phase 8B bid-ask / market-impact stress diagnostic | Completed — failed configured stress gate; candidate kept Calmar/drawdown edge but lost CAGR edge versus SPY 12M under stress |
| Phase 8C walk-forward / expanding-window validation audit | Completed — failed / mixed evidence; candidate stayed positive in all forward windows but failed CAGR/Calmar consistency gates |
| Phase 8D behavioural / tracking-error regret audit | Completed — failed / material behavioural regret; relative drawdown and worst 3Y active CAGR versus Buy & Hold failed gates |
| Phase 8E research-degrees-of-freedom audit | Completed — claims narrowed; 11 branches documented, 25 failed/rejected units, promoted share 15.38% |
| Phase 8F boundary-control / non-production boundary audit | Completed — research-only boundary documented; not production-ready, not live-tradable, not financial advice |
| Phase 8G final Phase 8 checkpoint audit | Completed — Phase 8 checkpoint consistent; README/config/report consistency passed |
| Phase 9A technical indicator expansion diagnostic | Completed — diagnostic only; 94.99% indicator coverage, 25 regime rows, 15 underperformance cluster rows, no strategy promotion |
| Phase 9B technical regime cluster stability audit | Completed — diagnostic only; 25 stability rows, 6 stable across both benchmarks, 19 unstable rows, no strategy promotion |
| Phase 9C pre-registered technical rule design spec | Completed — pre-registered spec only; 2 bounded hypotheses, 8 allowed input rows, 18 validation gate rows, no strategy testing, no optimisation, no promotion |
| Phase 9D pre-registered technical rule test | Failed — no pre-registered rule passed; both H1 oversold RSI relief and H2 negative 12M momentum confirmation failed validation gates |
| Phase 9E technical extension closeout audit | Completed — technical extension closed without promotion; Phase 9D failure documented, no technical rule promoted, no successor candidate created |
| Phase 9F final Phase 9 checkpoint audit | Completed — Phase 9 checkpoint consistent; README wording, config flags, report inventory, hierarchy, and closeout documentation passed |
| Phase 10A feature-family feasibility spec | Completed — feature-family feasibility spec only; macro/rates/inflation selected as first non-price family to audit in Phase 10B |
| Phase 10B macro/rates/inflation data-source leakage audit | Completed — data-source and leakage feasibility audit only; FRED/ALFRED, Treasury/rates, and BLS CPI selected for Phase 10C source reliability/alignment audit; no data download, feature engineering, signal creation, model training, strategy testing, or promotion |
| Phase 10C macro source reliability and point-in-time alignment audit | Completed — source reliability/alignment audit passed; UNRATE, DGS2, DGS10, and CPIAUCSL loaded and aligned; Phase 10D allowed only as diagnostic macro regime analysis |
| Phase 10D diagnostic-only macro regime analysis | Completed — diagnostic-only macro/rates/inflation regime analysis; 5 regime families and 15 regime metric rows generated; no macro signal, strategy test, model, allocation rule, or promotion |
| Phase 10E pre-registered macro hypothesis design spec | Completed — exactly two macro hypotheses pre-registered for possible Phase 10F testing; no macro signal, allocation overlay, model feature, strategy test, or promotion |
| Phase 10F pre-registered macro rule test | Failed — no pre-registered macro rule passed all configured gates; H1 failed risk/overclaim/friction gates and H2 failed episode-damage and stress-friction gates; no promotion |
| Phase 10G macro extension closeout audit | Completed — macro/rates/inflation branch closed without promotion; Phase 10F failure documented; no macro rule passed, no successor candidate created, and final hierarchy unchanged |
| Phase 10H final Phase 10 checkpoint audit | Completed — final Phase 10 README/config/report consistency audit passed; Phase 10F failure locked, Phase 10G closeout documented, no macro successor candidate created, and final hierarchy unchanged |
| Phase 11A richer-information architecture review | Completed — architecture review passed; simple if/then overlays rejected as the immediate next step; preferred next step is Phase 11B regime-scoring architecture spec; no strategy test, model, or promotion |
| Phase 11B regime scoring architecture spec | Completed — design-only regime-scoring architecture spec passed; technical, macro, and validation-risk components defined conceptually; future fundamental/sentiment components blocked; no score calculation, signal, backtest, model, or promotion |
| Phase 11C regime scoring rulebook spec | Completed — rulebook-spec phase passed; conceptual technical, macro, and validation-risk directions documented; future fundamental/sentiment components blocked; no score calculation, signal, backtest, model, new data ingestion, or promotion |
| Phase 11D regime scoring diagnostic panel design | Completed — diagnostic panel design passed; panel layouts, required columns, component availability, conceptual direction, missingness, weighting-policy, blocked-family, and boundary reports designed; no score, signal, backtest, model, new data ingestion, or promotion |
| Phase 11E regime scoring diagnostic panel template implementation audit | Completed — schema-compliant diagnostic panel templates generated; required columns, blocked-family rows, boundary rows, and non-signal/non-return constraints verified; no score, signal, backtest, model, new data ingestion, or promotion |
| Phase 11F regime scoring diagnostic panel content audit | Completed — diagnostic panel content audit passed; component, direction, missingness, weighting, blocked-family, and boundary content verified; no score, signal, backtest, model, new data ingestion, or promotion |
| Phase 11G final regime scoring closeout/checkpoint audit | Completed — final Phase 11 checkpoint passed; Phase 11A–11F reports and gates verified, config flags clean, branch closed without score/signal/backtest/model/new data/promotion, and Phase 12A limited to score-calculation pre-registration spec only |
| Phase 12A score-calculation pre-registration spec | Completed — score-calculation design pre-registered; eligible technical, macro/rates/inflation, and validation-risk components locked; fundamental/sentiment components blocked; formula grammar, non-return weighting policy, missingness handling, validation gates, and failure conditions documented; no score/signal/backtest/model/new data/promotion |
| Phase 12B score-calculation readiness audit | Completed — readiness audit passed; Phase 12A reports and gates verified, readiness claims locked, and Phase 12C limited to diagnostic score calculation only; no score/signal/backtest/model/new data/promotion |
| Phase 12C diagnostic score calculation | Completed — diagnostic score calculation passed; categorical supportive/neutral/fragile score calculated from Phase 12A grammar using existing project evidence only; no signal/backtest/model/new data/promotion |
| Phase 12D diagnostic score distribution/content audit | Completed — score distribution/content audit passed; aggregate diagnostic score and component-state content verified; forbidden score/signal/backtest/empirical-weight columns absent; no signal/backtest/model/new data/promotion |
| Phase 12E diagnostic score interpretation / closeout audit | Completed — fragile diagnostic score interpreted as research-only context; closeout claims locked; no score-to-signal conversion, allocation rule, backtest, empirical weighting, model, new data, promotion, or final-candidate change |
| Phase 12F final diagnostic score checkpoint audit | Completed — final Phase 12 checkpoint passed; Phase 12A–12E reports and gates verified, diagnostic score branch closed, and any future score-to-signal work restricted to a separate pre-registration spec |
| Phase 13A baseline SPY research arc freeze / transition spec | Completed — SPY regime-switch arc frozen as baseline research framework; fragile diagnostic score not converted into signal; hierarchy unchanged; new multi-factor model architecture path opened |
| Phase 13B multi-factor long-term decision model architecture roadmap spec | Completed — roadmap passed; technical, macro, fundamental, sentiment, dissertation-integration, walk-forward design, visual reporting, and paper-trading readiness defined; no feature ingestion, signal, backtest, model, paper trading, promotion, or final-candidate change |
| Phase 13C multi-factor feature-source inventory / leakage-feasibility spec | Completed — feature-source inventory passed; technical and macro contract paths feasible, fundamental and sentiment present but blocked pending dedicated audits, contract requirements and leakage controls documented; no feature ingestion/signal/backtest/model/paper trading/promotion |
| Phase 13D feature contract / data availability readiness audit | Completed — readiness audit passed; Phase 13C reports/gates verified, config flags clean, contract coverage passed, blocked families respected, and Phase 13E limited to schema design only |
---

# What Should Happen Next

Do **not** add another strategy variant immediately.

Phase 8 is closed. Phase 9A has completed as a diagnostic-only technical indicator expansion. It identified interpretable technical-regime clusters, but it did not create, tune, validate, or promote a new trading rule.

The immediate checkpoint work is:

1. Ensure `phase9a_technical_indicator_expansion_diagnostic.enabled` is `false` in the permanent config.
2. Ensure all Phase 8A–8G diagnostic flags are disabled in the permanent config.
3. Keep `relative_momentum_allocator.enabled` set to `true`.
4. Ensure all tests pass.
5. Ensure `ruff` passes.
6. Confirm `.env` is ignored and no API key or secret is staged.
7. Commit the Phase 9A source, tests, config, and README update directly to `main`.
8. Push directly to `main`.
9. Tag the Phase 9A checkpoint.

The current checkpoint should be documented as:

> Final Phase 6B `loose_relief` candidate remains the best execution-realistic risk-adjusted candidate built so far, with mixed rolling-window liveability, meaningful spread/impact sensitivity, mixed walk-forward evidence, material behavioural-regret risk, an explicit research-degrees-of-freedom caveat, a documented research-only/non-production boundary, and diagnostic-only Phase 9A technical-regime evidence.

The next research phase after Phase 9A checkpointing should be:

> **Phase 9B: Technical Regime Cluster Stability Audit**

Phase 9B should test whether the Phase 9A underperformance/helpfulness clusters are stable across subperiods and episodes, or whether they are full-period artefacts.

Do **not** turn Phase 9A clusters into rules yet. That would be overfitting. Any future technical indicator rule must be pre-defined and validated separately.

No macro, sentiment, fundamentals, ML, or new tax work should be opened before Phase 9B cluster stability is completed.

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
| Simplified tax-drag status | Phase 8A survived at 20% proxy; 30% proxy erased SPY 12M CAGR edge |
| Bid-ask / market-impact status | Phase 8B failed configured stress gate; execution friction remains a major caveat |
| Walk-forward validation status | Phase 8C failed / mixed evidence; forward-window superiority was not clean |
| Behavioural regret status | Phase 8D failed / material behavioural regret versus Buy & Hold |
| Research degrees-of-freedom status | Phase 8E completed; claims narrowed explicitly |
| Research-only boundary status | Phase 8F boundary-control audit passed; research-only boundary documented |
| Final Phase 8 checkpoint status | Phase 8G completed; README/config/report consistency passed |
| Technical indicator expansion status | Phase 9A completed diagnostic-only; no strategy promotion |

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

> **The best execution-realistic risk-adjusted candidate built so far, with mixed rolling-window liveability, meaningful spread/impact sensitivity, mixed walk-forward evidence, material behavioural-regret risk, an explicit research-degrees-of-freedom caveat, a documented research-only/non-production boundary, and diagnostic-only Phase 9A technical-regime evidence.**

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
- Phase 8A simplified tax-drag diagnostic survived at the 20% proxy but exposed tax sensitivity at the 30% proxy,
- Phase 8B further narrows the claim: the final candidate remains the best execution-realistic risk-adjusted candidate built so far, but its edge is sensitive to spread/impact assumptions and should not be described as friction-robust.
- all canonical results are pinned to 2026-05-01.
Phase 8C further narrows the claim: the final candidate remains the best execution-realistic risk-adjusted candidate built so far, but sequential forward-window evidence is mixed rather than clean.
Phase 8D further narrows the liveability claim: the final candidate remains the best execution-realistic risk-adjusted candidate built so far, but behavioural regret versus SPY Buy & Hold is material.
Phase 8E further narrows the claim: the final candidate remains the best execution-realistic risk-adjusted candidate built so far, but the project has accumulated enough research degrees of freedom that claims must remain explicitly caveated.
Phase 8F closes the research-only/non-production boundary: the final candidate remains a research result only. It is not production-ready, not live-tradable, and not a financial recommendation.
- Phase 8G confirmed README/config/report consistency and closed Phase 8 as a research checkpoint.
- Phase 9A completed as a diagnostic-only technical indicator expansion and produced interpretable regime evidence without changing the hierarchy.
- Phase 9A cluster evidence may inform future hypotheses, but it is not a validated trading rule.
That distinction is the whole point of the project.