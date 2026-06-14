# Market Strats Lab

A reproducible systematic-trading research lab for testing long-term market strategies, dynamic asset allocation, and individual-equity ranking systems under strict lookahead, robustness, and operational controls.

The project investigates whether transparent systematic methods can improve the **return / drawdown / liveability** trade-off versus passive benchmarks across two connected research tracks:

1. **ETF and multi-asset strategy research**
2. **Individual-equity ranking and shadow-portfolio research**

It is not designed to discover a magic trading rule. It is designed to answer a more difficult question:

> Can a systematic process improve the path of long-term returns without destroying compounding, overfitting historical data, or creating a system that an investor would abandon in practice?

---

## Important Disclaimer

This project is for **research and education only**.

It is **not** financial advice, investment advice, or a recommendation to buy or sell any security. Historical backtests and model diagnostics can be misleading, particularly when many strategies, assets, parameters, features, and rules have been tested.

Real-world results can differ materially because of:

* data quality and survivorship bias;
* lookahead and timestamp errors;
* transaction costs;
* bid-ask spreads;
* market impact;
* taxes;
* liquidity;
* order rejection and partial execution;
* corporate actions;
* changing market regimes;
* behavioural difficulty;
* model drift;
* implementation errors;
* future market conditions.

**Current status:** research-grade framework with active manual paper and shadow-trading infrastructure.

The ETF/multi-asset branch has recorded a valid manual paper session. The individual-equity branch has generated its first genuine post-endpoint ranking, target portfolio, and proposed shadow orders, but the first simulated entries remain pending valid next-open execution prices.

**Not production-ready. Not connected to a broker. Not live-tradable. Not approved for real-money deployment.**

---

## Executive Summary

Market Strats Lab began as a simple ETF trend-following project and evolved into a broader systematic research and operational-testing framework.

### ETF and Multi-Asset Branch

The project has built and stress-tested:

* buy-and-hold benchmarks;
* 10-month and 12-month trend-following systems;
* tactical relative-momentum allocators;
* SPY regime-switch overlays;
* execution-cost and market-impact diagnostics;
* tax-drag diagnostics;
* walk-forward validation;
* bootstrap robustness;
* behavioural-regret analysis;
* technical and macro extension tests;
* diagnostic regime scoring;
* visual backtest reporting;
* operational switch-log reconstruction;
* manual paper-session generation, ingestion, archival, holdings, cash, and performance tracking.

The main ETF research conclusion remains:

> No tested strategy dominates SPY Buy & Hold on raw wealth while also improving every risk and liveability metric.

However, the project identified a strong defensive and risk-adjusted candidate:

> **SPY 3D Confirmed Overlay + deep_drawdown_guard + loose_relief**

This candidate does **not** beat SPY Buy & Hold on raw terminal wealth. SPY Buy & Hold remains the primary raw-wealth benchmark.

Its value is different:

> It gives up some upside participation in exchange for materially lower drawdown and stronger risk-adjusted performance.

### Individual-Equity Branch

The project has also built the foundations of an autonomous individual-stock research system:

* point-in-time universe, identity, and membership contracts;
* SEC filing-time, amendment, and restatement controls;
* news, filing-text, transcript, analyst, macro, and sentiment timestamp contracts;
* a leak-safe combined feature-panel schema;
* a controlled 16-stock research-only pilot universe;
* technical, liquidity, and market-stress feature calculation;
* forward-return target generation;
* a deterministic Ridge cross-sectional stock ranker;
* purged and embargoed walk-forward evaluation;
* robustness, bootstrap, permutation, ablation, sector, security, and regime diagnostics;
* a frozen model specification and deterministic model hash;
* cost-aware portfolio construction;
* a separate prospective individual-equity shadow namespace;
* post-endpoint data acquisition and validation;
* prospective rankings, target weights, and proposed simulated orders.

The initial stock-ranking evidence is encouraging, but it remains a small, noncanonical, survivorship-biased pilot and is not evidence of investable performance.

---

## Current Canonical Checkpoint

The historical research endpoint is pinned at:

```text
2026-05-01
```

This endpoint is deliberately fixed for:

* historical validation;
* metric reconciliation;
* switch-log reconstruction;
* model training and robustness analysis;
* README checkpoint numbers;
* reproducibility.

Any data after this endpoint must be stored and evaluated separately as:

```text
post_endpoint_prospective_shadow
```

The pinned historical endpoint is not a flaw. It prevents refreshed market data from silently changing previously validated results.

It must not be treated as a current executable signal.

Canonical ETF comparison period:

```text
2006-04-28 to 2026-05-01
```

Controlled individual-equity pilot period:

```text
2023-01-03 to 2026-05-01
```

Post-endpoint individual-equity shadow period:

```text
After 2026-05-01
```

---

## Current Research Tracks

| Track                                     | Current State                                         | Main Limitation                                          |
| ----------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| ETF and multi-asset historical research   | Mature historical framework with validated candidates | No candidate dominates SPY Buy & Hold on every dimension |
| ETF and multi-asset manual paper tracking | First valid entered paper session recorded            | Still manual and research-only                           |
| Individual-equity feature engineering     | Pilot panel built and validated                       | Only 16 noncanonical surviving stocks                    |
| Individual-equity ranking model           | Interpretable Ridge ranker completed                  | Technical, liquidity, and stress features only           |
| Individual-equity robustness              | Encouraging IC evidence with material caveats         | Rank spread uncertainty remains weaker                   |
| Individual-equity portfolio simulation    | Cost-aware historical diagnostics completed           | Noncanonical pilot; not investable performance           |
| Individual-equity prospective shadow      | First ranking and target portfolio generated          | First next-open simulated execution still pending        |
| Broker integration                        | Blocked                                               | No broker or sandbox integration approved                |
| Live trading                              | Blocked                                               | No real-money readiness claim                            |

---

## Current ETF Strategy Hierarchy

| Rank | Role                                                | System                                                                 |
| ---: | --------------------------------------------------- | ---------------------------------------------------------------------- |
|    1 | Raw wealth benchmark                                | SPY Buy & Hold                                                         |
|    2 | Simple defensive benchmark                          | SPY 12M Absolute Momentum                                              |
|    3 | Original canonical risk-adjusted system             | SPY Trend Regime Switch Overlay 3D Confirmed under flat 5 bps slippage |
|    4 | Validated execution-realistic baseline              | SPY 3D Confirmed Overlay + deep_drawdown_guard                         |
|    5 | Best execution-realistic ETF candidate built so far | SPY 3D Confirmed Overlay + deep_drawdown_guard + loose_relief          |

Important distinction:

> The final ETF candidate is the best execution-realistic **risk-adjusted** candidate built so far. It is not the raw-wealth winner.

---

## ETF Headline Results

### Full-Period Comparison

Common period:

```text
2006-04-28 to 2026-05-01
```

| Strategy                                                          | Role                                        |      End Value |       CAGR |    Calmar | Volatility | Max Drawdown | Verdict                               |
| ----------------------------------------------------------------- | ------------------------------------------- | -------------: | ---------: | --------: | ---------: | -----------: | ------------------------------------- |
| SPY Buy & Hold                                                    | Raw wealth benchmark                        |     $79,306.63 |     10.90% |     0.197 |     19.41% |      -55.19% | Highest raw terminal wealth           |
| SPY 12M Absolute Momentum                                         | Simple defensive benchmark                  |     $63,497.24 |      9.68% |     0.287 |     15.05% |      -33.72% | Strong simple timing benchmark        |
| Top 3 Equal Weight Trend-Confirmed Relative Momentum              | Best standalone balanced allocator          |     $58,401.74 |      9.22% |     0.317 |     16.29% |      -29.06% | Useful standalone allocator           |
| Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum  | Best standalone defensive allocator         |     $52,197.16 |      8.61% |     0.351 |     13.35% |      -24.54% | Strong defensive allocator            |
| **SPY 3D Confirmed Overlay**                                      | **Original flat-slippage canonical system** | **$70,048.61** | **10.22%** | **0.429** | **13.58%** |  **-23.84%** | **Original Phase 3 canonical system** |
| SPY 3D Confirmed Overlay + deep_drawdown_guard                    | Execution-realistic baseline                |     $66,429.13 |      9.93% |     0.412 |     13.60% |      -24.12% | Validated dynamic-stress baseline     |
| **SPY 3D Confirmed Overlay + deep_drawdown_guard + loose_relief** | **Best execution-realistic candidate**      | **$71,779.16** | **10.35%** | **0.429** | **13.50%** |  **-24.12%** | **Final Phase 6C candidate**          |

### Holdout Validation

Holdout period:

```text
2016-01-04 to 2026-05-01
```

| Strategy                                                          | Holdout CAGR | Holdout Calmar | Holdout Max Drawdown | Holdout Volatility |
| ----------------------------------------------------------------- | -----------: | -------------: | -------------------: | -----------------: |
| SPY Buy & Hold                                                    |       15.03% |          0.446 |              -33.72% |             17.87% |
| SPY 12M Absolute Momentum                                         |       11.49% |          0.341 |              -33.72% |             16.12% |
| SPY 3D Confirmed Overlay                                          |       12.06% |          0.506 |              -23.83% |             13.63% |
| SPY 3D Confirmed Overlay + deep_drawdown_guard                    |       11.62% |          0.482 |              -24.12% |             13.60% |
| **SPY 3D Confirmed Overlay + deep_drawdown_guard + loose_relief** |   **12.05%** |      **0.500** |          **-24.12%** |         **13.60%** |

Holdout conclusion:

> The final execution-realistic candidate improved on the Phase 4 baseline in the holdout, increasing CAGR from 11.62% to 12.05% and Calmar from 0.482 to 0.500, while leaving maximum drawdown unchanged at -24.12%.

SPY Buy & Hold still won on raw CAGR, but with materially worse drawdown.

---

## Individual-Equity Pilot Results

### Pilot Scope

The controlled pilot contains:

```text
AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, BRK-B,
XOM, JNJ, UNH, PG, COST, CAT, NEE, TSLA
```

SPY is used as the benchmark.

The pilot is explicitly:

```text
NONCANONICAL
SURVIVORSHIP-BIASED
RESEARCH-ONLY
NOT A HISTORICAL S&P 500 RECONSTRUCTION
NOT VALID FOR GENERALISATION OR INVESTABLE-PERFORMANCE CLAIMS
```

### Feature and Target Panel

| Item                     |                                             Result |
| ------------------------ | -------------------------------------------------: |
| Pilot securities         |                                                 16 |
| Feature-panel rows       |                                              2,784 |
| Forward-target rows      |                                             24,384 |
| Training-eligible rows   |                                              2,784 |
| Calculated feature count |                                                 10 |
| Registered target count  |                                                  9 |
| Primary target           | 20-trading-day excess return versus pilot universe |
| Decision cadence         |                                             Weekly |
| Purge window             |                                    63 trading days |
| Embargo window           |                                    63 trading days |

### Interpretable Ridge Ranker

Phase 23G produced strictly out-of-sample predictions using a chronological, purged, and embargoed walk-forward process.

| Metric                             |  Result |
| ---------------------------------- | ------: |
| Unique stock-date observations     |   2,112 |
| Test dates                         |     132 |
| Securities                         |      16 |
| Mean Spearman IC                   |  0.1225 |
| Median Spearman IC                 |  0.1485 |
| Positive-IC date fraction          |   62.9% |
| Top-k average 20-day excess return | 1.2166% |
| Top-minus-bottom rank spread       | 2.8345% |
| Prediction coverage                |    100% |

The reported 10,560 prediction rows represent:

```text
132 test dates × 16 securities × 5 models or baselines
```

They are not 10,560 independent stock-date observations.

### Robustness Results

Phase 23H found:

| Diagnostic                                     |            Result |
| ---------------------------------------------- | ----------------: |
| Moving-block-bootstrap 95% IC interval         |  0.0069 to 0.2420 |
| Bootstrap probability that mean IC is positive |              0.98 |
| Within-date permutation IC p-value             |            0.0099 |
| Rank-spread 95% interval                       | -0.0031 to 0.0576 |

Interpretation:

> Rank-correlation evidence is encouraging for further research, but the rank-spread interval crosses slightly below zero. The signal is not yet established as an investable trading edge.

### Cost-Aware Historical Portfolio Diagnostic

The preregistered primary portfolio was:

```text
ridge_top5_equal_weight
```

| Cost Assumption | End Value |   CAGR | Max Drawdown | Total Costs |
| --------------- | --------: | -----: | -----------: | ----------: |
| Zero cost       |  $273,954 | 25.65% |      -29.19% |          $0 |
| 10 bps          |  $265,089 | 24.72% |      -29.47% |      $5,797 |
| 25 bps          |  $252,104 | 23.31% |      -29.88% |     $14,086 |
| 50 bps stress   |  $231,963 | 21.00% |      -30.58% |     $26,882 |

These results survived the configured cost assumptions within the pilot, but they must be labelled:

```text
NONCANONICAL PILOT DIAGNOSTIC — NOT INVESTABLE PERFORMANCE
```

The result may be materially overstated by the hand-selected surviving-stock universe, limited history, and absence of canonical fundamentals and news features.

---

## Current Final-Candidate Descriptions

### ETF Candidate

The final ETF candidate should be described narrowly:

> **Best execution-realistic ETF risk-adjusted candidate built so far, with mixed rolling-window liveability, meaningful spread and market-impact sensitivity, mixed walk-forward evidence, material behavioural-regret risk, and no real-money readiness claim.**

### Individual-Equity Model

The individual-equity model should be described narrowly:

> **A frozen, interpretable, research-only cross-sectional Ridge ranker that produced encouraging out-of-sample rank-correlation evidence in a controlled 16-stock pilot, but has not established canonical generalisation, investable performance, or live-trading readiness.**

Do **not** describe either branch as:

* a guaranteed edge;
* a production system;
* a live-trading system;
* real-money-ready;
* broker-integrated;
* generally validated across the historical S&P 500 or Nasdaq-100.

---

## Current Paper and Shadow-Trading Status

### ETF and Multi-Asset Paper Track

The ETF/multi-asset branch has progressed beyond preparation:

| Area                                      | Status                      |
| ----------------------------------------- | --------------------------- |
| Historical switch logic                   | Reconstructed and validated |
| Fresh-signal and candidate infrastructure | Implemented                 |
| Manual session validation                 | Implemented                 |
| Session rollover and archival             | Implemented                 |
| Holdings and cash accounting              | Implemented                 |
| Performance dashboard                     | Implemented                 |
| Valid entered paper session               | Completed                   |
| Broker/API integration                    | Blocked                     |
| Live trading                              | Blocked                     |
| Real-money deployment                     | Blocked                     |

### Individual-Equity Shadow Track

As of the latest operational checkpoint:

| Area                                     | Status    |
| ---------------------------------------- | --------- |
| Frozen model specification               | Completed |
| Deterministic model hash                 | Completed |
| Cost-aware portfolio construction        | Completed |
| Separate post-endpoint data directory    | Completed |
| Historical overlap validation            | Passed    |
| Post-endpoint data for SPY and 16 stocks | Validated |
| Prospective features                     | Generated |
| Prospective ranking                      | Generated |
| Target portfolio                         | Generated |
| Proposed simulated orders                | Generated |
| Valid next-open execution prices         | Pending   |
| First entered shadow session             | Pending   |
| Automated broker paper trading           | Blocked   |
| Live trading                             | Blocked   |
| Real-money deployment                    | Blocked   |

The latest genuine post-endpoint signal date is:

```text
2026-06-12
```

The latest frozen-model ranking selected:

```text
TSLA
META
CAT
AMZN
NVDA
```

The research target portfolio assigned 20% to each selected stock before share rounding and execution-price validation.

These are model outputs from a noncanonical research pilot. They are **not investment recommendations**.

The first simulated shadow entries were correctly blocked because valid next-open execution prices were not yet available:

```text
blocking_reason: execution_open_price_pending
```

The fill helper correctly refused to fabricate or backfill execution prices.

---

## Current Development Priority

The immediate operational task is:

> Obtain the next eligible market-session opening prices, regenerate the Phase 23J extension, validate the Phase 23I shadow order plan, and explicitly enter the first simulated individual-equity shadow session.

Required sequence:

```text
1. Refresh Phase 23J post-endpoint market data.
2. Confirm the next-open execution date and prices.
3. Regenerate the Phase 23I shadow session.
4. Confirm all proposed orders are unblocked.
5. Explicitly create simulated fills.
6. Validate and ingest the filled session.
7. Archive the completed session.
8. Begin weekly shadow valuation and rebalance tracking.
```

After the first entered session, the next engineering milestone is:

> **Phase 23K — Prospective Shadow Monitoring, Drift, and Operational Controls**

That phase should monitor:

* ranking stability;
* prediction outcomes as forward labels mature;
* portfolio returns and drawdowns;
* transaction costs and turnover;
* feature-distribution drift;
* model-score drift;
* security and sector concentration;
* stale or missing data;
* model-hash consistency;
* proposed versus entered orders;
* skipped and blocked sessions;
* operational failures.

---

## Key Caveats

### 1. SPY Buy & Hold remains the ETF raw-wealth winner

The final ETF candidate improves drawdown and Calmar but does not beat SPY Buy & Hold on raw terminal wealth.

### 2. The ETF candidate is sensitive to real-world friction

Bid-ask spread and market-impact stress can erase the candidate’s CAGR advantage versus SPY 12M Momentum, even when drawdown and Calmar remain better.

### 3. Rolling-window ETF liveability is mixed

The system performs better over several three- and five-year windows, but short-window relative performance and liveability remain important caveats.

### 4. Behavioural regret is material

Relative underperformance against Buy & Hold can remain psychologically difficult for extended periods.

### 5. The ETF strategy is not tax-proof

The candidate survived a simplified 20% tax proxy, but its CAGR edge versus SPY 12M disappeared under a harsher 30% proxy.

### 6. Technical and macro ETF extensions failed as validated rule upgrades

The diagnostics were informative, but the preregistered rule extensions did not produce a validated successor to the final ETF candidate.

### 7. The diagnostic ETF regime score is fragile

The categorical regime score remains diagnostic only and does not create an independent trading signal.

### 8. The earlier technical-plus-macro ML branch failed commercially

That branch failed validation-to-holdout and did not produce a promoted signal, paper-trading candidate, or accepted model.

### 9. The individual-equity pilot is noncanonical

The 16-stock universe is hand-selected, survivorship-biased, and materially smaller than the S&P 500 or Nasdaq-100.

It cannot establish broad historical generalisation.

### 10. The individual-equity feature set is incomplete

The current model uses technical, liquidity, and market-stress features.

Point-in-time fundamental, news, transcript, analyst, and sentiment data contracts exist, but the historical datasets have not yet been acquired and integrated.

### 11. The individual-equity labels overlap

Weekly decisions are evaluated against 20-trading-day targets, so adjacent outcomes overlap.

Phase 23H uses block bootstrap and within-date permutation tests rather than treating all rows as independent.

### 12. The historical stock-portfolio results are not investable results

The high historical CAGR produced by the 16-stock pilot may reflect survivorship bias, concentration, selected-period effects, and limited universe breadth.

### 13. Prospective evidence is still minimal

The system has generated its first genuine prospective proposal but has not yet recorded its first entered individual-equity shadow session.

A few weeks of results would be an operational test, not evidence of a durable edge.

### 14. No broker or live-money path is enabled

All broker integration, automated execution, live trading, real money, and promotion flags remain disabled.

---

## Research Question

The project asks:

> Can transparent systematic rules and models improve long-term outcomes versus passive benchmarks without destroying compounding, robustness, or practical liveability?

Strategies and models are evaluated on:

| Metric or Control                      | Why It Matters                                            |
| -------------------------------------- | --------------------------------------------------------- |
| Terminal wealth and CAGR               | Raw compounding power                                     |
| Maximum drawdown                       | Worst historical investor pain                            |
| Calmar ratio                           | Return per unit of maximum drawdown                       |
| Volatility                             | Path smoothness                                           |
| Sharpe and Sortino                     | Risk-adjusted efficiency                                  |
| Worst three- and five-year CAGR        | Bad-window survivability                                  |
| Exposure and cash weight               | Capital utilisation                                       |
| Trade count and turnover               | Friction and tax efficiency                               |
| Time underwater                        | Duration of loss periods                                  |
| Regime performance                     | Behaviour under different market environments             |
| Holdout validation                     | Performance outside the reference period                  |
| Endpoint integrity                     | Protection against silent historical drift                |
| Signal-execution separation            | Prevention of same-close or lookahead execution           |
| Point-in-time data availability        | Prevention of future-information leakage                  |
| Bootstrap robustness                   | Sensitivity to resampling and overlapping labels          |
| Walk-forward evidence                  | Sequential out-of-sample behaviour                        |
| Information coefficient                | Cross-sectional ranking quality                           |
| Rank spread                            | Separation between high- and low-ranked stocks            |
| Feature and coefficient stability      | Model interpretability and drift                          |
| Transaction-cost survival              | Whether realistic friction destroys the result            |
| Behavioural regret                     | Tolerability relative to passive benchmarks               |
| Operational replay readiness           | Ability to reproduce decisions without hidden state       |
| Paper and shadow reconciliation        | Whether proposed trades, fills, cash, and positions agree |
| Research-degrees-of-freedom discipline | Whether claims remain narrow after many experiments       |

The goal is not only to ask:

> Did it make more money?

It is also to ask:

> Was the result reproducible, point-in-time valid, cost-aware, operationally executable, and something an investor could realistically follow?

---

## Tested Market Universe

### ETF and Multi-Asset Universe

| Ticker    | Market or Asset Class           | Role in Research                                |
| --------- | ------------------------------- | ----------------------------------------------- |
| `SPY`     | US large-cap equities / S&P 500 | Main benchmark and core compounding engine      |
| `QQQ`     | Nasdaq-100 / US growth equities | High-beta equity and offensive allocation test  |
| `IWM`     | US small caps                   | Small-cap trend behaviour                       |
| `EFA`     | Developed ex-US equities        | International developed-equity exposure         |
| `EEM`     | Emerging markets                | Higher-volatility international-equity exposure |
| `GLD`     | Gold                            | Crisis and real-rate-sensitive asset            |
| `SLV`     | Silver                          | High-volatility precious-metal exposure         |
| `DBC`     | Broad commodities               | Commodity-cycle exposure                        |
| `USO`     | Oil proxy                       | Controlled oil-expansion diagnostic             |
| `TLT`     | Long-duration US Treasuries     | Duration-heavy defensive asset                  |
| `AGG`     | Aggregate US bonds              | Broad defensive bond sleeve                     |
| `VNQ`     | US REITs                        | Real-estate and credit-sensitive equity         |
| `BTC-USD` | Bitcoin                         | Quarantined separate research branch            |
| `ETH-USD` | Ethereum                        | Quarantined crypto diagnostic                   |

Bitcoin and Ethereum remain separate or quarantined research branches because their histories are shorter, structurally different, and highly sensitive to selection bias.

### Controlled Individual-Equity Pilot

| Ticker  | Sector                 |
| ------- | ---------------------- |
| `AAPL`  | Information Technology |
| `MSFT`  | Information Technology |
| `NVDA`  | Information Technology |
| `AMZN`  | Consumer Discretionary |
| `GOOGL` | Communication Services |
| `META`  | Communication Services |
| `JPM`   | Financials             |
| `BRK-B` | Financials             |
| `XOM`   | Energy                 |
| `JNJ`   | Health Care            |
| `UNH`   | Health Care            |
| `PG`    | Consumer Staples       |
| `COST`  | Consumer Staples       |
| `CAT`   | Industrials            |
| `NEE`   | Utilities              |
| `TSLA`  | Consumer Discretionary |

This pilot is an engineering and research sample, not a canonical historical index universe.

---

## Bottom Line

The project has not found a magic strategy.

It has produced two serious but still limited research tracks.

### ETF and Multi-Asset Track

> A defensive, execution-realistic SPY regime-switch candidate that materially improves drawdown and risk-adjusted performance versus simple defensive benchmarks, while still trailing SPY Buy & Hold on raw wealth.

That candidate has progressed into a functioning manual paper-trading workflow.

### Individual-Equity Track

> A frozen, interpretable stock-ranking model with encouraging out-of-sample rank-correlation evidence, cost-aware historical portfolio diagnostics, and a functioning prospective shadow-order workflow.

However, the stock model remains based on a small noncanonical pilot. It has not established investable performance, broad index-level generalisation, or real-money readiness.

The immediate milestone is:

> Enter, validate, and archive the first genuine individual-equity simulated shadow session using actual next-open execution prices.

The next research milestone is:

> Build prospective monitoring, drift detection, and operational controls across at least 12 weekly shadow sessions, with 26 weeks preferred before considering broker-sandbox automation.

The project must continue to:

* preserve the pinned historical endpoint;
* keep post-endpoint data separate;
* prevent same-close or fabricated execution;
* preserve frozen model specifications;
* retain complete session and order lineage;
* distinguish proposed orders from entered positions;
* avoid investable-performance claims from the noncanonical pilot;
* keep broker integration, live trading, and real money disabled until independently justified.

---

# Phase 2: Tactical Portfolio Management

## Phase 2 Goal

Phase 2 tested whether the framework could dynamically allocate across broad investable assets and improve the **return / drawdown / liveability** trade-off relative to both:

* SPY Buy & Hold;
* SPY 12M Absolute Momentum.

The longer-term ambition was to evolve towards a richer decision framework incorporating technical, fundamental, sentiment, macroeconomic, geopolitical, and cross-asset information.

However, the project deliberately did **not** begin with macro data, sentiment, machine learning, cryptocurrency, or individual-stock selection.

Instead, it followed a disciplined sequence:

```text
1. Build a price- and risk-based allocator.
2. Diagnose where it works and fails.
3. Add portfolio constraints.
4. Validate the resulting system.
5. Analyse behaviour across market regimes.
6. Only then consider more complex information sources.
```

---

## Phase 2 Universe

Phase 2 expanded the tactical allocation universe to:

```text
SPY, QQQ, IWM, EFA, EEM, AGG, TLT, GLD, SLV, VNQ, DBC
```

This includes:

* US equities;
* international equities;
* bonds;
* REITs;
* gold;
* silver;
* broad commodities.

BTC remained quarantined and was **not** part of the main tactical allocator.

---

## Relative Momentum Allocator

### Baseline Rule

```text
At month-end:
  rank assets by trailing 12-month return
  keep assets with positive 12-month momentum
  hold the top 3
  unused capital goes to cash
```

The framework uses daily adjusted close data, but the base allocator makes monthly decisions.

### Initial Bug Caught

The first relative-momentum result showed unrealistically low exposure. This revealed a bug:

```text
Target weights were not persisting between monthly rebalance dates.
```

Fix:

```text
Initialise target weights as NaN.
Forward-fill weights between rebalance dates.
Set weights to zero only when no asset qualifies.
```

This matters because the project did not simply accept attractive outputs. It diagnosed and corrected a structural implementation error before continuing.

---

## Phase 2 Allocator Results

| Strategy                                                         |  CAGR | Calmar | Volatility | Max Drawdown | Verdict                             |
| ---------------------------------------------------------------- | ----: | -----: | ---------: | -----------: | ----------------------------------- |
| Top 3 Equal Weight Relative Momentum                             | 8.93% |  0.250 |     17.12% |      -35.74% | Failed baseline                     |
| Top 3 Inverse Volatility Relative Momentum                       | 8.52% |  0.264 |     15.60% |      -32.31% | Better risk, weaker return          |
| Top 3 Equal Weight Trend-Confirmed Relative Momentum             | 9.22% |  0.317 |     16.29% |      -29.06% | Best standalone balanced allocator  |
| Top 3 Inverse Volatility Trend-Confirmed Relative Momentum       | 8.74% |  0.295 |     14.85% |      -29.63% | Defensive variant                   |
| Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum | 8.61% |  0.351 |     13.35% |      -24.54% | Best standalone defensive allocator |

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

Phase 2 allocator conclusion:

> Trend confirmation and portfolio constraints improved the allocator, but relative momentum alone did not beat SPY Buy & Hold on raw wealth.

---

## Phase 2 Holdout Validation

| Period    | Dates                    |
| --------- | ------------------------ |
| Reference | 2006-04-28 to 2015-12-31 |
| Holdout   | 2016-01-04 to 2026-05-01 |

### Reference Period

| Strategy                           |  CAGR | Calmar | Volatility |
| ---------------------------------- | ----: | -----: | ---------: |
| Top 3 Equal Weight Trend-Confirmed | 9.22% |  0.346 |     16.32% |
| Top 3 Constrained Trend-Confirmed  | 8.67% |  0.540 |     12.59% |
| SPY Buy & Hold                     | 6.84% |  0.124 |     20.94% |
| SPY 12M Momentum                   | 7.95% |  0.427 |     13.82% |

Reference-period conclusion:

> Phase 2 added real value in the mixed/choppy reference period.

### Holdout Period

| Strategy                           |   CAGR | Calmar | Volatility |
| ---------------------------------- | -----: | -----: | ---------: |
| Top 3 Equal Weight Trend-Confirmed |  9.40% |  0.376 |     16.26% |
| Top 3 Constrained Trend-Confirmed  |  8.70% |  0.386 |     14.03% |
| SPY Buy & Hold                     | 15.03% |  0.446 |     17.87% |
| SPY 12M Momentum                   | 11.49% |  0.341 |     16.12% |

Holdout conclusion:

> Phase 2 failed as a wealth-growth replacement in the bull-heavy 2016–2026 holdout, but retained defensive and regime-diversifying value.

---

## Regime Diagnostics

The key regime question was:

> When does the tactical allocator work, and when does it fail?

### SPY Above 200D Trend

| Strategy                               | Conditional Annualised Return |
| -------------------------------------- | ----------------------------: |
| SPY Buy & Hold                         |                        26.32% |
| SPY 12M Momentum                       |                        22.21% |
| Equal Weight Trend-Confirmed Allocator |                        18.56% |
| Constrained Trend-Confirmed Allocator  |                        16.22% |

Conclusion:

> When SPY is healthy, SPY dominates. The tactical allocators are too defensive.

### SPY Below 200D Trend

| Strategy                               | Conditional Annualised Return |
| -------------------------------------- | ----------------------------: |
| Constrained Trend-Confirmed Allocator  |                       -14.58% |
| Equal Weight Trend-Confirmed Allocator |                       -18.39% |
| SPY 12M Momentum                       |                       -26.59% |
| SPY Buy & Hold                         |                       -31.34% |

Conclusion:

> When SPY trend is broken, the allocators lose much less than SPY.

### Deep SPY Bear Drawdowns Below -20%

| Strategy                               | Conditional Annualised Return |
| -------------------------------------- | ----------------------------: |
| Equal Weight Trend-Confirmed Allocator |                         9.16% |
| Constrained Trend-Confirmed Allocator  |                         7.27% |
| SPY 12M Momentum                       |                        -8.84% |
| SPY Buy & Hold                         |                       -20.90% |

Conclusion:

> The relative-momentum allocators are most valuable when SPY is in serious trouble.

### Normal Corrections: -10% to -20%

| Strategy               | Conditional Annualised Return |
| ---------------------- | ----------------------------: |
| SPY Buy & Hold         |                        -6.81% |
| SPY 12M Momentum       |                       -11.26% |
| Constrained Allocator  |                       -11.75% |
| Equal Weight Allocator |                       -15.80% |

Conclusion:

> The allocators struggled in transition regimes. Their value was clearer in severe bear-market regimes than in ordinary corrections.

---

# Phase 3: Regime-Switch Overlay Branch

## Motivation

The Phase 2 regime diagnostics showed a clear pattern:

```text
When SPY is healthy:
  SPY dominates.

When SPY is broken:
  the constrained allocator protects better.
```

This led to the regime-switch overlay branch.

---

## Raw SPY 200D Regime-Switch Overlay

Rule:

```text
If SPY is above its 200D SMA:
  hold SPY Buy & Hold

If SPY is below its 200D SMA:
  hold the constrained trend-confirmed relative-momentum allocator
```

### Raw Overlay Result

| Metric       |   Value |
| ------------ | ------: |
| CAGR         |   8.48% |
| Calmar       |   0.329 |
| Volatility   |  13.22% |
| Max Drawdown | -25.77% |
| End Value    | $50,979 |

Conclusion:

> The raw binary overlay failed as a new leader. It improved drawdown versus SPY 12M, but lost too much CAGR and did not beat the constrained allocator on defensive quality.

---

## Raw Overlay Whipsaw Audit

| Metric                                   |  Value |
| ---------------------------------------- | -----: |
| Total Switches                           |    114 |
| Whipsaw Count                            |     86 |
| Whipsaw Rate                             | 75.44% |
| Median Days Until Next Switch            |      5 |
| Average SPY Distance From 200D at Switch | -0.17% |

Conclusion:

> The raw overlay was not detecting clean regimes. It was thrashing around the 200D boundary.

This justified exactly one buffered confirmation test.

---

## 3D Confirmed Regime-Switch Overlay

Rule:

```text
If SPY closes below its 200D SMA for 3 consecutive trading days:
  switch to the constrained trend-confirmed allocator

If SPY closes above its 200D SMA for 3 consecutive trading days:
  switch back to SPY
```

No other confirmation windows, bands, blends, macro filters, sentiment filters, BTC, or individual-stock signals were tested at this stage.

### Full-Period Result

| Metric       |      Value |
| ------------ | ---------: |
| End Value    | $70,048.61 |
| CAGR         |     10.22% |
| Calmar       |      0.429 |
| Volatility   |     13.58% |
| Max Drawdown |    -23.83% |
| Sharpe       |      0.785 |
| Sortino      |      0.975 |

### Comparison Versus SPY 12M

| Metric       | 3D Overlay |    SPY 12M |
| ------------ | ---------: | ---------: |
| CAGR         |     10.22% |      9.68% |
| Calmar       |      0.429 |      0.287 |
| Volatility   |     13.58% |     15.05% |
| Max Drawdown |    -23.83% |    -33.72% |
| End Value    | $70,048.61 | $63,497.24 |

Conclusion:

> The 3D overlay beat SPY 12M full-period on CAGR, Calmar, volatility, max drawdown, Sharpe, Sortino, terminal value, and rolling-window survivability.

It still trailed SPY Buy & Hold on raw terminal wealth.

---

## 3D Overlay Mode Summary

| Mode                |  Days | % Days | Total Return | Average Position | Average Cash |
| ------------------- | ----: | -----: | -----------: | ---------------: | -----------: |
| Offensive SPY       | 3,996 | 79.38% |      452.56% |          100.00% |        0.00% |
| Defensive Allocator | 1,038 | 20.62% |       26.77% |           58.10% |       41.90% |

Interpretation:

> The overlay spent most of its time in SPY and switched to the defensive allocator roughly one-fifth of the time.

---

## 3D Overlay Whipsaw Audit

| Metric                        | Raw Overlay | 3D Confirmed Overlay |
| ----------------------------- | ----------: | -------------------: |
| Total Switches                |         114 |                   52 |
| Whipsaw Count                 |          86 |                   29 |
| Whipsaw Rate                  |      75.44% |               55.77% |
| Median Days Until Next Switch |           5 |                   20 |

Conclusion:

> The 3D confirmation filter materially reduced whipsaw damage.

---

## 3D Overlay Rolling-Window Results

### 3-Year Windows

| Strategy         | Avg CAGR | Worst CAGR | Avg Max DD | Worst Max DD |
| ---------------- | -------: | ---------: | ---------: | -----------: |
| 3D Overlay       |    9.88% |      2.50% |    -18.03% |      -23.83% |
| SPY 12M Momentum |    9.14% |     -1.95% |    -20.11% |      -33.72% |
| SPY Buy & Hold   |   11.07% |    -16.73% |    -25.83% |      -55.19% |

### 5-Year Windows

| Strategy         | Avg CAGR | Worst CAGR | Avg Max DD | Worst Max DD |
| ---------------- | -------: | ---------: | ---------: | -----------: |
| 3D Overlay       |    9.96% |      3.68% |    -20.14% |      -23.83% |
| SPY 12M Momentum |    9.16% |     -0.19% |    -23.48% |      -33.72% |
| SPY Buy & Hold   |   11.76% |     -1.15% |    -29.92% |      -55.19% |

Conclusion:

> The 3D overlay improved worst rolling 3Y and 5Y survivability versus both SPY 12M and SPY Buy & Hold.

---

## 3D Overlay Holdout Validation

| Period    | Dates                    |
| --------- | ------------------------ |
| Reference | 2006-04-28 to 2015-12-31 |
| Holdout   | 2016-01-04 to 2026-05-01 |

### Reference Period

| Strategy                  |  CAGR | Calmar |  Max DD |
| ------------------------- | ----: | -----: | ------: |
| 3D Regime-Switch Overlay  | 8.46% |  0.444 | -19.06% |
| SPY Buy & Hold            | 6.84% |  0.124 | -55.19% |
| SPY 12M Momentum          | 7.95% |  0.427 | -18.61% |
| Trend-Confirmed Allocator | 9.22% |  0.346 | -26.62% |
| Constrained Allocator     | 8.67% |  0.540 | -16.06% |

Reference conclusion:

> The 3D overlay beat SPY 12M on CAGR and Calmar, but slightly lost on max drawdown: -19.06% versus -18.61%.

So it did **not** fully pass the strict SPY 12M triple gate in reference, although it was a near miss.

### Holdout Period

| Strategy                  |   CAGR | Calmar |  Max DD |
| ------------------------- | -----: | -----: | ------: |
| 3D Regime-Switch Overlay  | 12.06% |  0.506 | -23.83% |
| SPY Buy & Hold            | 15.03% |  0.446 | -33.72% |
| SPY 12M Momentum          | 11.49% |  0.341 | -33.72% |
| Trend-Confirmed Allocator |  9.40% |  0.376 | -25.02% |
| Constrained Allocator     |  8.70% |  0.386 | -22.52% |

Holdout conclusion:

> The 3D overlay beat SPY 12M in holdout on CAGR, Calmar, max drawdown, volatility, Sharpe, and Sortino.

It also beat SPY Buy & Hold on major risk-adjusted metrics, while trailing it on raw CAGR.

---

## Regime-Switch Overlay Validation Conclusion

| Claim                                                                        | Status                      | Interpretation                                                                                             |
| ---------------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Raw SPY 200D binary overlay is sufficient                                    | Failed                      | Excessive boundary whipsaw made the raw rule unsuitable                                                    |
| Raw SPY 200D overlay failed mainly because of whipsaw                        | Survived                    | The audit confirmed excessive switching around the trend boundary                                          |
| 3D confirmation reduced whipsaw damage                                       | Survived                    | Switches and short-lived reversals fell materially                                                         |
| 3D overlay beats SPY 12M full-period                                         | Survived                    | It improved both return and risk metrics                                                                   |
| 3D overlay beats SPY 12M in holdout                                          | Survived                    | It improved CAGR, Calmar, max drawdown, volatility, Sharpe, and Sortino                                    |
| 3D overlay passes the strict SPY 12M triple gate in holdout                  | Survived                    | Higher CAGR, higher Calmar, and better max drawdown                                                        |
| 3D overlay passes the strict SPY 12M triple gate in reference                | Failed / near miss          | Its reference-period max drawdown was slightly worse than SPY 12M                                          |
| 3D overlay beats SPY Buy & Hold on raw wealth                                | Failed                      | SPY Buy & Hold retained the higher raw CAGR                                                                |
| 3D overlay became the best risk-adjusted candidate at the Phase 3 checkpoint | Survived                    | It became the strongest candidate at that stage, before later execution-realistic guard and relief testing |
| Immediate broad parameter expansion is justified                             | Rejected at this checkpoint | The strength of the result increased the risk of overfitting                                               |
| The branch had reached a documented validation checkpoint                    | Survived                    | The system was ready for robustness and execution-realism testing                                          |


---

# Phase 3A: Robustness Validation

## Phase 3A Goal

Phase 3A tested whether the current best system, the **SPY Trend Regime Switch Overlay 3D Confirmed**, was fragile.

The robustness question was:

> Does the 3D overlay still work after changing realistic assumptions around trading costs, cash yield, and signal price basis?

---

## Slippage Sensitivity

| Slippage |   CAGR | Calmar | Max Drawdown | Interpretation               |
| -------: | -----: | -----: | -----------: | ---------------------------- |
|    5 bps | 10.22% |  0.429 |      -23.84% | Baseline                     |
|   10 bps |  9.93% |  0.415 |      -23.91% | Passed                       |
|   25 bps |  9.08% |  0.376 |      -24.12% | Defensive only / weakened    |
|   50 bps |  7.67% |  0.304 |      -25.21% | Failed as wealth-growth case |

Conclusion:

> Execution friction is the system's main vulnerability. The strategy survives low/moderate ETF-like friction, but it is not friction-proof.

---

## Cash-Yield Sensitivity

The baseline strategy earns cash returns when out of risky assets. To test whether the result was secretly powered by cash yield, the strategy was rerun with 0% cash yield.

| Scenario            |   CAGR | Calmar | Max Drawdown | Status   |
| ------------------- | -----: | -----: | -----------: | -------- |
| Baseline cash yield | 10.22% |  0.429 |      -23.84% | Baseline |
| 0% cash yield       |  9.85% |  0.413 |      -23.84% | Passed   |

Conclusion:

> The 3D overlay does not depend heavily on cash yield.

---

## Raw-Close Signal Sensitivity

Because adjusted-close data is backward-adjusted, the project tested whether using raw close for SPY trend signals would break the result.

| Signal Test           | Period      |   CAGR | Calmar | Max Drawdown | Status             |
| --------------------- | ----------- | -----: | -----: | -----------: | ------------------ |
| Adjusted-close signal | Full period | 10.22% |  0.429 |      -23.84% | Baseline           |
| Raw-close signal      | Full period |  9.72% |  0.408 |      -23.84% | Passed with caveat |
| Raw-close signal      | Holdout     | 11.72% |  0.492 |      -23.84% | Passed             |

Conclusion:

> The raw-close signal version still worked, although with weaker full-period CAGR and Calmar. This supports the view that the system is not entirely dependent on adjusted-close signal artefacts.

---

## Phase 3A Conclusion

| Claim                                                                  | Status                      | Interpretation                                                                        |
| ---------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------- |
| The 3D overlay survives low-to-moderate slippage                       | Survived                    | The 10 bps scenario retained a 9.93% CAGR and 0.415 Calmar                            |
| The 3D overlay is friction-proof                                       | Failed                      | The result weakened materially at 25 bps and failed as a wealth-growth case at 50 bps |
| High execution friction is the main identified vulnerability           | Survived                    | Slippage sensitivity produced the largest deterioration                               |
| The 3D overlay depends heavily on cash yield                           | Failed                      | The 0% cash-yield scenario remained viable                                            |
| The 3D overlay survives raw-close signal sensitivity                   | Survived with caveat        | The raw-close version remained viable but produced weaker full-period CAGR and Calmar |
| Immediate macro, sentiment, or machine-learning expansion is justified | Rejected at this checkpoint | Execution robustness and checkpoint discipline remained the priority                  |

---

# Phase 3B: Controlled Asset Expansion

## Phase 3B Goal

Phase 3B tested whether adding new investable assets improved the existing portfolio-management system.

The key rule was:

> New assets are not promoted because they improve a standalone allocator. They must improve the actual 3D overlay system.

---

## USO / Oil Expansion Diagnostic

Oil was tested using `USO` as an oil proxy.

Comparison:

```text
Base universe
vs
Base + Oil
```

These Phase 3B figures come from the controlled asset-expansion diagnostic setup and should not be read as a replacement for the canonical Phase 3 headline results.

### USO Allocator Impact

| Metric       | Base Allocator | Base + Oil Allocator |     Delta |
| ------------ | -------------: | -------------------: | --------: |
| CAGR         |          7.96% |                8.93% | +0.97 pts |
| Calmar       |          0.280 |                0.376 |    +0.096 |
| Max Drawdown |        -28.42% |              -23.73% | +4.69 pts |

### USO Overlay Impact

| Metric                   | Base 3D Overlay | Base + Oil 3D Overlay |     Delta |
| ------------------------ | --------------: | --------------------: | --------: |
| Full-period CAGR         |           9.78% |                10.47% | +0.69 pts |
| Full-period Calmar       |           0.335 |                 0.400 |    +0.065 |
| Full-period Max Drawdown |         -29.18% |               -26.20% | +2.98 pts |
| Holdout CAGR             |          12.62% |                12.66% | +0.04 pts |
| Holdout Calmar           |           0.482 |                 0.483 |    +0.001 |

USO allocation behaviour:

| Metric             |   Value |
| ------------------ | ------: |
| Average USO weight |  2.563% |
| Days held          |     466 |
| % days held        |  9.257% |
| Final weight       | 33.333% |

USO conclusion:

> Oil improved the allocator and full-period overlay, but the holdout overlay improvement was too small to validate it. USO is promising, but not validated.

---

## ETH Quarantine Diagnostic

ETH was tested separately because its history is shorter and structurally different from the ETF universe.

ETH was capped through a crypto group cap:

```text
crypto cap = 10%
```

### ETH Overlay Impact

| Metric       | Base Overlay | Base + ETH Overlay |                 Delta |
| ------------ | -----------: | -----------------: | --------------------: |
| CAGR         |       12.02% |             11.46% |             -0.56 pts |
| Calmar       |        0.459 |              0.437 |                -0.022 |
| Max Drawdown |      -26.20% |            -26.20% |              0.00 pts |
| Volatility   |     Baseline |          -0.21 pts | Lower, but not enough |

ETH allocation behaviour:

| Metric             |   Value |
| ------------------ | ------: |
| Average ETH weight |  3.527% |
| Max ETH weight     | 10.000% |
| Days held          |     751 |
| % days held        | 35.275% |
| Final weight       |  0.000% |
| Dominates flag     |    True |

ETH conclusion:

> ETH improved allocator CAGR but worsened the actual 3D overlay. It was used often enough to matter, but it did not improve the system. ETH is rejected for now.

---

## Oil + ETH Combined Diagnostic

The combined `Base + Oil + ETH Quarantine` system also failed to validate.

| Metric       | Base Overlay | Oil + ETH Overlay |     Delta |
| ------------ | -----------: | ----------------: | --------: |
| CAGR         |       12.02% |            12.00% | -0.02 pts |
| Calmar       |        0.459 |             0.458 |    -0.001 |
| Max Drawdown |      -26.20% |           -26.20% |  0.00 pts |
| Volatility   |     Baseline |         +0.31 pts |     Worse |

Combined conclusion:

> Oil + ETH did not improve the overlay enough to validate inclusion. The combined expansion is not validated.

---

## Phase 3B Conclusion

| Expansion | Status                      | Interpretation                                                       |
| --------- | --------------------------- | -------------------------------------------------------------------- |
| USO / Oil | Promising but not validated | Helped allocator and full-period overlay, failed holdout materiality |
| ETH       | Rejected                    | Improved allocator but worsened overlay CAGR and Calmar              |
| Oil + ETH | Not validated               | Did not improve overlay enough to justify inclusion                  |

---

# Phase 4: Execution Realism and Switch Quality

## Phase 4 Goal

Phase 4 tested whether the **SPY Trend Regime Switch Overlay 3D Confirmed** survived more realistic execution assumptions and whether its regime switches were genuinely adding value.

This phase was not about adding new assets, macro data, sentiment, or machine learning.

It focused on the system's biggest known weakness:

> execution friction during regime switches.

---

## Phase 4A: Dynamic Stress Slippage

Phase 4A tested whether the 3D confirmed overlay survived a stress-aware execution-cost model.

| Market State            | Overlay Slippage |
| ----------------------- | ---------------: |
| Normal regime           |            5 bps |
| SPY below 200D          |           15 bps |
| SPY drawdown below -10% |           25 bps |
| SPY drawdown below -20% |           50 bps |

Costs were applied only on overlay switch days.

### Result

| Scenario                |   CAGR | Calmar | Max Drawdown |
| ----------------------- | -----: | -----: | -----------: |
| Flat 5 bps baseline     | 10.22% |  0.429 |      -23.84% |
| Dynamic stress slippage |  9.49% |  0.393 |      -24.12% |

Phase 4A conclusion:

> Dynamic stress slippage reduced full-period CAGR by 0.73 percentage points and Calmar by 0.036. The defensive profile survived, but the wealth-growth edge weakened.

The dynamic model preserved a better drawdown profile than SPY 12M Momentum, but failed the strict full-period SPY 12M triple gate because CAGR fell below SPY 12M's pinned 9.68%.

---

## Phase 4B: Switch-Effectiveness Audit

Phase 4B tested whether individual regime switches added value versus the counterfactual of staying in the previous mode.

52 switches were audited under the dynamic stress-slippage model.

| Switch Group    | Switch Count | Helped 5D % | Avg 5D Value Added |
| --------------- | -----------: | ----------: | -----------------: |
| All switches    |           52 |     48.077% |         +0.021 pts |
| 5 bps switches  |           23 |     43.478% |         +0.017 pts |
| 15 bps switches |            9 |     77.778% |         +0.980 pts |
| 25 bps switches |           13 |     46.154% |         -0.158 pts |
| 50 bps switches |            7 |     28.571% |         -0.864 pts |

Phase 4B conclusion:

> Switch quality was weak/mixed. The aggregate overlay remained defensively useful, but individual switch timing did not show a reliable event-level edge.

Final Phase 4B verdict:

> The system's aggregate defensive value was stronger than its event-level switch timing quality.

---

## Phase 4C: Switch-Failure Attribution

Phase 4C diagnosed where the bad switches were concentrated.

Switches were grouped by:

* transition direction;
* dynamic slippage bucket;
* SPY drawdown bucket;
* SPY distance from trend.

### Key Findings

| Bucket                    | Switch Count | Helped 5D % | Avg 5D Value Added |
| ------------------------- | -----------: | ----------: | -----------------: |
| Deep drawdown below -20%  |            7 |     28.571% |         -0.864 pts |
| 50 bps slippage           |            7 |     28.571% |         -0.864 pts |
| Mild drawdown -5% to -10% |           19 |     63.158% |         +0.719 pts |
| Near highs 0% to -5%      |           13 |     38.462% |         -0.341 pts |

Phase 4C conclusion:

> Switch failures were concentrated in high-friction / deep-drawdown switches.

This suggested that the system often switched too late in deep drawdowns, when execution costs were highest and mean-reversion risk was elevated.

Final Phase 4C verdict:

> The switch rule was more useful during mild deterioration than during late deep-drawdown conditions.

---

## Phase 4D: Guarded Switch Diagnostic

Phase 4D tested targeted guarded-switch rules derived from Phase 4C.

The main candidate was:

> **deep_drawdown_guard** — do not initiate new defensive switches when SPY is already below -20% drawdown.

### Result

| System                    |  CAGR | Calmar | Max Drawdown | Switch Count |
| ------------------------- | ----: | -----: | -----------: | -----------: |
| Dynamic no-guard baseline | 9.49% |  0.393 |      -24.12% |           52 |
| deep_drawdown_guard       | 9.93% |  0.412 |      -24.12% |           46 |
| near_high_whipsaw_guard   | 9.43% |  0.391 |      -24.12% |           52 |
| combined guard            | 9.87% |  0.409 |      -24.12% |           46 |

Phase 4D conclusion:

> The deep_drawdown_guard was the best guarded-switch variant. It improved CAGR, improved Calmar, reduced switch count, and did not worsen max drawdown.

It was not yet ready for promotion until the removed switches were audited.

---

## Phase 4E: Guard Validation and Removed-Switch Audit

Phase 4E tested whether `deep_drawdown_guard` improved results for the right reason.

### Removed Switch Summary

| Removed Switch Count | Avg Slippage | Avg SPY Drawdown | Avg 5D Value Added | 5D Helped % | Avg 20D Value Added | 20D Helped % |
| -------------------: | -----------: | ---------------: | -----------------: | ----------: | ------------------: | -----------: |
|                    6 |       50 bps |         -25.461% |         -1.082 pts |     16.667% |          -2.891 pts |      16.667% |

Phase 4E conclusion:

> The removed switches were genuinely harmful. They occurred in deep drawdowns, carried high execution cost, and had strongly negative average value added.

Final Phase 4E verdict:

> deep_drawdown_guard improved the dynamic baseline by removing genuinely bad switches, not by randomly reducing activity.

---

## Phase 4F: Guard Promotion Validation

Phase 4F tested whether `deep_drawdown_guard` was robust enough to become the execution-realistic overlay candidate.

### Core Result

| System                        |  CAGR | Calmar | Max Drawdown |
| ----------------------------- | ----: | -----: | -----------: |
| Dynamic no-guard baseline     | 9.49% |  0.393 |      -24.12% |
| Dynamic + deep_drawdown_guard | 9.93% |  0.412 |      -24.12% |

### Validation Gates

| Gate                                                               | Status |
| ------------------------------------------------------------------ | ------ |
| Candidate beats pinned SPY 12M strict full-period triple gate      | Passed |
| Candidate improves dynamic no-guard baseline                       | Passed |
| Candidate avoids holdout damage                                    | Passed |
| Candidate avoids material episode-level damage                     | Passed |
| Candidate can be promoted to execution-realistic overlay candidate | Passed |

### Episode Validation

| Episode               | Baseline CAGR / Calmar / Max DD | Guarded CAGR / Calmar / Max DD | Result    |
| --------------------- | ------------------------------: | -----------------------------: | --------- |
| Crisis 2006–2010      |         7.62% / 0.401 / -18.99% |        9.49% / 0.543 / -17.49% | Improved  |
| Post-crisis 2011–2015 |         7.01% / 0.362 / -19.39% |        7.01% / 0.362 / -19.39% | Unchanged |
| Bull/Covid 2016–2020  |        11.25% / 0.466 / -24.12% |       11.25% / 0.466 / -24.12% | Unchanged |
| Inflation 2021–2026   |        12.29% / 0.584 / -21.05% |       12.29% / 0.584 / -21.05% | Unchanged |

### Final Phase 4F Verdict

> deep_drawdown_guard was validated as the execution-realistic overlay candidate.

Important distinction:

| System                                                             | Role                                                                |
| ------------------------------------------------------------------ | ------------------------------------------------------------------- |
| SPY Trend Regime Switch Overlay 3D Confirmed                       | Original Phase 3 canonical system under flat 5 bps slippage         |
| SPY Trend Regime Switch Overlay 3D Confirmed + deep_drawdown_guard | Phase 4 execution-realistic candidate under dynamic stress slippage |

The guarded version should **not** silently replace the original Phase 3 system. They answer different assumptions.

---

## Phase 4 Final Verdict

| System                                                   |   CAGR | Calmar | Max Drawdown |
| -------------------------------------------------------- | -----: | -----: | -----------: |
| Flat 5 bps 3D overlay                                    | 10.22% |  0.429 |      -23.84% |
| Dynamic stress-slippage 3D overlay                       |  9.49% |  0.393 |      -24.12% |
| Dynamic stress-slippage 3D overlay + deep_drawdown_guard |  9.93% |  0.412 |      -24.12% |

Final Phase 4 conclusion:

> The original 3D overlay remains the Phase 3 canonical system. The `deep_drawdown_guard` variant was validated as the best execution-realistic overlay candidate at the Phase 4 checkpoint.

---

# Phase 5: Breadth Confirmation Validation

## Phase 5A: Breadth Confirmation Diagnostic

Phase 5A tested whether a simple market-breadth confirmation layer could improve the Phase 4 execution-realistic candidate.

Benchmark:

| System                                |  CAGR | Calmar | Max Drawdown |
| ------------------------------------- | ----: | -----: | -----------: |
| Phase 4 execution-realistic candidate | 9.93% |  0.412 |      -24.12% |

Tested variants:

* defensive breadth confirmation;
* offensive breadth confirmation;
* combined breadth confirmation.

### Result

| Variant                        |  CAGR | Calmar | Max Drawdown | Holdout CAGR | Verdict              |
| ------------------------------ | ----: | -----: | -----------: | -----------: | -------------------- |
| Phase 4 execution candidate    | 9.93% |  0.412 |      -24.12% |       11.62% | Benchmark            |
| Defensive breadth confirmation | 9.99% |  0.414 |      -24.12% |       11.62% | Marginal improvement |
| Offensive breadth confirmation | 9.33% |  0.386 |      -24.20% |       10.52% | Rejected             |
| Combined breadth confirmation  | 9.39% |  0.389 |      -24.20% |       10.52% | Rejected             |

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

| Variant                     |  CAGR | Calmar | Max Drawdown | Holdout CAGR | Verdict                              |
| --------------------------- | ----: | -----: | -----------: | -----------: | ------------------------------------ |
| Phase 4 execution candidate | 9.93% |  0.412 |      -24.12% |       11.62% | Benchmark                            |
| Breadth 0.33                | 9.70% |  0.402 |      -24.12% |       11.22% | Worse                                |
| Breadth 0.50                | 9.99% |  0.414 |      -24.12% |       11.62% | Tiny improvement, failed materiality |
| Breadth 0.67                | 9.93% |  0.412 |      -24.12% |       11.62% | Same as benchmark                    |

Materiality gate:

```text
Full-period CAGR improvement >= +0.15 pts
Full-period Calmar improvement >= +0.005
```

Best breadth result:

```text
+0.06 pts CAGR
+0.002 Calmar
```

Final Phase 5 verdict:

> Breadth confirmation was rejected for promotion. The improvement was too small to justify added complexity.

---

# Phase 6: Stress Confirmation and Final Candidate Decision

## Phase 6A: SPY Stress Confirmation Diagnostic

Phase 6A tested whether SPY-derived stress filters could improve the Phase 4 execution-realistic candidate.

Tested stress inputs:

* 20D realised volatility;
* 20D SPY return shock;
* SPY distance from 200D trend;
* offensive relief confirmation.

### Defensive Stress Results

| Variant                         |  CAGR | Calmar | Max Drawdown | Verdict               |
| ------------------------------- | ----: | -----: | -----------: | --------------------- |
| Phase 4 execution candidate     | 9.93% |  0.412 |      -24.12% | Benchmark             |
| Defensive volatility stress     | 9.25% |  0.310 |      -29.83% | Rejected              |
| Defensive return shock          | 8.96% |  0.296 |      -30.28% | Rejected              |
| Defensive trend-distance stress | 9.84% |  0.408 |      -24.12% | Rejected / not useful |
| Defensive composite stress      | 9.81% |  0.407 |      -24.12% | Rejected / not useful |

Phase 6A conclusion:

> Defensive stress filters generally worsened performance and sometimes materially worsened drawdown.

### Offensive Relief Lead

| Variant                       |   CAGR | Calmar | Max Drawdown | Holdout CAGR | Switch Count | Verdict                     |
| ----------------------------- | -----: | -----: | -----------: | -----------: | -----------: | --------------------------- |
| Offensive relief confirmation | 10.55% |  0.437 |      -24.12% |       13.14% |           30 | Promising but not validated |

Phase 6A conclusion:

> Defensive stress confirmation was rejected. Offensive relief looked promising, but failed initial validation because it damaged the post-crisis 2011–2015 episode and reduced switch count too aggressively.

---

## Phase 6B: Offensive Relief Validation

Phase 6B tested whether offensive relief was genuinely useful or merely over-filtering re-entry.

| Profile           | Rule Summary                                             |
| ----------------- | -------------------------------------------------------- |
| `strict_relief`   | vol <= 0.16, 20D return >= 0.00, trend distance >= 0.00  |
| `baseline_relief` | vol <= 0.18, 20D return >= -0.02, trend distance >= 0.00 |
| `loose_relief`    | vol <= 0.20, 20D return >= -0.03, trend distance >= 0.00 |

### Result

| Variant                     |   CAGR | Calmar | Max Drawdown | Switch Count | Gate Result |
| --------------------------- | -----: | -----: | -----------: | -----------: | ----------- |
| Phase 4 execution candidate |  9.93% |  0.412 |      -24.12% |           46 | Benchmark   |
| `strict_relief`             | 10.20% |  0.423 |      -24.12% |           30 | Failed      |
| `baseline_relief`           | 10.55% |  0.437 |      -24.12% |           30 | Failed      |
| `loose_relief`              | 10.35% |  0.429 |      -24.12% |           36 | Passed      |

The initial Phase 6B gate logic incorrectly selected the highest headline-score candidate before checking all gates. That was fixed so every candidate was evaluated independently.

Corrected conclusion:

> `baseline_relief` remained rejected despite stronger headline CAGR because it damaged the post-crisis episode and reduced switches too aggressively. `loose_relief` passed all Phase 6B validation gates.

---

## Phase 6C: Final Candidate Decision

Phase 6C compared the final candidate set.

| Candidate                         | Role                                   |
| --------------------------------- | -------------------------------------- |
| SPY Buy & Hold                    | Raw wealth benchmark                   |
| SPY 12M Momentum                  | Simple defensive timing benchmark      |
| Phase 3 flat 5 bps 3D overlay     | Original canonical overlay             |
| Phase 4 execution candidate       | Validated execution-realistic baseline |
| Phase 6B `loose_relief` candidate | Enhanced execution-realistic candidate |

### Full-Period Final Comparison

| Candidate                             |       CAGR |    Calmar | Max Drawdown |      End Value |                       Trade / Switch Count |
| ------------------------------------- | ---------: | --------: | -----------: | -------------: | -----------------------------------------: |
| SPY Buy & Hold                        |     10.90% |     0.197 |      -55.19% |     $79,306.62 |                                          1 |
| SPY 12M Momentum                      |      9.68% |     0.287 |      -33.72% |     $63,497.30 |                                         17 |
| Phase 3 flat 5 bps 3D overlay         |     10.22% |     0.429 |      -23.84% |     $70,048.61 |                                         52 |
| Phase 4 execution candidate           |      9.93% |     0.412 |      -24.12% |     $66,429.13 |                                         46 |
| **Phase 6B `loose_relief` candidate** | **10.35%** | **0.429** |  **-24.12%** | **$71,779.16** | **66 metric trades / 36 overlay switches** |

### Holdout Final Comparison

| Candidate                             | Holdout CAGR | Holdout Calmar | Holdout Max Drawdown |
| ------------------------------------- | -----------: | -------------: | -------------------: |
| SPY Buy & Hold                        |       15.03% |          0.446 |              -33.72% |
| SPY 12M Momentum                      |       11.49% |          0.341 |              -33.72% |
| Phase 3 flat 5 bps 3D overlay         |       12.06% |          0.506 |              -23.84% |
| Phase 4 execution candidate           |       11.62% |          0.482 |              -24.12% |
| **Phase 6B `loose_relief` candidate** |   **12.05%** |      **0.500** |          **-24.12%** |

### Final Gates

| Gate                                                                        | Status |
| --------------------------------------------------------------------------- | ------ |
| Phase 6B candidate improves Phase 4 execution candidate full-period         | Passed |
| Phase 6B candidate avoids holdout damage versus Phase 4 execution candidate | Passed |
| Phase 6B candidate avoids material episode-level damage                     | Passed |
| Phase 6B candidate beats pinned SPY 12M strict full-period triple gate      | Passed |
| Phase 6B candidate beats SPY Buy & Hold on raw CAGR                         | Failed |
| Phase 3 flat 5 bps canonical overlay remains separately documented          | Passed |
| Phase 6B candidate can be promoted as best execution-realistic candidate    | Passed |

Final Phase 6C verdict:

> Phase 6B `loose_relief` was promoted as the best execution-realistic candidate.

Important distinction:

> The project still does **not** beat SPY Buy & Hold on raw wealth. The final promoted candidate is the best execution-realistic risk-adjusted system built so far, not a universal raw-return champion.

---

## Phase 2–6 Bottom Line

Phases 2–6 transformed the project from a collection of simple ETF timing rules into a disciplined tactical-allocation and regime-switch framework.

The hierarchy established by the end of Phase 6 was:

| Role                                   | System                                                            |
| -------------------------------------- | ----------------------------------------------------------------- |
| Raw wealth benchmark                   | SPY Buy & Hold                                                    |
| Simple defensive benchmark             | SPY 12M Absolute Momentum                                         |
| Best standalone balanced allocator     | Top 3 Equal Weight Trend-Confirmed Relative Momentum              |
| Best standalone defensive allocator    | Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum  |
| Original canonical overlay             | SPY 3D Confirmed Overlay under flat 5 bps slippage                |
| Validated execution-realistic baseline | SPY 3D Confirmed Overlay + `deep_drawdown_guard`                  |
| Best execution-realistic candidate     | SPY 3D Confirmed Overlay + `deep_drawdown_guard` + `loose_relief` |

The core conclusion was:

> The project did not find a raw-wealth strategy that consistently beat SPY Buy & Hold. It identified a defensive, execution-realistic SPY regime-switch candidate that materially improved maximum drawdown and Calmar while retaining much of SPY’s long-term compounding.

The progression also produced several broader lessons:

* tactical relative momentum was most valuable during severe equity stress;
* ordinary corrections and transition regimes were more difficult than deep bear markets;
* confirmation reduced, but did not eliminate, trend-boundary whipsaw;
* execution friction was the system’s most important practical vulnerability;
* deep-drawdown defensive switches were often too late and too expensive;
* the `deep_drawdown_guard` improved results by removing demonstrably harmful switches;
* defensive breadth and stress filters generally added complexity without sufficient benefit;
* looser offensive-relief confirmation improved re-entry without causing the damage associated with stricter variants;
* SPY Buy & Hold remained the correct benchmark for raw terminal wealth.

Later phases expanded robustness, operational replay, paper tracking, dynamic opportunity research, and individual-equity modelling. Those later developments do not retroactively change the conclusions reached in Phases 2–6.

---

# Phase 7: Final Validation, Data Reliability, Bootstrap Robustness, and Rolling Survivability

Phase 7 did **not** introduce another strategy variant.

Its purpose was to determine whether the Phase 6C checkpoint could be trusted as a reproducible research result.

The phase focused on:

1. checkpoint integrity;
2. signal and execution timing;
3. secondary data-source reliability;
4. bootstrap and statistical robustness;
5. rolling-window survivability.

Phase 7 deliberately avoided further optimisation. Its role was to narrow the project’s claims, expose weaknesses, and determine whether the Phase 6C candidate deserved to remain the final ETF research checkpoint.

---

## Phase 7A: Final Checkpoint Integrity Audit

Phase 7A checked whether the final Phase 6C checkpoint was internally consistent before tagging.

| Check                                                      | Result |
| ---------------------------------------------------------- | ------ |
| No report endpoint drift beyond 2026-05-01                 | Passed |
| Expected checkpoint reports exist                          | Passed |
| Final candidate metrics match configured checkpoint values | Passed |
| README contains final Phase 6C checkpoint story            | Passed |
| Checkpoint ready to commit and tag                         | Passed |

### Trade Count Clarification

Phase 7A caught an important ambiguity.

| Concept              | Value | Meaning                                             |
| -------------------- | ----: | --------------------------------------------------- |
| Metric trade count   |    66 | Trade count reported by the final metrics framework |
| Overlay switch count |    36 | Number of overlay regime switches in `loose_relief` |

These are not the same thing. The audit checks them separately.

Phase 7A verdict:

> Final checkpoint integrity passed. The Phase 6C candidate metrics, endpoint pin, report existence, and README story were internally consistent.

---

## Phase 7B: Lookahead / Signal-Execution Audit

Phase 7B audited whether the final candidate's signal and execution path could be reconstructed without obvious lookahead leakage.

| Check                                                              | Result |
| ------------------------------------------------------------------ | ------ |
| Required signal/execution columns exist                            | Passed |
| Trend SMA can be reconstructed from trailing `signal_price`        | Passed |
| Raw 3D confirmation state can be reconstructed without future data | Passed |
| Switches occurred only after `trend_sma` availability              | Passed |
| Slippage costs align with positive overlay turnover                | Passed |
| No obvious lookahead issue found                                   | Passed |

### Key Numbers

| Audit Item                        | Result |
| --------------------------------- | -----: |
| Trend SMA rows checked            |  4,834 |
| Trend SMA mismatches              |      0 |
| Trend SMA max absolute difference |    0.0 |
| Raw 3D confirmation rows checked  |  5,034 |
| Raw confirmation mismatches       |      0 |
| Mode switches                     |     36 |
| Slippage rows                     |     37 |
| Turnover rows                     |     37 |
| Slippage-without-turnover rows    |      0 |

One expected diagnostic value was:

```text
positive_bps_without_cost_or_turnover_rows = 4,997
```

This is not a hidden-cost bug. It means the daily dynamic slippage schedule had a positive basis-point value on most days, but costs were only charged when turnover occurred.

The important value is:

```text
slippage_without_turnover_rows = 0
```

Phase 7B verdict:

> No obvious lookahead issue was found in the audited final candidate. This materially strengthened the checkpoint, but it did not make the system production-ready.

---

## Phase 7C and 7C.2: Secondary Data-Source Reliability Audit

Phase 7C compared the primary yfinance adjusted-close data against Stooq daily close data.

Stooq required API-key authentication through a local environment variable:

```text
STOOQ_API_KEY
```

The key is not stored in the repository and should not be committed.

### Initial Cross-Check Result

| Classification          | Count |
| ----------------------- | ----: |
| Clean match             |     4 |
| Acceptable difference   |     4 |
| Review difference       |     2 |
| Potential data issue    |     2 |
| Authentication failures |     0 |
| Unavailable tickers     |     0 |

| Ticker | Classification        | Notes                                                                 |
| ------ | --------------------- | --------------------------------------------------------------------- |
| QQQ    | Clean match           | Strong agreement                                                      |
| GLD    | Clean match           | Strong agreement                                                      |
| SLV    | Clean match           | Strong agreement                                                      |
| USO    | Clean match           | Strong agreement                                                      |
| SPY    | Acceptable difference | Broadly aligned                                                       |
| IWM    | Acceptable difference | Broadly aligned                                                       |
| EEM    | Acceptable difference | Broadly aligned                                                       |
| DBC    | Acceptable difference | Broadly aligned                                                       |
| EFA    | Review difference     | Larger CAGR divergence                                                |
| TLT    | Review difference     | Distribution-sensitive ETF                                            |
| AGG    | Potential data issue  | Distribution-heavy bond ETF; large CAGR divergence versus Stooq close |
| VNQ    | Potential data issue  | Distribution-heavy REIT ETF; large CAGR divergence versus Stooq close |

Initial conclusion:

> A usable secondary data-source cross-check was completed, but broad agreement did not fully pass before attribution because AGG and VNQ showed material differences and EFA/TLT required review.

Phase 7C.2 then investigated whether these differences were genuine data issues or expected price-basis differences.

The main suspicion was:

> Stooq close data is not equivalent to yfinance adjusted-close total-return data, especially for distribution-heavy ETFs.

### Attribution Result

| Item                                   | Count |
| -------------------------------------- | ----: |
| Tickers checked                        |    12 |
| No material data-source concern        |     8 |
| Distribution / price-basis differences |     4 |
| Review differences unresolved          |     0 |
| Unresolved potential data issues       |     0 |

| Ticker | Prior Classification  | Attribution                                  |
| ------ | --------------------- | -------------------------------------------- |
| SPY    | Acceptable difference | No material data-source concern              |
| QQQ    | Clean match           | No material data-source concern              |
| IWM    | Acceptable difference | No material data-source concern              |
| EEM    | Acceptable difference | No material data-source concern              |
| GLD    | Clean match           | No material data-source concern              |
| SLV    | Clean match           | No material data-source concern              |
| DBC    | Acceptable difference | No material data-source concern              |
| USO    | Clean match           | No material data-source concern              |
| EFA    | Review difference     | Likely distribution / price-basis difference |
| AGG    | Potential data issue  | Likely distribution / price-basis difference |
| TLT    | Review difference     | Likely distribution / price-basis difference |
| VNQ    | Potential data issue  | Likely distribution / price-basis difference |

## Phase 7 Final Verdict

Phase 7 strengthened the integrity of the Phase 6C checkpoint while materially narrowing the claim that could be made about it.

| Area                                 | Result               | Interpretation                                                                                                      |
| ------------------------------------ | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Checkpoint integrity                 | Passed               | Metrics, dates, reports, and documentation reconciled                                                               |
| Lookahead and signal-execution audit | Passed               | No obvious future-information leakage was found                                                                     |
| Secondary-source reliability         | Survived with caveat | Broad agreement was established, but Stooq close could not fully validate adjusted total-return data                |
| Bootstrap robustness                 | Passed               | The risk-adjusted advantage survived the primary resampling design                                                  |
| Bootstrap stability                  | Passed               | The conclusion remained stable across tested block lengths and random seeds                                         |
| Rolling-window survivability         | Failed overall       | Medium- and long-window evidence was useful, but short-window liveability and rolling superiority were inconsistent |

Final Phase 7 interpretation:

> The Phase 6C candidate survived checkpoint, timing, data-reliability, and bootstrap audits strongly enough to remain a credible ETF research checkpoint. However, it was not consistently superior across rolling windows and should not be described as a universally dominant, statistically proven, or production-ready trading system.

The correct claim after Phase 7 was therefore narrower:

> The candidate had meaningful full-period and risk-adjusted evidence, but mixed short-window liveability and no guarantee that its historical advantages would persist.

---

## Phase 7D: Bootstrap / Statistical Robustness Audit

Phase 7D tested whether the final Phase 6B `loose_relief` candidate remained robust under paired block-bootstrap resampling of daily returns.

Configuration:

```text
500 bootstrap iterations
21-trading-day blocks
Pinned period: 2006-04-28 to 2026-05-01
```

Comparison set:

* Phase 6B `loose_relief` candidate;
* SPY Buy & Hold;
* SPY 12M Absolute Momentum.

### Bootstrap Probability Results

| Claim                                                 | Probability |                   Gate | Result |
| ----------------------------------------------------- | ----------: | ---------------------: | ------ |
| Candidate beats SPY 12M on CAGR                       |       64.0% |                 >= 55% | Passed |
| Candidate beats SPY 12M on Calmar                     |       72.2% |                 >= 60% | Passed |
| Candidate has better max drawdown than SPY 12M        |       74.0% |                 >= 60% | Passed |
| Candidate beats SPY Buy & Hold on CAGR                |       42.0% | <= 50% hierarchy check | Passed |
| Candidate beats SPY Buy & Hold on Calmar              |       77.8% |                 >= 60% | Passed |
| Candidate has better max drawdown than SPY Buy & Hold |       92.2% |                 >= 70% | Passed |

### Distribution Summary

| Metric              | Candidate | SPY Buy & Hold | SPY 12M |
| ------------------- | --------: | -------------: | ------: |
| Mean CAGR           |    10.42% |         10.88% |   9.70% |
| Median CAGR         |    10.36% |         10.91% |   9.65% |
| Mean Calmar         |     0.405 |          0.304 |   0.340 |
| Median Calmar       |     0.366 |          0.283 |   0.312 |
| Mean max drawdown   |   -28.57% |        -40.01% | -32.30% |
| Median max drawdown |   -27.81% |        -38.70% | -31.18% |

Phase 7D verdict:

> The final candidate survived bootstrap robustness versus SPY 12M and preserved its risk-adjusted advantage versus SPY Buy & Hold.

However:

> The bootstrap did not justify replacing SPY Buy & Hold as the raw wealth benchmark.

Correct interpretation:

> Bootstrap supports the final candidate's risk-adjusted edge, but it does not statistically prove the strategy and does not guarantee future performance.

---

## Phase 7E: Bootstrap Stability Audit

Phase 7E tested whether the Phase 7D bootstrap conclusion depended on one specific resampling setup.

Configuration:

```text
block lengths: 5, 21, 63 trading days
random seeds: 7, 42, 123
bootstrap profiles: 9 total
iterations per profile: 300
```

### Bootstrap Stability Result

| Profile Group              | Result |
| -------------------------- | -----: |
| Total bootstrap profiles   |      9 |
| Profiles passing all gates |      9 |
| Profiles failing any gate  |      0 |

### Probability Stability Summary

| Claim                                                 | Min Probability | Mean Probability | Max Probability | Result                 |
| ----------------------------------------------------- | --------------: | ---------------: | --------------: | ---------------------- |
| Candidate beats SPY 12M on CAGR                       |          59.67% |           63.70% |          68.33% | Passed                 |
| Candidate beats SPY 12M on Calmar                     |          67.67% |           72.78% |          77.00% | Passed                 |
| Candidate has better max drawdown than SPY 12M        |          70.67% |           74.48% |          78.33% | Passed                 |
| Candidate beats SPY Buy & Hold on CAGR                |          36.67% |           41.41% |          49.67% | Passed hierarchy check |
| Candidate beats SPY Buy & Hold on Calmar              |          73.33% |           77.52% |          80.67% | Passed                 |
| Candidate has better max drawdown than SPY Buy & Hold |          92.33% |           93.30% |          94.33% | Passed                 |

Phase 7E verdict:

> The Phase 7D bootstrap conclusion was stable across tested block lengths and random seeds.

Caveat:

```text
max probability candidate beats SPY Buy & Hold CAGR = 49.67%
gate = must remain <= 50%
```

The raw-CAGR hierarchy survived, but only narrowly in the weakest profile. The final candidate remains a risk-adjusted candidate, not a raw-CAGR replacement for SPY Buy & Hold.

---

## Phase 7F: Rolling-Window Survivability Audit

Phase 7F tested whether the final Phase 6B `loose_relief` candidate remained liveable across rolling 1Y, 3Y, and 5Y windows.

Comparison set:

* Phase 6B `loose_relief` candidate;
* SPY Buy & Hold;
* SPY 12M Absolute Momentum.

### Rolling-Window Gate Result

| Window              | Result | Interpretation                                                                            |
| ------------------- | ------ | ----------------------------------------------------------------------------------------- |
| 1Y                  | Failed | Candidate did not consistently beat SPY 12M or Buy & Hold on short-window Calmar/drawdown |
| 3Y vs SPY 12M       | Passed | Candidate beat SPY 12M on 3Y Calmar and drawdown often enough                             |
| 5Y vs SPY 12M       | Passed | Candidate beat SPY 12M on 5Y Calmar and drawdown often enough                             |
| 3Y/5Y vs Buy & Hold | Failed | Candidate did not clear the rolling Buy-and-Hold risk gates                               |
| Worst 3Y/5Y CAGR    | Passed | Candidate avoided negative worst rolling 3Y and 5Y CAGR windows                           |

### Key Rolling-Window Results

| Metric                                     |     1Y |     3Y |     5Y |
| ------------------------------------------ | -----: | -----: | -----: |
| Candidate beats SPY 12M on CAGR            | 39.87% | 64.01% | 73.67% |
| Candidate beats SPY 12M on Calmar          | 36.13% | 68.26% | 73.80% |
| Candidate beats SPY 12M on max drawdown    | 37.26% | 65.46% | 69.77% |
| Candidate beats Buy & Hold on CAGR         | 19.86% | 19.21% | 16.34% |
| Candidate beats Buy & Hold on Calmar       | 20.82% | 37.91% | 52.45% |
| Candidate beats Buy & Hold on max drawdown | 39.35% | 61.53% | 67.52% |

### Worst Rolling Windows

| Window | Worst Candidate CAGR | Period                   |
| ------ | -------------------: | ------------------------ |
| 1Y     |              -15.42% | 2022-01-05 to 2023-01-05 |
| 3Y     |                1.45% | 2017-03-17 to 2020-03-18 |
| 5Y     |                1.73% | 2015-03-19 to 2020-03-19 |

Phase 7F verdict:

> Rolling-window survivability failed overall.

The final candidate was not consistently superior across short rolling windows and did not reliably beat SPY Buy & Hold on rolling risk metrics.

However, this was not a full strategy rejection.

Correct interpretation:

> The final candidate has strong full-period, bootstrap, and medium/long-horizon evidence, but short-window liveability is mixed and must not be oversold.

---

## Phase 7 Final Verdict

Phase 7 strengthened the Phase 6C checkpoint but narrowed the claim.

| Area                               | Result               |
| ---------------------------------- | -------------------- |
| Checkpoint integrity               | Passed               |
| Lookahead / signal-execution audit | Passed               |
| Secondary-source reliability       | Survived with caveat |
| Bootstrap robustness               | Passed               |
| Bootstrap stability                | Passed               |
| Rolling-window survivability       | Failed overall       |

Final Phase 7 interpretation:

> The Phase 6C candidate is a credible research checkpoint, not a universally superior or production-ready trading system. It has strong risk-adjusted evidence, but mixed rolling-window liveability.

---

# Phase 8: Real-World Friction and Research-Boundary Diagnostics

Phase 8 moved beyond backtest-path validation and tested whether the final ETF candidate remained credible after accounting for additional real-world and research-process risks.

It examined:

* simplified tax drag;
* bid-ask spread and market-impact stress;
* sequential walk-forward behaviour;
* behavioural and tracking-error regret;
* research degrees of freedom;
* non-production boundaries;
* final README and configuration consistency.

Phase 8 did **not** add a new alpha signal or optimise the `loose_relief` rule.

Its purpose was to determine how much of the Phase 6C claim survived once practical friction, sequential instability, investor behaviour, and research flexibility were made explicit.

---

## Phase 8A: Simplified Tax-Drag Diagnostic

Phase 8A tested whether the final Phase 6B `loose_relief` candidate survived a simple turnover-based taxable-account drag model.

This was not a production tax engine. It did not model:

* tax lots;
* wash-sale rules;
* dividend taxation;
* final liquidation;
* holding-period rules;
* jurisdiction-specific treatment;
* investor-specific circumstances.

The narrow question was:

> Does the final candidate obviously collapse once turnover creates a simple realised-gain tax drag?

Tested tax-rate proxies:

```text
0%, 10%, 20%, 30%
```

The benchmark gate used the 20% tax-rate proxy.

### Tax-Adjusted Metrics

| Strategy         | Tax Rate |   CAGR | Calmar | Max Drawdown | Avg Annual Tax Drag | Trade Count |
| ---------------- | -------: | -----: | -----: | -----------: | ------------------: | ----------: |
| Final candidate  |       0% | 10.35% |  0.429 |      -24.12% |          0.0000 pts |          66 |
| Final candidate  |      10% | 10.09% |  0.407 |      -24.80% |          0.2426 pts |          66 |
| Final candidate  |      20% |  9.83% |  0.386 |      -25.48% |          0.4851 pts |          66 |
| Final candidate  |      30% |  9.57% |  0.366 |      -26.16% |          0.7277 pts |          66 |
| SPY Buy & Hold   |       0% | 10.90% |  0.197 |      -55.19% |          0.0000 pts |           0 |
| SPY Buy & Hold   |      10% | 10.90% |  0.197 |      -55.19% |          0.0000 pts |           0 |
| SPY Buy & Hold   |      20% | 10.90% |  0.197 |      -55.19% |          0.0000 pts |           0 |
| SPY Buy & Hold   |      30% | 10.90% |  0.197 |      -55.19% |          0.0000 pts |           0 |
| SPY 12M Momentum |       0% |  9.68% |  0.287 |      -33.72% |          0.0000 pts |          14 |
| SPY 12M Momentum |      10% |  9.67% |  0.287 |      -33.72% |          0.0091 pts |          14 |
| SPY 12M Momentum |      20% |  9.66% |  0.286 |      -33.72% |          0.0183 pts |          14 |
| SPY 12M Momentum |      30% |  9.65% |  0.286 |      -33.72% |          0.0274 pts |          14 |

### Benchmark 20% Tax-Proxy Gate Result

| Gate                                                                   | Result |
| ---------------------------------------------------------------------- | ------ |
| Candidate beats SPY 12M after tax on CAGR                              | Passed |
| Candidate beats SPY 12M after tax on Calmar                            | Passed |
| Candidate has better after-tax max drawdown than SPY 12M               | Passed |
| Candidate is not promoted as after-tax raw-CAGR winner over Buy & Hold | Passed |
| Candidate beats Buy & Hold after tax on Calmar                         | Passed |
| Candidate has better after-tax max drawdown than Buy & Hold            | Passed |

At the 20% proxy:

| Comparison                                 |      Value |
| ------------------------------------------ | ---------: |
| Candidate minus SPY 12M CAGR               |  +0.17 pts |
| Candidate minus SPY 12M Calmar             |     +0.100 |
| Candidate drawdown advantage vs SPY 12M    |  +8.24 pts |
| Candidate minus Buy & Hold CAGR            |  -1.07 pts |
| Candidate Calmar advantage vs Buy & Hold   |     +0.189 |
| Candidate drawdown advantage vs Buy & Hold | +29.71 pts |

Phase 8A verdict:

> The final candidate survived the simplified 20% tax-drag diagnostic.

However:

> The tax-adjusted CAGR edge over SPY 12M was thin.

At the 30% proxy, the candidate's CAGR fell to 9.57%, slightly below SPY 12M at 9.65%.

Correct interpretation:

> The final candidate remains credible under a simplified moderate tax-drag proxy, but tax sensitivity is a documented implementation risk. It should not be described as tax-proof.

---

## Phase 8B: Bid-Ask / Market-Impact Stress Diagnostic

Phase 8B tested whether the final Phase 6B `loose_relief` candidate survived additional scenario-based spread and market-impact costs on turnover days.

This was not a production execution simulator. It did not model order books, intraday liquidity, broker routing, partial fills, fund-level liquidity, or real broker execution.

The tested scenarios were:

| Scenario      | Spread bps | Impact bps per 100% turnover | Stress Multiplier | Deep-Stress Multiplier |
| ------------- | ---------: | ---------------------------: | ----------------: | ---------------------: |
| No extra cost |        0.0 |                          0.0 |               1.0 |                    1.0 |
| Moderate      |        2.5 |                          5.0 |               2.0 |                    3.0 |
| Stress        |        5.0 |                         10.0 |               3.0 |                    5.0 |
| Severe        |       10.0 |                         20.0 |               4.0 |                    8.0 |

### Phase 8B Metrics

| Strategy         | Scenario      |   CAGR | Calmar | Max Drawdown | Total Turnover | Trade Count | Avg Annual Extra Drag |
| ---------------- | ------------- | -----: | -----: | -----------: | -------------: | ----------: | --------------------: |
| Final candidate  | No extra cost | 10.35% |  0.429 |      -24.12% |          93.27 |          66 |              0.00 pts |
| Final candidate  | Moderate      |  9.52% |  0.389 |      -24.49% |          93.27 |          66 |              0.76 pts |
| Final candidate  | Stress        |  8.17% |  0.324 |      -25.21% |          93.27 |          66 |              2.00 pts |
| Final candidate  | Severe        |  4.96% |  0.147 |      -33.81% |          93.27 |          66 |              4.95 pts |
| SPY Buy & Hold   | Stress        | 10.90% |  0.198 |      -55.19% |           0.00 |           0 |              0.00 pts |
| SPY 12M Momentum | Stress        |  9.38% |  0.278 |      -33.72% |          14.00 |          14 |              0.27 pts |

### Phase 8B Gate Result

| Gate                                                                  | Result |
| --------------------------------------------------------------------- | ------ |
| Candidate beats SPY 12M on CAGR under stress                          | Failed |
| Candidate beats SPY 12M on Calmar under stress                        | Passed |
| Candidate has better max drawdown than SPY 12M under stress           | Passed |
| Candidate does not become raw-CAGR winner over Buy & Hold             | Passed |
| Candidate beats Buy & Hold on Calmar under stress                     | Passed |
| Candidate has better max drawdown than Buy & Hold under stress        | Passed |
| Candidate CAGR degradation versus no-extra-cost case is not excessive | Failed |

Phase 8B verdict:

> The final candidate failed the configured Phase 8B stress gate.

Under the stress scenario, final-candidate CAGR fell to 8.17% versus SPY 12M at 9.38%. The candidate still preserved better Calmar and max drawdown than SPY 12M and SPY Buy & Hold, but the wealth-growth edge versus SPY 12M did not survive added spread/impact stress.

Correct interpretation:

> The final candidate remains a risk-adjusted path-improvement candidate, but it is meaningfully sensitive to spread/impact assumptions because its turnover is much higher than SPY 12M.

This should narrow the execution-realistic claim. It should **not** trigger immediate threshold tuning.

---

## Phase 8C: Walk-Forward / Expanding-Window Validation Audit

Phase 8C tested the fixed Phase 6B `loose_relief` candidate across sequential forward windows after an expanding training-history period.

This was not a full prospective model-selection test. The final candidate had already been selected.

The audit tested sequential robustness, not whether the rule would have been discovered in real time.

Configuration:

| Setting                          |   Value |
| -------------------------------- | ------: |
| Initial expanding-history period | 5 years |
| Forward test window              | 3 years |
| Step size                        | 3 years |
| Minimum test length              | 2 years |
| Forward windows generated        |       5 |

### Forward-Window Summary

| Metric                                        | Result |
| --------------------------------------------- | -----: |
| Test windows                                  |      5 |
| Candidate positive CAGR rate                  |   100% |
| Candidate beats SPY 12M on CAGR               |    40% |
| Candidate beats SPY 12M on Calmar             |    40% |
| Candidate has better drawdown than SPY 12M    |    80% |
| Candidate beats Buy & Hold on CAGR            |     0% |
| Candidate beats Buy & Hold on Calmar          |    20% |
| Candidate has better drawdown than Buy & Hold |    60% |
| Worst candidate forward-window CAGR           |  5.38% |

### Gate Result

| Gate                                                          | Result |
| ------------------------------------------------------------- | ------ |
| Enough forward windows were generated                         | Passed |
| Candidate beats SPY 12M on CAGR often enough                  | Failed |
| Candidate beats SPY 12M on Calmar often enough                | Failed |
| Candidate has better drawdown than SPY 12M often enough       | Passed |
| Candidate keeps positive CAGR often enough                    | Passed |
| Candidate does not warrant raw-CAGR promotion over Buy & Hold | Passed |
| Candidate beats Buy & Hold on Calmar often enough             | Failed |
| Candidate has better drawdown than Buy & Hold often enough    | Passed |
| Worst candidate forward-window CAGR remains positive          | Passed |

Phase 8C verdict:

> Phase 8C failed / produced mixed walk-forward evidence.

The final candidate stayed positive in every forward window and preserved useful drawdown characteristics, but it did not beat SPY 12M on CAGR or Calmar often enough, and it beat Buy & Hold on Calmar in only 20% of forward windows.

Correct interpretation:

> Phase 8C narrows the validation claim. The candidate has useful path-improvement properties, but its sequential forward-window evidence is mixed and should not be described as clean prospective validation.

---

## Phase 8D: Behavioural / Tracking-Error Regret Audit

Phase 8D tested how painful the final Phase 6B `loose_relief` candidate would feel versus SPY Buy & Hold and SPY 12M Momentum.

This was not a new strategy and did not tune the final candidate. It measured:

* terminal relative wealth;
* time spent lagging benchmarks;
* relative drawdown;
* longest lagging streaks;
* rolling active underperformance.

### Terminal Relative Wealth

| Benchmark        | Terminal Relative Wealth | Candidate CAGR | Benchmark CAGR | Candidate Minus Benchmark CAGR |
| ---------------- | -----------------------: | -------------: | -------------: | -----------------------------: |
| SPY Buy & Hold   |                    0.905 |         10.35% |         10.90% |                      -0.55 pts |
| SPY 12M Momentum |                    1.130 |         10.35% |          9.68% |                      +0.67 pts |

### Rolling Regret Snapshot

| Benchmark        | Window | Underperformance Rate | Mean Active CAGR | Median Active CAGR | Worst Active CAGR |
| ---------------- | -----: | --------------------: | ---------------: | -----------------: | ----------------: |
| SPY Buy & Hold   |     1Y |                68.76% |        -1.20 pts |          -0.65 pts |        -46.51 pts |
| SPY Buy & Hold   |     3Y |                78.04% |        -0.76 pts |          -3.31 pts |        -18.17 pts |
| SPY Buy & Hold   |     5Y |                78.45% |        -1.34 pts |          -3.11 pts |        -11.03 pts |
| SPY 12M Momentum |     1Y |                50.49% |        +0.73 pts |           0.00 pts |        -19.58 pts |
| SPY 12M Momentum |     3Y |                35.87% |        +0.89 pts |          +0.72 pts |         -7.13 pts |
| SPY 12M Momentum |     5Y |                24.78% |        +1.02 pts |          +1.21 pts |         -3.58 pts |

### Gate Result

| Gate                                                           | Result |
| -------------------------------------------------------------- | ------ |
| Terminal relative wealth versus Buy & Hold remains tolerable   | Passed |
| Time lagging Buy & Hold is not excessive                       | Passed |
| Relative drawdown versus Buy & Hold is not excessive           | Failed |
| Longest lagging streak versus Buy & Hold is tolerable          | Passed |
| Terminal relative wealth versus SPY 12M remains favourable     | Passed |
| Time lagging SPY 12M is not excessive                          | Passed |
| 3Y rolling underperformance versus Buy & Hold is not excessive | Passed |
| Worst 3Y active CAGR versus Buy & Hold is tolerable            | Failed |

Phase 8D verdict:

> Phase 8D failed / showed material behavioural regret.

The final candidate remained favourable versus SPY 12M on terminal relative wealth and lagged SPY 12M only rarely over the full period. However, versus SPY Buy & Hold, it suffered a large relative drawdown and a poor worst 3Y active CAGR.

Correct interpretation:

> The final candidate is defensively useful, but behavioural regret versus Buy & Hold is material. Lower absolute drawdown does not automatically make the strategy easy to hold.

---

## Phase 8E: Multiple-Comparisons / Research-Degrees-of-Freedom Audit

Phase 8E documented the number of strategy families, diagnostics, branches, and caveated results that contributed to the final project state.

This was not a formal multiple-comparisons correction. Inventory counts are research-ledger units, not independent statistical trials.

The purpose was to narrow the claim and prevent the final candidate from being overstated.

### Summary

| Metric                         |                    Result |
| ------------------------------ | ------------------------: |
| Research branches documented   |                        11 |
| Total tested units             |                        52 |
| Total promoted units           |                         8 |
| Failed/rejected units          |                        25 |
| Mixed/caveated units           |                        19 |
| Promoted share of tested units |                    15.38% |
| Claim strength after audit     | Narrow / heavily caveated |

### Gate Result

| Gate                                            | Result |
| ----------------------------------------------- | ------ |
| Inventory contains tested research branches     | Passed |
| Failed/rejected branches are documented         | Passed |
| Promoted share of tested units is not excessive | Passed |
| Multiple-comparisons caveat is produced         | Passed |
| Raw wealth hierarchy is preserved               | Passed |
| Final claim is narrow rather than overpromoted  | Passed |

Phase 8E verdict:

> Phase 8E completed the research-degrees-of-freedom audit and narrowed the claim.

Correct interpretation:

> The final candidate emerged after many tested branches, rejected ideas, caveated diagnostics, and validation filters. It should be described as the best execution-realistic risk-adjusted candidate built so far, not as a broadly proven market-beating system.

---

## Phase 8F: Boundary-Control / Non-Production Boundary Audit

Phase 8F documented why Market Strats Lab remains a research-grade systematic strategy lab rather than a production trading system.

This was not production approval.

A pass meant the non-production boundary was documented clearly.

### Summary

| Metric                       | Result |
| ---------------------------- | -----: |
| Total boundary items         |     11 |
| Critical items               |      7 |
| Major items                  |      4 |
| Blocker items                |      7 |
| Gap items                    |      3 |
| Caveat items                 |      1 |
| Categories documented        |      9 |
| Production-ready after audit |  False |
| Live-trading claim           |  False |

### Boundary Categories

| Category   | Items | Critical | Major | Blockers | Gaps | Caveats |
| ---------- | ----: | -------: | ----: | -------: | ---: | ------: |
| Data       |     2 |        2 |     0 |        2 |    0 |       0 |
| Execution  |     2 |        1 |     1 |        1 |    1 |       0 |
| Tax        |     1 |        1 |     0 |        1 |    0 |       0 |
| Portfolio  |     1 |        0 |     1 |        0 |    1 |       0 |
| Monitoring |     1 |        1 |     0 |        1 |    0 |       0 |
| Operations |     1 |        0 |     1 |        0 |    1 |       0 |
| Validation |     1 |        0 |     1 |        0 |    0 |       1 |
| Governance |     1 |        1 |     0 |        1 |    0 |       0 |
| Compliance |     1 |        1 |     0 |        1 |    0 |       0 |

### Gate Result

| Gate                                             | Result |
| ------------------------------------------------ | ------ |
| Audit explicitly preserves non-production status | Passed |
| Audit makes no live-trading claim                | Passed |
| Critical production blockers are documented      | Passed |
| Data risk is documented                          | Passed |
| Execution risk is documented                     | Passed |
| Tax risk is documented                           | Passed |
| Operational/configuration risk is documented     | Passed |
| Monitoring risk is documented                    | Passed |
| Human review / governance boundary is documented | Passed |
| Boundary statement is produced                   | Passed |

Phase 8F verdict:

> Phase 8F documented the research-only boundary.

Correct interpretation:

> The project documented why the final candidate remains research-only and not production-ready. This was a boundary-control pass, not production approval.

---

## Phase 8G: Final Phase 8 Checkpoint / README Consistency Audit

Phase 8G checked that the README, config flags, local Phase 8 report artefacts, final hierarchy, canonical dates, and research-only boundary were internally consistent after Phases 8A–8F.

This was not a strategy test and not production approval.

It did not make the strategy production-ready, live-tradable, or financial advice.

### Audit Scope

| Check Area                                            | Result |
| ----------------------------------------------------- | ------ |
| README contains all required Phase 8 wording          | Passed |
| README contains no forbidden overclaiming phrases     | Passed |
| Config flags match permanent checkpoint state         | Passed |
| Expected Phase 8 report artefacts are present locally | Passed |
| Canonical hierarchy and dates are documented          | Passed |
| Final candidate wording includes full caveat stack    | Passed |

Phase 8G verdict:

> Phase 8G completed the final Phase 8 checkpoint audit.

Correct interpretation:

> Phase 8G confirmed that Phase 8 was internally consistent as a research checkpoint. This closed Phase 8 documentation/config consistency, but it was not production approval and did not change the strategy hierarchy.

---

## Phase 8 Final Verdict

Phase 8 materially narrowed the final ETF candidate’s claim.

| Diagnostic                           | Result                        | Interpretation                                                                            |
| ------------------------------------ | ----------------------------- | ----------------------------------------------------------------------------------------- |
| Simplified tax drag                  | Survived at the 20% proxy     | The advantage over SPY 12M remained, but the CAGR margin was thin                         |
| Bid-ask and market-impact stress     | Failed configured stress gate | Risk-control value survived, but the CAGR advantage over SPY 12M did not                  |
| Walk-forward validation              | Failed / mixed                | The candidate remained positive but did not outperform its benchmarks consistently        |
| Behavioural regret                   | Failed                        | Relative underperformance versus SPY Buy & Hold could be severe and prolonged             |
| Research degrees of freedom          | Completed                     | The final claim was narrowed after documenting the number of tested and rejected branches |
| Boundary-control audit               | Completed                     | The research-only and non-production boundaries were made explicit                        |
| README and configuration consistency | Completed                     | The Phase 8 checkpoint reconciled internally                                              |

Final Phase 8 interpretation:

> The Phase 6B `loose_relief` candidate remained the best execution-realistic ETF risk-adjusted candidate built so far, but the evidence was heavily caveated.

It should not be described as:

* friction-proof;
* tax-proof;
* a clean walk-forward winner;
* behaviourally easy to follow;
* a raw-return replacement for SPY Buy & Hold;
* production-ready;
* live-tradable.

The correct description after Phase 8 was:

> A defensive research candidate with meaningful historical risk-control value, but material sensitivity to costs, sequential market conditions, and investor tracking regret.

# Phase 9: Technical Indicator Extension

Phase 9 tested whether additional price-derived technical indicators could explain where the final ETF candidate helped or failed and whether any tightly bounded technical extension could improve it.

The phase was deliberately constrained. It did **not** permit:

* an open-ended indicator search;
* threshold optimisation;
* repeated rule mutation;
* post-result parameter tuning;
* automatic strategy promotion.

The sequence was:

```text
Phase 9A: diagnostic technical-regime analysis
Phase 9B: cluster-stability audit
Phase 9C: pre-registered technical-rule design specification
Phase 9D: pre-registered technical-rule test
Phase 9E: technical-extension closeout
Phase 9F: final Phase 9 checkpoint audit
```

Phase 9 therefore separated three distinct activities:

1. using technical indicators to explain historical behaviour;
2. testing whether those diagnostic patterns were stable;
3. testing only the pre-registered rules that survived the design stage.

The final Phase 9 conclusion was:

> Technical indicators produced useful explanatory evidence, but no pre-registered technical rule passed validation. The final candidate hierarchy remained unchanged.

---

## Phase 9A: Technical Indicator Expansion Diagnostic

Phase 9A tested whether additional price-derived technical indicators helped explain where the final candidate helped or failed.

This was diagnostic only. It did not create, tune, or promote a new trading rule.

### Summary

| Metric                                               |     Result |
| ---------------------------------------------------- | ---------: |
| Start date                                           | 2006-04-28 |
| End date                                             | 2026-05-01 |
| Rows                                                 |      5,034 |
| Indicator coverage rate                              |     94.99% |
| Technical regime rows                                |         25 |
| Underperformance cluster rows                        |         15 |
| Candidate underperforms Buy & Hold daily-return rate |     10.91% |
| Candidate underperforms SPY 12M daily-return rate    |     11.62% |

### Main Findings

Candidate underperformance versus Buy & Hold was most concentrated in:

* intermediate drawdowns;
* near-long-SMA transition zones;
* mild drawdowns;
* high-volatility regimes;
* overbought regimes.

The candidate’s defensive usefulness was more visible in:

* deep bear states;
* below-long-SMA regimes;
* negative 12-month momentum regimes;
* oversold regimes.

### Gate Result

| Gate                                       | Result |
| ------------------------------------------ | ------ |
| Indicator coverage is sufficient           | Passed |
| Technical regime rows were generated       | Passed |
| Underperformance clusters were reported    | Passed |
| Diagnostic does not promote a new strategy | Passed |
| Diagnostic role remains bounded            | Passed |

Phase 9A verdict:

> Phase 9A completed as a diagnostic-only technical indicator expansion.

Correct interpretation:

> Phase 9A produced interpretable technical-regime evidence, but did not change the final candidate hierarchy. The results could inform future hypotheses, but they were not validated trading rules.

---

## Phase 9B: Technical Regime Cluster Stability Audit

Phase 9B tested whether the Phase 9A technical-regime clusters were stable across subperiods and market episodes.

This was diagnostic only. It did not create, tune, validate, or promote a trading rule.

### Summary

| Metric                                   | Result |
| ---------------------------------------- | -----: |
| Cluster episode metric rows              |    110 |
| Stability rows                           |     25 |
| Stable across both benchmarks            |      6 |
| Unstable rows                            |     19 |
| Instability report rows                  |     15 |
| Helpful stability report rows            |     13 |
| Mean direction consistency vs Buy & Hold | 79.33% |
| Mean direction consistency vs SPY 12M    | 61.33% |

### Main Findings

Phase 9B showed that the Phase 9A technical-regime evidence was useful but mixed.

The most stable helpful cluster was:

```text id="7lrzp0"
rsi_bucket = oversold_below_30
```

This helped versus both Buy & Hold and SPY 12M with full direction consistency across covered episodes.

Another useful cluster was:

```text id="fpu1g9"
long_momentum_state = negative_12m_momentum
```

This remained especially useful versus SPY 12M.

However, most clusters were unstable. Only 6 of 25 stability rows were stable across both benchmarks.

Correct interpretation:

> Phase 9A/9B evidence was useful for hypothesis generation, but too unstable to become trading rules directly.

### Gate Result

| Gate                                       | Result |
| ------------------------------------------ | ------ |
| Cluster stability rows were generated      | Passed |
| Instability report was produced            | Passed |
| Helpful stability report was produced      | Passed |
| Diagnostic does not promote a new strategy | Passed |
| Diagnostic role remains bounded            | Passed |

Phase 9B verdict:

> Phase 9B completed as a diagnostic-only technical regime cluster stability audit.

---

## Phase 9C: Pre-Registered Technical Rule Design Spec

Phase 9C pre-registered the only technical-rule hypotheses allowed to move into a later Phase 9D test.

This was not a strategy test, backtest, parameter search, or promotion decision.

### Summary

| Metric                                                  |                          Result |
| ------------------------------------------------------- | ------------------------------: |
| Spec role                                               | Pre-registered design spec only |
| Proposed test phase                                     |                        Phase 9D |
| Hypothesis count                                        |                               2 |
| Allowed input rows                                      |                               8 |
| Allowed inputs all registered                           |                            True |
| Forbidden keyword rows                                  |                              32 |
| Forbidden keywords absent from testable hypothesis text |                            True |
| Validation gate rows                                    |                              18 |
| Forbidden action rows                                   |                               6 |

### Pre-Registered Hypotheses

| Hypothesis                                        | Description                                             |
| ------------------------------------------------- | ------------------------------------------------------- |
| `H1_oversold_rsi_reentry_relief`                  | Oversold RSI re-entry relief hypothesis                 |
| `H2_negative_12m_momentum_defensive_confirmation` | Negative 12M momentum defensive confirmation hypothesis |

### Gate Result

| Gate                                                       | Result |
| ---------------------------------------------------------- | ------ |
| Hypothesis count is bounded                                | Passed |
| Source evidence is documented                              | Passed |
| Allowed inputs are documented                              | Passed |
| Forbidden inputs are documented                            | Passed |
| Proposed rule logic is documented                          | Passed |
| Validation gates are documented                            | Passed |
| Failure conditions are documented                          | Passed |
| README wording outcomes are documented                     | Passed |
| Promotion constraints are documented                       | Passed |
| Allowed inputs stay inside registry                        | Passed |
| Forbidden keywords are absent from allowed hypothesis text | Passed |
| Spec does not allow strategy testing                       | Passed |
| Spec does not allow parameter optimisation                 | Passed |
| Spec does not allow strategy promotion                     | Passed |
| Spec role is correct                                       | Passed |

Phase 9C verdict:

> Phase 9C completed as a pre-registered technical rule design spec.

Correct interpretation:

> Phase 9C pre-registered the only technical-rule hypotheses allowed for Phase 9D. It did not run performance tests, tune parameters, or promote a strategy.

---

## Phase 9D: Pre-Registered Technical Rule Test

Phase 9D tested only the two Phase 9C pre-registered technical-rule hypotheses:

1. `H1_oversold_rsi_reentry_relief`
2. `H2_negative_12m_momentum_defensive_confirmation`

This was not an open-ended indicator search. It did not add new inputs, search thresholds, or promote a strategy.

### Summary

| Rule                                              | Full CAGR | Full Calmar | Result             |
| ------------------------------------------------- | --------: | ----------: | ------------------ |
| `H1_oversold_rsi_reentry_relief`                  |     5.52% |       0.102 | Failed             |
| `H2_negative_12m_momentum_defensive_confirmation` |     8.66% |       0.266 | Failed             |
| Baseline final candidate                          |    10.35% |       0.429 | Existing benchmark |

### Gate Result

Both pre-registered rules failed the configured validation gates.

They failed on:

* full-period CAGR;
* full-period Calmar;
* max drawdown;
* holdout performance;
* episode damage;
* stress-friction performance;
* behavioural relative drawdown versus Buy & Hold.

The only gates they passed were discipline gates confirming that the rules were not promoted and remained bounded.

Phase 9D verdict:

> Phase 9D failed. No pre-registered technical rule passed.

Correct interpretation:

> Phase 9A/9B technical-regime evidence was useful diagnostically, but the two Phase 9C rule implementations failed validation. No technical rule should be promoted or tuned around this result.

---

## Phase 9E: Technical Extension Closeout / Failure Documentation Audit

Phase 9E closed the Phase 9 technical-extension branch after the Phase 9D rule test failed.

This did not create a new rule, tune a failed rule, or promote a successor candidate.

### Summary

| Metric                      | Result                                               |
| --------------------------- | ---------------------------------------------------- |
| Branch                      | Phase 9 technical indicator extension                |
| Status                      | Closed — no rule promoted                            |
| Successor candidate created | False                                                |
| Final candidate changed     | False                                                |
| Rule promotion allowed      | False                                                |
| Next allowed step           | Phase 9 final README/checkpoint consistency or pause |

### Gate Result

| Gate                                         | Result |
| -------------------------------------------- | ------ |
| Expected Phase 9 reports are present         | Passed |
| Config flags match closeout state            | Passed |
| Phase 9D failure is documented               | Passed |
| No Phase 9D rule passed all gates            | Passed |
| No strategy promotion occurred               | Passed |
| No successor candidate was created           | Passed |
| Technical branch is closed without promotion | Passed |

Phase 9E verdict:

> Phase 9E completed the technical-extension closeout audit.

Correct interpretation:

> Phase 9A/9B remained diagnostic, Phase 9C pre-registered two hypotheses, Phase 9D rejected both, and Phase 9E closed the branch without promotion.

---

## Phase 9F: Final Phase 9 Checkpoint / README Consistency Audit

Phase 9F checked that the README, config flags, local Phase 9 report artefacts, final hierarchy, canonical dates, and technical-extension closeout were internally consistent after Phases 9A–9E.

This was not a strategy test and not production approval.

### Gate Result

| Gate                                                  | Result |
| ----------------------------------------------------- | ------ |
| README contains all required Phase 9 wording          | Passed |
| README contains no forbidden overclaiming phrases     | Passed |
| Config flags match permanent checkpoint state         | Passed |
| Expected Phase 9 report artefacts are present locally | Passed |
| Canonical hierarchy and dates are documented          | Passed |
| Phase 9 closeout is documented                        | Passed |
| No technical rule was promoted                        | Passed |
| No successor candidate was created                    | Passed |

Phase 9F verdict:

> Phase 9F completed the final Phase 9 checkpoint audit.

Correct interpretation:

> Phase 9A/9B diagnostic evidence, Phase 9C pre-registration, Phase 9D failure, and Phase 9E closeout were documented consistently. No technical rule was promoted and the final candidate hierarchy remained unchanged.

---

## Phase 9 Final Verdict

| Phase | Result                     | Interpretation                                                                |
| ----- | -------------------------- | ----------------------------------------------------------------------------- |
| 9A    | Diagnostic completed       | Technical regimes helped explain where the candidate helped or underperformed |
| 9B    | Stability audit completed  | A small number of clusters were useful, but most were unstable                |
| 9C    | Pre-registration completed | Only two bounded technical-rule hypotheses were permitted                     |
| 9D    | Failed                     | Neither pre-registered technical rule passed validation                       |
| 9E    | Closeout completed         | The technical-extension branch was closed without promotion                   |
| 9F    | Checkpoint audit completed | README, configuration, reports, and closeout status reconciled                |

Final Phase 9 interpretation:

> Technical indicators were valuable as diagnostic tools but failed as validated rule extensions.

The branch produced several useful lessons:

* explanatory clusters are not automatically tradable rules;
* apparent regime relationships can be unstable across periods;
* pre-registration prevented further threshold search after failure;
* the failed rules were documented rather than retuned;
* no successor candidate was created;
* the Phase 6C ETF hierarchy remained unchanged.

The correct conclusion was therefore:

> Phase 9 improved understanding of the existing candidate but did not improve the candidate itself.

---

# Phase 10: Macro, Rates, and Inflation Extension

Phase 10 tested whether macroeconomic, interest-rate, and inflation data could be introduced into the framework without compromising point-in-time integrity or creating hidden lookahead risk.

The phase deliberately began with:

* feature-family selection;
* source feasibility;
* release-date policies;
* revision and vintage controls;
* conservative point-in-time alignment;
* diagnostic analysis.

Only after those controls passed were a small number of macro-rule hypotheses pre-registered and tested.

The sequence was:

```text
Phase 10A: feature-family feasibility specification
Phase 10B: macro source and leakage feasibility audit
Phase 10C: source reliability and point-in-time alignment audit
Phase 10D: diagnostic-only macro regime analysis
Phase 10E: pre-registered macro hypothesis design specification
Phase 10F: pre-registered macro-rule test
Phase 10G: macro-branch closeout
Phase 10H: final Phase 10 checkpoint audit
```

Phase 10 did not permit:

* unrestricted macro-feature search;
* post-result threshold optimisation;
* repeated rule mutation;
* silent use of revised data as though it had been known historically;
* model training;
* automatic strategy promotion.

The final Phase 10 conclusion was:

> Macro, rates, and inflation data were feasible to source, align, and analyse safely, but neither pre-registered macro rule passed validation. No macro rule was promoted, no successor candidate was created, and the ETF strategy hierarchy remained unchanged.

---

## Phase 10A: Feature-Family Feasibility Spec

Phase 10A evaluated which non-price feature family should enter the framework first.

This was a feasibility specification only. It did not ingest data, train a model, test a strategy, or promote a candidate.

### Summary

| Metric                        |                               Result |
| ----------------------------- | -----------------------------------: |
| Spec role                     | Feature-family feasibility spec only |
| Proposed next phase           |                            Phase 10B |
| Feature-family count          |                                    4 |
| Data requirement rows         |                                    4 |
| Leakage control rows          |                                   15 |
| Validation requirement rows   |                                   12 |
| Scorecard rows                |                                    4 |
| Recommended family            |              `macro_rates_inflation` |
| Matches expected first family |                                 True |

### Feature-Family Ranking

| Rank | Feature Family            | Interpretation                                          |
| ---: | ------------------------- | ------------------------------------------------------- |
|    1 | Macro / rates / inflation | Selected as first non-price family to audit             |
|    2 | Fundamental / valuation   | Future candidate; slower-moving and timing-sensitive    |
|    3 | Sentiment / narrative     | Future candidate; noisy and high overfit risk           |
|    4 | ML / ensemble modelling   | Long-term branch only; premature without clean features |

### Gate Result

| Gate                                             | Result |
| ------------------------------------------------ | ------ |
| Feature-family count is bounded                  | Passed |
| Recommended family matches expected first family | Passed |
| Recommended family has no active disqualifier    | Passed |
| Each family documents data requirements          | Passed |
| Each family documents leakage controls           | Passed |
| Each family documents validation requirements    | Passed |
| Scorecard exists for all families                | Passed |
| Spec does not allow data ingestion               | Passed |
| Spec does not allow model training               | Passed |
| Spec does not allow strategy testing             | Passed |
| Spec does not allow strategy promotion           | Passed |
| Spec role is correct                             | Passed |

Phase 10A verdict:

> Phase 10A completed as a feature-family feasibility spec.

Correct interpretation:

> Phase 10A selected macro/rates/inflation as the first non-price feature family to audit. It did not ingest data, train a model, test a strategy, or promote a candidate.

---

## Phase 10B: Macro / Rates / Inflation Data-Source and Leakage Feasibility Audit

Phase 10B audited whether macro/rates/inflation data sources were feasible enough for a later point-in-time data-source audit.

This phase did not download data, engineer features, create signals, train models, test strategies, or promote candidates.

### Summary

| Metric                                       |                                         Result |
| -------------------------------------------- | ---------------------------------------------: |
| Audit role                                   | Data-source and leakage feasibility audit only |
| Recommended family                           |                        `macro_rates_inflation` |
| Proposed next phase                          |                                      Phase 10C |
| Source candidate count                       |                                              5 |
| Release-policy ready count                   |                                              5 |
| Revision-policy ready count                  |                                              5 |
| Leakage-controls ready count                 |                                              5 |
| Vintage-capable source count                 |                                              1 |
| Recommended source count for Phase 10C audit |                                              3 |

### Recommended Sources for Phase 10C

| Source                       | Role                                      |
| ---------------------------- | ----------------------------------------- |
| `fred_alfred_macro_vintage`  | General macro / vintage-capable candidate |
| `treasury_rates_yield_curve` | Rates and yield-curve candidate           |
| `bls_cpi_inflation`          | Inflation candidate                       |

BEA growth/activity and NBER recession dates remained documented but constrained.

Important limitation:

> BEA-style data carries revision-treatment risk, and NBER recession dates are suitable only for ex-post labelling/diagnostics, not live decision inputs.

### Gate Result

| Gate                                             | Result |
| ------------------------------------------------ | ------ |
| Source candidate count is sufficient             | Passed |
| Recommended family is macro/rates/inflation      | Passed |
| No data download is allowed in Phase 10B         | Passed |
| No feature engineering is allowed in Phase 10B   | Passed |
| No signal creation is allowed in Phase 10B       | Passed |
| No model training is allowed in Phase 10B        | Passed |
| No strategy test is allowed in Phase 10B         | Passed |
| No strategy promotion is allowed in Phase 10B    | Passed |
| Each source has a release-date policy            | Passed |
| Each source has a revision policy                | Passed |
| Each source has leakage controls                 | Passed |
| At least one source has vintage/revision support | Passed |
| At least one rates source is present             | Passed |
| At least one inflation source is present         | Passed |
| No source is allowed for strategy testing now    | Passed |
| Phase 10C boundary is data-audit only            | Passed |
| Audit role is correct                            | Passed |

Phase 10B verdict:

> Phase 10B completed as a macro/rates/inflation data-source leakage feasibility audit.

Correct interpretation:

> Phase 10B found that selected macro/rates/inflation data-source candidates were feasible enough to audit in Phase 10C. Phase 10C was allowed only as a data-source reliability and point-in-time alignment audit.

---

## Phase 10C: Macro Source Reliability and Point-in-Time Alignment Audit

Phase 10C loaded/fetched selected macro/rates/inflation sources and checked:

* source reliability;
* historical coverage;
* conservative trading-day lagging;
* revision/vintage risk documentation;
* missingness;
* Phase 10D readiness.

This did not create macro signals, allocation rules, predictive model features, model training, strategy tests, or candidate promotion.

### Summary

| Metric                       |                                                          Result |
| ---------------------------- | --------------------------------------------------------------: |
| Audit role                   | Macro source reliability and point-in-time alignment audit only |
| Recommended family           |                                         `macro_rates_inflation` |
| Proposed next phase          |                                                       Phase 10D |
| Selected source count        |                                                               3 |
| Series count                 |                                                               4 |
| Loaded series count          |                                                               4 |
| Phase 10D ready series count |                                                               4 |
| Phase 10D allowed            |                                                            True |

### Loaded Series

| Series     | Role                                 | Raw Rows | Aligned Rows | Non-Missing Aligned Rows |
| ---------- | ------------------------------------ | -------: | -----------: | -----------------------: |
| `UNRATE`   | Labour-market proxy                  |      940 |        5,034 |                    5,008 |
| `DGS2`     | 2-year Treasury yield / rates proxy  |   13,038 |        5,034 |                    4,961 |
| `DGS10`    | 10-year Treasury yield / rates proxy |   16,798 |        5,034 |                    4,969 |
| `CPIAUCSL` | CPI / inflation proxy                |      952 |        5,034 |                    4,996 |

### Gate Result

| Gate                                                                | Result |
| ------------------------------------------------------------------- | ------ |
| Selected source count is sufficient                                 | Passed |
| Remote/local macro series load succeeded                            | Passed |
| Release-date policies are documented                                | Passed |
| Revision/vintage policies are documented                            | Passed |
| Aligned series meet missingness threshold                           | Passed |
| Conservative trading-day lag is applied                             | Passed |
| Revision risk is documented for every series                        | Passed |
| Rates series is ready for diagnostic audit                          | Passed |
| Inflation series is ready for diagnostic audit                      | Passed |
| Macro series is ready for diagnostic audit                          | Passed |
| No macro signal creation is allowed                                 | Passed |
| No allocation rule creation is allowed                              | Passed |
| No model feature creation is allowed                                | Passed |
| No model training is allowed                                        | Passed |
| No strategy test is allowed                                         | Passed |
| No strategy promotion is allowed                                    | Passed |
| Phase 10D boundary is diagnostic-only                               | Passed |
| Enough series are ready to allow Phase 10D diagnostic-only analysis | Passed |
| Audit role is correct                                               | Passed |

Phase 10C verdict:

> Phase 10C completed as a macro source reliability and point-in-time alignment audit.

Correct interpretation:

> Phase 10C loaded and aligned the selected macro/rates/inflation sources with conservative trading-day lagging and documented revision risk. Phase 10D was allowed only as diagnostic macro-regime analysis.

---

## Phase 10D: Diagnostic-Only Macro Regime Analysis

Phase 10D analysed whether macro/rates/inflation regimes helped explain where the final candidate behaved better or worse versus SPY Buy & Hold and SPY 12M Momentum.

This did not create macro signals, allocation rules, predictive model features, model training, strategy tests, or candidate promotion.

### Summary

| Metric                    |                                Result |
| ------------------------- | ------------------------------------: |
| Diagnostic role           | Diagnostic-only macro regime analysis |
| Proposed next phase       |                             Phase 10E |
| Macro panel rows          |                                 5,033 |
| Regime family count       |                                     5 |
| Regime metric rows        |                                    15 |
| Helpful regime rows       |                                     9 |
| Weak regime rows          |                                     4 |
| Phase 10E boundary passed |                                  True |

### Diagnostic Observations

Phase 10D found that macro/rates/inflation regimes were diagnostically informative, but not strategy-promotional.

The final candidate looked comparatively more useful in several lower-rate, lower-inflation, and improving-labour-market regimes.

| Regime                       | Diagnostic Interpretation                                                               |
| ---------------------------- | --------------------------------------------------------------------------------------- |
| `low_short_rates_below_1_5`  | Helpful versus both benchmarks on risk-adjusted / drawdown-style diagnostics            |
| `low_inflation_below_2`      | Helpful versus both benchmarks on risk-adjusted / drawdown-style diagnostics            |
| `unemployment_falling`       | Helpful versus both benchmarks                                                          |
| `normal_unemployment_4_to_6` | Helpful versus both benchmarks                                                          |
| `yield_curve_inverted`       | Helpful versus both benchmarks, but economically complex and must be treated cautiously |

The final candidate looked weaker or mixed in several regimes.

| Regime                      | Diagnostic Interpretation                                      |
| --------------------------- | -------------------------------------------------------------- |
| `high_short_rates_above_4`  | Weak versus both benchmarks                                    |
| `high_unemployment_above_6` | Mixed/weak, especially versus SPY 12M                          |
| `unemployment_stable`       | Weak versus both benchmarks on configured weak-regime criteria |
| `low_unemployment_below_4`  | Weak versus both benchmarks on configured weak-regime criteria |

### Gate Result

| Gate                                   | Result |
| -------------------------------------- | ------ |
| Macro panel loaded                     | Passed |
| UNRATE is present                      | Passed |
| DGS2 is present                        | Passed |
| DGS10 is present                       | Passed |
| CPIAUCSL is present                    | Passed |
| Regime family count is sufficient      | Passed |
| Regime metrics were generated          | Passed |
| No macro signal creation is allowed    | Passed |
| No allocation rule creation is allowed | Passed |
| No model feature creation is allowed   | Passed |
| No model training is allowed           | Passed |
| No strategy test is allowed            | Passed |
| No strategy promotion is allowed       | Passed |
| Phase 10E boundary is spec-only        | Passed |
| Diagnostic role is correct             | Passed |

Phase 10D verdict:

> Phase 10D completed as diagnostic-only macro regime analysis.

Correct interpretation:

> Phase 10D produced macro/rates/inflation regime diagnostics that justified pre-registering macro hypotheses in Phase 10E. It did not create a macro signal, allocation rule, model feature, strategy test, or candidate promotion.

---

## Phase 10E: Pre-Registered Macro Hypothesis Design Spec

Phase 10E pre-registered the only macro hypotheses allowed to move into a later Phase 10F macro-rule test.

This did not create macro signals, allocation overlays, predictive model features, model training, strategy tests, or candidate promotion.

### Summary

| Metric                        |                                           Result |
| ----------------------------- | -----------------------------------------------: |
| Spec role                     | Pre-registered macro hypothesis design spec only |
| Proposed test phase           |                                        Phase 10F |
| Hypothesis count              |                                                2 |
| Allowed input rows            |                                               13 |
| Allowed inputs all registered |                                             True |
| Forbidden input rows          |                                               14 |
| Validation gate rows          |                                               16 |
| Failure condition rows        |                                               10 |

### Pre-Registered Hypotheses

| Hypothesis                                    | Description                                                                                          | Max Allowed Role After Phase 10F      |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `H1_supportive_low_rate_low_inflation_relief` | Fixed low-rate / low-inflation supportive macro-relief hypothesis derived from Phase 10D diagnostics | Candidate for further validation only |
| `H2_high_rate_high_unemployment_stress_guard` | Fixed high-rate / high-unemployment macro stress-guard hypothesis derived from Phase 10D diagnostics | Candidate for further validation only |

### Gate Result

| Gate                                           | Result |
| ---------------------------------------------- | ------ |
| Hypothesis count is bounded                    | Passed |
| Source evidence is documented                  | Passed |
| Allowed macro inputs are documented            | Passed |
| Allowed macro inputs stay inside registry      | Passed |
| Forbidden inputs are documented                | Passed |
| Fixed thresholds are documented                | Passed |
| Validation gates are documented                | Passed |
| Failure conditions are documented              | Passed |
| README wording outcomes are documented         | Passed |
| Phase 10F boundary is pre-registered-test only | Passed |
| Spec does not allow macro signal creation      | Passed |
| Spec does not allow allocation rule creation   | Passed |
| Spec does not allow model feature creation     | Passed |
| Spec does not allow model training             | Passed |
| Spec does not allow strategy testing           | Passed |
| Spec does not allow strategy promotion         | Passed |
| Spec role is correct                           | Passed |

Phase 10E verdict:

> Phase 10E completed as a pre-registered macro hypothesis design spec.

Correct interpretation:

> Phase 10E pre-registered the only macro hypotheses allowed for Phase 10F. It did not create a macro signal, allocation rule, model feature, strategy test, or candidate promotion.

---

## Phase 10F: Pre-Registered Macro Rule Test

Phase 10F tested only the two Phase 10E pre-registered macro hypotheses:

1. `H1_supportive_low_rate_low_inflation_relief`
2. `H2_high_rate_high_unemployment_stress_guard`

This did not add new inputs, thresholds, sentiment, fundamentals, ML, optimisation, or candidate promotion.

### Summary

| Metric                  |                                       Result |
| ----------------------- | -------------------------------------------: |
| Discipline gates passed |                                         True |
| Any rule passed         |                                        False |
| Passed rules            |                                         None |
| Strategy promotion      |                                        False |
| Verdict                 | Failed / no pre-registered macro rule passed |

### Rule Outcomes

| Rule                                          | Result | Interpretation                                                                                                                                            |
| --------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `H1_supportive_low_rate_low_inflation_relief` | Failed | Higher CAGR, but worse Calmar, worse drawdown, holdout drawdown damage, episode damage, stress-friction failure, and raw-CAGR overclaim versus Buy & Hold |
| `H2_high_rate_high_unemployment_stress_guard` | Failed | Better headline CAGR/Calmar and preserved drawdown, but failed episode-damage control and stress-friction survival                                        |

### Gate Interpretation

H1 failed because it improved raw return at the cost of materially worse drawdown and weaker robustness.

H2 produced more interesting evidence, but still failed the pre-registered episode-damage and stress-friction gates.

Correct interpretation:

> H2 was interesting, but it still failed. It cannot be promoted, softened, or tuned around after the fact.

Phase 10F verdict:

> Phase 10F failed. No pre-registered macro rule passed all configured gates.

---

## Phase 10G: Macro Branch Closeout / Failure Documentation Audit

Phase 10G closed the Phase 10 macro/rates/inflation branch after the Phase 10F rule test failed.

This was not a new strategy test. It confirmed that no macro rule was promoted, no successor candidate was created, and the final candidate hierarchy remained unchanged.

### Summary

| Metric                      | Result                                                           |
| --------------------------- | ---------------------------------------------------------------- |
| Branch                      | Phase 10 macro/rates/inflation extension                         |
| Status                      | Closed — no macro rule promoted                                  |
| Next allowed step           | Phase 10H final Phase 10 checkpoint audit or architecture review |
| Successor candidate created | False                                                            |
| Final candidate changed     | False                                                            |

### Phase 10F Failure Check

| Check                                            | Result |
| ------------------------------------------------ | ------ |
| Phase 10F conclusion report exists               | Passed |
| Phase 10F conclusion documents failure           | Passed |
| Phase 10F conclusion says no rule passed         | Passed |
| No Phase 10F rule passed from rule gate report   | Passed |
| No Phase 10F rule passed from comparison summary | Passed |
| Phase 10F discipline gates passed                | Passed |
| Phase 10F did not promote a strategy             | Passed |

### Gate Result

| Gate                                     | Result |
| ---------------------------------------- | ------ |
| Expected Phase 10 reports are present    | Passed |
| Config flags match closeout state        | Passed |
| Phase 10F failure is documented          | Passed |
| No Phase 10F rule passed all gates       | Passed |
| Phase 10F discipline gates passed        | Passed |
| No strategy promotion occurred           | Passed |
| No successor candidate was created       | Passed |
| Final candidate remains unchanged        | Passed |
| Macro branch is closed without promotion | Passed |
| Audit role is correct                    | Passed |

Phase 10G verdict:

> Phase 10G completed the macro extension closeout without promotion.

Correct interpretation:

> Phase 10A–10D showed that macro/rates/inflation data was feasible and diagnostically informative, but Phase 10F failed as a pre-registered macro-rule test. No macro rule was promoted, no successor candidate was created, and the final hierarchy remained unchanged.

---

## Phase 10H: Final Phase 10 Checkpoint and README–Config–Report Consistency Audit

Phase 10H verified the final Phase 10 record after the macro/rates/inflation branch was closed without promotion.

This was not a new strategy test. It checked README wording, config flags, report inventory, Phase 10G closeout, Phase 10F failure documentation, canonical hierarchy, and promotion boundaries.

### Summary

| Metric                                    | Result |
| ----------------------------------------- | ------ |
| README required Phase 10 phrases present  | True   |
| README forbidden overclaim phrases absent | True   |
| Expected Phase 10 reports present         | True   |
| Config flags clean                        | True   |
| Phase 10G closeout passed                 | True   |
| Phase 10F failure locked                  | True   |
| No successor candidate created            | True   |
| Final candidate unchanged                 | True   |
| Canonical hierarchy present               | True   |
| Strategy promotion                        | False  |

### Gate Result

| Gate                                               | Result |
| -------------------------------------------------- | ------ |
| README required Phase 10 phrases are present       | Passed |
| README forbidden overclaim phrases are absent      | Passed |
| Expected Phase 10 reports are present              | Passed |
| Config flags match final Phase 10 checkpoint state | Passed |
| Phase 10G closeout passed                          | Passed |
| Phase 10F failure remains locked                   | Passed |
| No successor candidate was created                 | Passed |
| Final candidate remains unchanged                  | Passed |
| Canonical hierarchy is present                     | Passed |
| No strategy promotion occurred                     | Passed |
| Audit role is correct                              | Passed |

Phase 10H verdict:

> Phase 10H completed the final Phase 10 checkpoint.

Correct interpretation:

> Phase 10 is closed cleanly. Macro/rates/inflation evidence was feasible and diagnostically informative, but the pre-registered macro-rule test failed. No macro rule was promoted, no successor candidate was created, and the final hierarchy remained unchanged.

---

## Phase 10 Final Verdict

| Phase | Result                                  | Interpretation                                                                  |
| ----- | --------------------------------------- | ------------------------------------------------------------------------------- |
| 10A   | Feasibility specification completed     | Macro, rates, and inflation were selected as the first non-price feature family |
| 10B   | Source and leakage feasibility passed   | Suitable sources and timing controls were identified                            |
| 10C   | Source reliability and alignment passed | Four macro series were loaded and conservatively aligned                        |
| 10D   | Diagnostic analysis completed           | Macro regimes helped explain candidate behaviour                                |
| 10E   | Pre-registration completed              | Only two bounded macro hypotheses were permitted                                |
| 10F   | Failed                                  | Neither pre-registered rule passed every validation gate                        |
| 10G   | Closeout completed                      | The macro branch was closed without promotion                                   |
| 10H   | Checkpoint audit completed              | README, configuration, reports, and closeout state reconciled                   |

Final Phase 10 interpretation:

> Macro, rates, and inflation data were operationally feasible and diagnostically informative, but they did not produce a validated strategy extension.

The branch established several important lessons:

* release dates and data availability matter more than observation dates;
* revision-prone series require explicit vintage or lagging policies;
* ex-post macro labels must not be treated as live inputs;
* diagnostic regime relationships are not automatically tradable rules;
* higher headline CAGR is insufficient when drawdown and robustness deteriorate;
* interesting failed hypotheses must not be softened or retuned after the result;
* branch failure should preserve, rather than silently mutate, the existing strategy hierarchy.

The correct conclusion was therefore:

> Phase 10 improved the project’s macro-data discipline and explanatory framework, but it did not improve the final ETF candidate.

---

# Phase 11: Regime-Scoring Architecture

Phase 11 reviewed the project’s decision architecture after both the technical and macro extension branches produced useful diagnostic evidence but failed as pre-registered rule overlays.

The central architectural conclusion was:

> The project should not continue stacking simple if/then rules onto the existing ETF candidate. Richer information requires a more structured decision layer before it can be evaluated responsibly.

Phase 11 therefore shifted from strategy testing to architecture design.

It did **not** create:

* a calculated regime score;
* numeric score weights;
* an allocation signal;
* a trading rule;
* a backtest;
* a predictive model;
* new data ingestion;
* a promoted candidate.

The sequence was:

```text
Phase 11A: richer-information architecture review
Phase 11B: regime-scoring architecture specification
Phase 11C: regime-scoring rulebook specification
Phase 11D: diagnostic-panel design
Phase 11E: diagnostic-panel template implementation audit
Phase 11F: diagnostic-panel content audit
Phase 11G: final Phase 11 closeout
```

The branch separated architecture from implementation:

1. select an appropriate future decision structure;
2. define component families and boundaries;
3. define the rulebook grammar;
4. define report schemas;
5. create schema-compliant templates;
6. audit template content;
7. close the branch before any empirical score was calculated.

The final Phase 11 conclusion was:

> A regime-scoring architecture and diagnostic-panel framework were prepared, but no empirical regime score, score weight, signal, allocation rule, model, strategy test, new data ingestion, candidate promotion, or final-candidate change existed.

---

## Phase 11A: Architecture Review for Richer Information Layers

Phase 11A reviewed the next research architecture after the technical-indicator and macro/rates/inflation branches both failed as pre-registered rule overlays.

This was not a new strategy test.

It did not create:

* a new indicator rule;
* a macro retry;
* sentiment ingestion;
* fundamental ingestion;
* a model;
* a backtest;
* an allocation rule;
* a promoted candidate.

### Summary

| Metric                               |                                                 Result |
| ------------------------------------ | -----------------------------------------------------: |
| Review role                          | Architecture review for richer information layers only |
| Phase branch                         |                           Phase 11 architecture review |
| Prior branch count                   |                                                      2 |
| Failed rule-extension count          |                                                      2 |
| Closed-without-promotion count       |                                                      2 |
| Architecture candidate count         |                                                      6 |
| Simple overlay rejected as next step |                                                   True |
| Preferred architecture               |                              `A2_regime_scoring_layer` |
| Recommended next phase               |                                              Phase 11B |
| Next step is spec-only               |                                                   True |
| Strategy test allowed next           |                                                  False |

### Architecture Candidates

| Architecture                             | Immediate Next-Step Role                   |
| ---------------------------------------- | ------------------------------------------ |
| `A1_continue_simple_rule_overlays`       | Rejected as immediate next step            |
| `A2_regime_scoring_layer`                | Preferred next architecture-spec candidate |
| `A3_probabilistic_allocation_confidence` | Secondary architecture candidate           |
| `A4_explainable_ensemble_decision_layer` | Long-term candidate, not next              |
| `A5_separate_successor_architecture`     | Architecture-review candidate              |
| `A6_freeze_spy_overlay_arc`              | Valid pause option                         |

### Gate Result

| Gate                                                           | Result |
| -------------------------------------------------------------- | ------ |
| Prior rule-extension failures are documented                   | Passed |
| Architecture candidates are documented                         | Passed |
| Simple overlay continuation is rejected as immediate next step | Passed |
| Preferred architecture is identified                           | Passed |
| Next step is spec-only                                         | Passed |
| No new indicator rule is allowed                               | Passed |
| No macro rule retry is allowed                                 | Passed |
| No sentiment ingestion is allowed                              | Passed |
| No fundamental ingestion is allowed                            | Passed |
| No model training is allowed                                   | Passed |
| No strategy backtest is allowed                                | Passed |
| No candidate promotion is allowed                              | Passed |
| Review role is correct                                         | Passed |

Phase 11A verdict:

> Phase 11A completed the richer-information architecture review.

Correct interpretation:

> After failed technical and macro rule-extension branches, the project should not immediately continue with more simple if/then overlays. The next step should be a design-only regime-scoring architecture spec.

---

## Phase 11B: Regime-Scoring Architecture Spec

Phase 11B defined the design boundaries for a future regime-scoring layer.

This was not a score implementation.

It did not:

* calculate scores;
* assign weights;
* create signals;
* create allocation rules;
* run strategy backtests;
* ingest new data;
* train models;
* promote a candidate.

### Summary

| Metric                               |                                Result |
| ------------------------------------ | ------------------------------------: |
| Spec role                            | Regime-scoring architecture spec only |
| Phase branch                         |          Phase 11 architecture review |
| Source architecture decision present |                                  True |
| Simple overlay rejected              |                                  True |
| Scoring principle count              |                                     6 |
| Required scoring principle count     |                                     6 |
| Component family count               |                                     5 |
| Validation-risk context present      |                                  True |
| Future data families blocked         |                                  True |
| Score states non-trading             |                                  True |
| Future validation requirement count  |                                     6 |
| Strategy promotion                   |                                 False |
| Candidate promotion                  |                                 False |

### Component Registry

| Component                    | Family                    | Role                         | Phase 11C Spec Allowed |
| ---------------------------- | ------------------------- | ---------------------------- | ---------------------- |
| `technical_regime_context`   | Technical                 | Diagnostic candidate         | True                   |
| `macro_regime_context`       | Macro / rates / inflation | Diagnostic candidate         | True                   |
| `validation_risk_context`    | Validation risk           | Required control layer       | True                   |
| `future_fundamental_context` | Fundamental / valuation   | Future candidate, not active | False                  |
| `future_sentiment_context`   | Sentiment / narrative     | Future candidate, not active | False                  |

### Gate Result

| Gate                                          | Result |
| --------------------------------------------- | ------ |
| Source architecture decision is documented    | Passed |
| Scoring principles are documented             | Passed |
| Component families are documented             | Passed |
| Validation-risk context is included           | Passed |
| Future unaudited data families are blocked    | Passed |
| Score states are non-trading concepts         | Passed |
| Future validation requirements are documented | Passed |
| Phase 11C boundary is spec-only               | Passed |
| No score calculation is allowed               | Passed |
| No score weights are allowed                  | Passed |
| No signal creation is allowed                 | Passed |
| No allocation rule creation is allowed        | Passed |
| No strategy backtest is allowed               | Passed |
| No model training is allowed                  | Passed |
| No new data ingestion is allowed              | Passed |
| No candidate promotion is allowed             | Passed |
| Spec role is correct                          | Passed |

Phase 11B verdict:

> Phase 11B completed the regime-scoring architecture spec.

Correct interpretation:

> Phase 11B defined a design-only regime-scoring architecture. It did not calculate scores, create weights, create signals, run backtests, ingest new data, train models, or promote a candidate.

---

## Phase 11C: Regime-Scoring Rulebook Spec

Phase 11C defined the future regime-scoring rulebook grammar after Phase 11B established the architecture.

This was not a score implementation.

It did not calculate scores, assign empirical weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Summary

| Metric                             |                            Result |
| ---------------------------------- | --------------------------------: |
| Spec role                          | Regime-scoring rulebook spec only |
| Source phase                       |                         Phase 11B |
| Component count                    |                                 5 |
| Active required components present |                              True |
| Future unaudited families blocked  |                              True |
| Conceptual direction count         |                                 6 |
| Conceptual directions non-trading  |                              True |
| Missingness rule count             |                                 5 |
| Weighting principle count          |                                 5 |
| Score states non-trading           |                              True |
| Audit output count                 |                                 5 |
| Future validation gate count       |                                 6 |
| Strategy promotion                 |                             False |
| Candidate promotion                |                             False |

### Component Rulebook

| Component                    | Family                    | Role                        | Status          | Conceptual Directions |
| ---------------------------- | ------------------------- | --------------------------- | --------------- | --------------------: |
| `technical_regime_context`   | Technical                 | Active conceptual component | Conceptual only |                     2 |
| `macro_regime_context`       | Macro / rates / inflation | Active conceptual component | Conceptual only |                     2 |
| `validation_risk_context`    | Validation risk           | Required control component  | Conceptual only |                     2 |
| `future_fundamental_context` | Fundamental / valuation   | Blocked future component    | Blocked         |                     0 |
| `future_sentiment_context`   | Sentiment / narrative     | Blocked future component    | Blocked         |                     0 |

### Gate Result

| Gate                                                    | Result |
| ------------------------------------------------------- | ------ |
| Source architecture is documented                       | Passed |
| Component rulebook is documented                        | Passed |
| Technical, macro, and validation components are present | Passed |
| Future unaudited families are blocked                   | Passed |
| Conceptual directions are documented and non-trading    | Passed |
| Missingness rules are documented                        | Passed |
| Weighting principles are documented                     | Passed |
| Score states are non-trading concepts                   | Passed |
| Audit output spec is documented                         | Passed |
| Future validation gates are documented                  | Passed |
| Phase 11D boundary is design-only                       | Passed |
| No score calculation is allowed                         | Passed |
| No numeric score weights are allowed                    | Passed |
| No empirical return weights are allowed                 | Passed |
| No signal creation is allowed                           | Passed |
| No allocation rule creation is allowed                  | Passed |
| No strategy backtest is allowed                         | Passed |
| No model training is allowed                            | Passed |
| No new data ingestion is allowed                        | Passed |
| No candidate promotion is allowed                       | Passed |
| Spec role is correct                                    | Passed |

Phase 11C verdict:

> Phase 11C completed the regime-scoring rulebook spec.

Correct interpretation:

> Phase 11C defined the regime-scoring rulebook only. It documented conceptual component directions, missingness rules, weighting principles, audit outputs, and future validation gates, but did not calculate a score, create a signal, test a strategy, train a model, ingest new data, or promote a candidate.

---

## Phase 11D: Regime-Scoring Diagnostic Panel Design

Phase 11D designed the future diagnostic-panel structure for the regime-scoring architecture.

This was not a score implementation.

It did not calculate scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Summary

| Metric                            |                                      Result |
| --------------------------------- | ------------------------------------------: |
| Design role                       | Regime-scoring diagnostic-panel design only |
| Source phase                      |                                   Phase 11C |
| Source rulebook present           |                                        True |
| Panel section count               |                                           6 |
| Required column rows              |                                          42 |
| Required columns present          |                                        True |
| Component availability rows       |                                           5 |
| Conceptual direction rows         |                                           3 |
| Conceptual directions non-trading |                                        True |
| Missingness policy count          |                                           5 |
| Weighting policy count            |                                           5 |
| Weighting non-empirical           |                                        True |
| Blocked family count              |                                           2 |
| Blocked families clean            |                                        True |
| All panels avoid returns usage    |                                        True |
| All panels are non-signal panels  |                                        True |
| Strategy promotion                |                                       False |
| Candidate promotion               |                                       False |

### Diagnostic Panel Sections

| Panel                          | Report                          | Uses Returns | Creates Signal | Required Columns |
| ------------------------------ | ------------------------------- | -----------: | -------------: | ---------------: |
| `component_availability_panel` | `component_availability_report` |        False |          False |                8 |
| `conceptual_direction_panel`   | `component_direction_report`    |        False |          False |                8 |
| `missingness_panel`            | `missingness_report`            |        False |          False |                8 |
| `weighting_policy_panel`       | `weighting_policy_report`       |        False |          False |                7 |
| `blocked_family_panel`         | `blocked_family_report`         |        False |          False |                6 |
| `boundary_panel`               | `boundary_report`               |        False |          False |                5 |

### Gate Result

| Gate                                            | Result |
| ----------------------------------------------- | ------ |
| Source rulebook is documented                   | Passed |
| Diagnostic panel sections are documented        | Passed |
| Required columns are documented                 | Passed |
| Component availability spec is documented       | Passed |
| Conceptual direction spec is documented         | Passed |
| Missingness policy spec is documented           | Passed |
| Weighting policy spec is documented             | Passed |
| Blocked family spec is documented               | Passed |
| All panels are non-signal panels                | Passed |
| All panels avoid returns usage                  | Passed |
| Phase 11E boundary is implementation-audit only | Passed |
| No score calculation is allowed                 | Passed |
| No numeric score weights are allowed            | Passed |
| No empirical return weights are allowed         | Passed |
| No signal creation is allowed                   | Passed |
| No allocation rule creation is allowed          | Passed |
| No strategy backtest is allowed                 | Passed |
| No model training is allowed                    | Passed |
| No new data ingestion is allowed                | Passed |
| No candidate promotion is allowed               | Passed |
| Design role is correct                          | Passed |

Phase 11D verdict:

> Phase 11D completed the regime-scoring diagnostic-panel design.

Correct interpretation:

> Phase 11D designed the diagnostic-panel structure and report schemas for future regime-scoring work. It did not implement a score, assign weights, create a signal, run a strategy test, ingest new data, train a model, or promote a candidate.

---

## Phase 11E: Regime-Scoring Diagnostic-Panel Template Implementation Audit

Phase 11E created schema-compliant diagnostic-panel templates from the Phase 11D design.

This was not a score implementation.

It did not calculate regime scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Summary

| Metric                              |                                                             Result |
| ----------------------------------- | -----------------------------------------------------------------: |
| Implementation role                 | Regime-scoring diagnostic-panel template implementation audit only |
| Source phase                        |                                                          Phase 11D |
| Source design reports present       |                                                               True |
| Template report count               |                                                                  6 |
| Template inventory rows             |                                                                  6 |
| Schema compliance passed            |                                                               True |
| Component availability rows         |                                                                  5 |
| Direction rows                      |                                                                  9 |
| Missingness rows                    |                                                                  5 |
| Weighting-policy rows               |                                                                  5 |
| Blocked-family rows                 |                                                                  2 |
| Boundary rows                       |                                                                  9 |
| Direction non-signal                |                                                               True |
| Missingness blocks return inference |                                                               True |
| Weighting non-empirical             |                                                               True |
| Blocked families clean              |                                                               True |
| Boundary report passed              |                                                               True |
| Strategy promotion                  |                                                              False |
| Candidate promotion                 |                                                              False |

### Template Inventory

| Report                          | Rows | Columns |
| ------------------------------- | ---: | ------: |
| `component_availability_report` |    5 |       8 |
| `component_direction_report`    |    9 |       8 |
| `missingness_report`            |    5 |       8 |
| `weighting_policy_report`       |    5 |       7 |
| `blocked_family_report`         |    2 |       6 |
| `boundary_report`               |    9 |       5 |

### Schema Compliance

| Report                          | Expected Columns | Actual Columns | Missing Columns | Rows | Result |
| ------------------------------- | ---------------: | -------------: | --------------: | ---: | ------ |
| `component_availability_report` |                8 |              8 |               0 |    5 | Passed |
| `component_direction_report`    |                8 |              8 |               0 |    9 | Passed |
| `missingness_report`            |                8 |              8 |               0 |    5 | Passed |
| `weighting_policy_report`       |                7 |              7 |               0 |    5 | Passed |
| `blocked_family_report`         |                6 |              6 |               0 |    2 | Passed |
| `boundary_report`               |                5 |              5 |               0 |    9 | Passed |

### Gate Result

| Gate                                       | Result |
| ------------------------------------------ | ------ |
| Source design reports are present          | Passed |
| Template reports are generated             | Passed |
| Template schemas are compliant             | Passed |
| Component availability template rows exist | Passed |
| Direction template rows exist              | Passed |
| Missingness template rows exist            | Passed |
| Weighting-policy template rows exist       | Passed |
| Blocked-family template rows exist         | Passed |
| Boundary template rows exist               | Passed |
| Templates are non-signal                   | Passed |
| Templates do not use returns               | Passed |
| Weighting templates are non-empirical      | Passed |
| Blocked-family templates are clean         | Passed |
| Boundary report passes                     | Passed |
| Phase 11F boundary is content-audit only   | Passed |
| No score calculation is allowed            | Passed |
| No numeric score weights are allowed       | Passed |
| No empirical return weights are allowed    | Passed |
| No signal creation is allowed              | Passed |
| No allocation rule creation is allowed     | Passed |
| No strategy backtest is allowed            | Passed |
| No model training is allowed               | Passed |
| No new data ingestion is allowed           | Passed |
| No candidate promotion is allowed          | Passed |
| Implementation role is correct             | Passed |

Phase 11E verdict:

> Phase 11E completed the regime-scoring diagnostic-panel template implementation audit.

Correct interpretation:

> Phase 11E created schema-compliant diagnostic-panel templates and verified required columns, blocked-family rows, boundary rows, and non-signal/non-return constraints. It did not calculate scores, assign weights, create signals, ingest new data, run strategy tests, train models, or promote a candidate.

---

## Phase 11F: Regime-Scoring Diagnostic-Panel Content Audit

Phase 11F audited the content of the diagnostic-panel templates created in Phase 11E.

This was not a score implementation.

It did not calculate regime scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Summary

| Metric                        |                                             Result |
| ----------------------------- | -------------------------------------------------: |
| Audit role                    | Regime-scoring diagnostic-panel content audit only |
| Source phase                  |                                          Phase 11E |
| Source templates present      |                                               True |
| Source template count         |                                                  6 |
| Phase 11E result passed       |                                               True |
| Component content passed      |                                               True |
| Direction content passed      |                                               True |
| Missingness content passed    |                                               True |
| Weighting content passed      |                                               True |
| Blocked-family content passed |                                               True |
| Boundary content passed       |                                               True |
| Strategy promotion            |                                              False |
| Candidate promotion           |                                              False |

### Content Checks

| Check Area                                  | Result |
| ------------------------------------------- | ------ |
| Expected components present                 | Passed |
| Blocked components flagged                  | Passed |
| Active components not blocked               | Passed |
| Technical regime directions complete        | Passed |
| Macro regime directions complete            | Passed |
| Validation-risk directions complete         | Passed |
| Direction rows non-signal/non-trading       | Passed |
| Missingness blocks return inference         | Passed |
| Missingness blocks silent fill              | Passed |
| Numeric weights blocked                     | Passed |
| Empirical return weights blocked            | Passed |
| Cutoff search blocked                       | Passed |
| Pre-registration required                   | Passed |
| Blocked families present                    | Passed |
| Blocked families not usable currently       | Passed |
| Blocked families cannot be score components | Passed |
| Boundary items present                      | Passed |
| Boundary allowed values all false           | Passed |
| Boundary rows passed                        | Passed |

### Gate Result

| Gate                                    | Result |
| --------------------------------------- | ------ |
| Source templates are present            | Passed |
| Phase 11E template audit remains passed | Passed |
| Schema compliance remains passed        | Passed |
| Component content is consistent         | Passed |
| Direction content is consistent         | Passed |
| Missingness content is consistent       | Passed |
| Weighting content is consistent         | Passed |
| Blocked-family content is consistent    | Passed |
| Boundary content is consistent          | Passed |
| Phase 11G boundary is closeout-only     | Passed |
| No score calculation is allowed         | Passed |
| No numeric score weights are allowed    | Passed |
| No empirical return weights are allowed | Passed |
| No signal creation is allowed           | Passed |
| No allocation rule creation is allowed  | Passed |
| No strategy backtest is allowed         | Passed |
| No model training is allowed            | Passed |
| No new data ingestion is allowed        | Passed |
| No candidate promotion is allowed       | Passed |
| Audit role is correct                   | Passed |

Phase 11F verdict:

> Phase 11F completed the regime-scoring diagnostic-panel content audit.

Correct interpretation:

> Phase 11F confirmed that the diagnostic-panel template content was internally consistent with the Phase 11E templates and Phase 11D design. No regime score, score weight, signal, allocation rule, strategy test, model, new data ingestion, or candidate promotion exists.

---

## Phase 11G: Final Phase 11 Regime-Scoring Closeout

Phase 11G closed the Phase 11 regime-scoring architecture and diagnostic-panel branch.

This was not a score implementation.

It did not calculate regime scores, assign weights, create signals, create allocation rules, run strategy backtests, ingest new data, train models, or promote a candidate.

### Summary

| Metric                              |                                                                                      Result |
| ----------------------------------- | ------------------------------------------------------------------------------------------: |
| Audit role                          |                                Final Phase 11 regime-scoring closeout/checkpoint audit only |
| Checkpoint status                   | Phase 11 closed — regime-scoring architecture and diagnostic panel prepared without scoring |
| Next allowed step                   |                                      Phase 12A score-calculation pre-registration spec only |
| Report prefixes present             |                                                                                        True |
| Markdown reports present            |                                                                                        True |
| Config flags clean for closeout run |                                                                                        True |
| Phase conclusions passed            |                                                                                        True |
| Phase gate reports passed           |                                                                                        True |
| Boundary reports passed             |                                                                                        True |
| Branch closure clean                |                                                                                        True |
| Strategy promotion                  |                                                                                       False |
| Candidate promotion                 |                                                                                       False |
| Final candidate changed             |                                                                                       False |

### Closure Claims

| Claim                   | Result |
| ----------------------- | ------ |
| Regime score exists     | False  |
| Signal exists           | False  |
| Allocation rule exists  | False  |
| Strategy test exists    | False  |
| Model exists            | False  |
| New data ingested       | False  |
| Candidate promoted      | False  |
| Final candidate changed | False  |

### Gate Result

| Gate                                                   | Result |
| ------------------------------------------------------ | ------ |
| Expected Phase 11 report prefixes are present          | Passed |
| Expected Phase 11 markdown reports are present         | Passed |
| Config flags are clean for closeout run                | Passed |
| Phase 11 conclusions passed                            | Passed |
| Phase 11 gate reports passed                           | Passed |
| Phase 11F is locked as passed                          | Passed |
| Boundary reports passed                                | Passed |
| No score, signal, model, strategy, or promotion exists | Passed |
| Phase 12A boundary is pre-registration-spec only       | Passed |
| No score calculation is allowed                        | Passed |
| No numeric score weights are allowed                   | Passed |
| No empirical return weights are allowed                | Passed |
| No signal creation is allowed                          | Passed |
| No allocation rule creation is allowed                 | Passed |
| No strategy backtest is allowed                        | Passed |
| No model training is allowed                           | Passed |
| No new data ingestion is allowed                       | Passed |
| No candidate promotion is allowed                      | Passed |
| Audit role is correct                                  | Passed |

Phase 11G verdict:

> Phase 11G completed the final Phase 11 regime-scoring checkpoint.

Correct interpretation:

> Phase 11 closed cleanly. The project prepared a regime-scoring architecture, rulebook, diagnostic-panel design, schema-compliant templates, and content audits, but no regime score, score weights, signal, allocation rule, strategy test, model, new data ingestion, candidate promotion, or final-candidate change exists.

---

## Phase 11 Final Verdict

| Phase | Result                                  | Interpretation                                                                 |
| ----- | --------------------------------------- | ------------------------------------------------------------------------------ |
| 11A   | Architecture review completed           | Repeated simple overlays were rejected as the immediate next design            |
| 11B   | Architecture specification completed    | A conceptual regime-scoring layer was defined                                  |
| 11C   | Rulebook specification completed        | Component grammar, missingness rules, and weighting boundaries were documented |
| 11D   | Diagnostic-panel design completed       | Report structures and required columns were defined                            |
| 11E   | Template implementation audit completed | Schema-compliant diagnostic templates were generated                           |
| 11F   | Content audit completed                 | Template content and boundaries passed consistency checks                      |
| 11G   | Closeout completed                      | The branch closed without empirical scoring, testing, or promotion             |

Final Phase 11 interpretation:

> Phase 11 created design infrastructure for a future diagnostic regime score but deliberately stopped before calculating or testing one.

The branch established several principles:

* technical and macro context should be represented as components rather than isolated rule overlays;
* validation risk must be part of the architecture rather than an afterthought;
* unaudited fundamental and sentiment families must remain blocked;
* missing data must not be silently filled;
* empirical return-based weights must not be introduced without pre-registration;
* diagnostic states must remain separate from trading signals;
* architecture design does not constitute trading evidence;
* schema and boundary audits should precede any empirical implementation.

The correct conclusion was:

> Phase 11 improved the project’s decision architecture, not its historical performance.

A future score implementation required a separate, explicitly pre-registered phase with fixed components, fixed weighting rules, point-in-time inputs, missingness controls, and a clear non-trading boundary.

---

# Phase 12: Diagnostic Regime Score

Phase 12 implemented, audited, interpreted, and closed the project’s first categorical diagnostic regime score.

The purpose was not to create a new trading system. It was to test whether the technical, macroeconomic, and validation-risk evidence developed in earlier phases could be combined under a pre-registered, non-empirical decision grammar.

Phase 12 therefore maintained a strict boundary between:

* diagnostic context;
* trading signals;
* allocation rules;
* predictive models;
* strategy backtests.

It did **not** create:

* a trading signal;
* an allocation rule;
* a strategy backtest;
* empirical or return-fitted weights;
* model training;
* new data ingestion;
* candidate promotion;
* a change to the final ETF candidate.

The sequence was:

```text
Phase 12A: score-calculation pre-registration specification
Phase 12B: score-calculation readiness audit
Phase 12C: categorical diagnostic-score calculation
Phase 12D: score-distribution and content audit
Phase 12E: score interpretation and closeout audit
Phase 12F: final Phase 12 checkpoint audit
```

The resulting score combined three categorical components:

```text
technical_regime_context
macro_regime_context
validation_risk_context
```

Technical and macro context were neutral, while validation risk was fragile. Under the locked aggregation grammar, this produced a final diagnostic state of:

```text
fragile
```

The final Phase 12 conclusion was:

> The available technical and macro evidence was not sufficiently supportive to overcome the project’s fragile validation-risk context. The resulting categorical score was research context only and did not constitute a trading signal.

---

## Phase 12A: Score-Calculation Pre-Registration Specification

Phase 12A locked the future diagnostic score-calculation design before any score was calculated.

This was not a score-calculation phase.

It locked:

* eligible components;
* blocked components;
* formula grammar;
* non-return weighting policy;
* missingness policy;
* score-state interpretation;
* validation gates;
* failure conditions.

No scores, signals, backtests, models, new data ingestion, candidate promotion, or final-candidate changes were created.

### Phase 12A Verdict

> Phase 12A completed the score-calculation pre-registration spec.

Correct interpretation:

> The score-calculation grammar was locked before calculation. This protected the project from converting diagnostic evidence into an after-the-fact fitted signal.

---

## Phase 12B: Score-Calculation Readiness Audit

Phase 12B verified that Phase 12A was complete and locked before any diagnostic score calculation.

This was not a score-calculation phase.

### Summary

| Metric                              |                                 Result |
| ----------------------------------- | -------------------------------------: |
| Audit role                          | Score-calculation readiness audit only |
| Source phase                        |                              Phase 12A |
| Phase 12A reports present           |                                   True |
| Phase 12A result passed             |                                   True |
| Config flags clean for combined run |                                   True |
| Readiness claims locked             |                                   True |
| Strategy promotion                  |                                  False |
| Candidate promotion                 |                                  False |

### Readiness Claims

| Claim                      | Result |
| -------------------------- | ------ |
| Pre-registration exists    | Passed |
| Eligible components locked | Passed |
| Blocked components locked  | Passed |
| Formula structure locked   | Passed |
| Weighting policy locked    | Passed |
| Missingness policy locked  | Passed |
| Failure conditions locked  | Passed |
| Score calculated           | False  |
| Signal created             | False  |
| Backtest run               | False  |
| Model trained              | False  |
| New data ingested          | False  |
| Candidate promoted         | False  |

### Phase 12C Boundary

| Boundary                        | Result                            |
| ------------------------------- | --------------------------------- |
| Allowed next step               | Diagnostic score calculation only |
| May calculate diagnostic scores | True                              |
| May assign empirical weights    | False                             |
| May create signal               | False                             |
| May test strategy               | False                             |
| May train model                 | False                             |
| May ingest new data             | False                             |
| May promote candidate           | False                             |

Phase 12B verdict:

> Phase 12B completed the score-calculation readiness audit.

Correct interpretation:

> Phase 12B verified that the score-calculation pre-registration was complete and locked. Phase 12C could calculate diagnostic scores only.

---

## Phase 12C: Diagnostic Score Calculation

Phase 12C calculated the first categorical diagnostic regime score using the pre-registered Phase 12A grammar.

This was not a trading-signal phase.

It did not create an allocation rule, run a strategy backtest, assign empirical weights, ingest new data, train a model, promote a candidate, or change the final candidate.

### Summary

| Metric                        |                            Result |
| ----------------------------- | --------------------------------: |
| Calculation role              | Diagnostic score calculation only |
| Source phase                  |                         Phase 12B |
| Source reports present        |                              True |
| Phase 12B result passed       |                              True |
| Component count               |                                 3 |
| Component states allowed      |                              True |
| Aggregate score allowed       |                              True |
| Blocked components excluded   |                              True |
| Existing project sources only |                              True |
| Component rows non-signal     |                              True |
| No empirical weights          |                              True |
| No numeric weights            |                              True |
| No returns used               |                              True |
| No signal/backtest/promotion  |                              True |
| Strategy promotion            |                             False |
| Candidate promotion           |                             False |

### Diagnostic Score Inputs

| Component                  | Diagnostic State | Role                     |
| -------------------------- | ---------------- | ------------------------ |
| `technical_regime_context` | Neutral          | Eligible component state |
| `macro_regime_context`     | Neutral          | Eligible component state |
| `validation_risk_context`  | Fragile          | Eligible control state   |

### Aggregate Score

| Item                         | Result                                              |
| ---------------------------- | --------------------------------------------------- |
| Score ID                     | `pre_registered_three_component_regime_score`       |
| Calculation scope            | Static branch-level diagnostic score                |
| Aggregation method           | Categorical equal vote with validation-risk control |
| Supportive components        | 0                                                   |
| Neutral components           | 2                                                   |
| Fragile components           | 1                                                   |
| Raw vote state               | Neutral                                             |
| Final diagnostic score state | Fragile                                             |
| Validation-risk override     | Fragile validation risk without supportive majority |
| Empirical weights allowed    | False                                               |
| Numeric weights allowed      | False                                               |
| Returns used                 | False                                               |
| Trading signal created       | False                                               |
| Strategy backtest run        | False                                               |
| Candidate promoted           | False                                               |

Phase 12C verdict:

> Phase 12C completed the diagnostic score calculation.

Correct interpretation:

> Phase 12C calculated a categorical diagnostic regime score from the pre-registered grammar. The resulting score is diagnostic only, not a trading signal.

---

## Phase 12D: Diagnostic Score Distribution and Content Audit

Phase 12D audited the Phase 12C diagnostic score distribution and content quality.

This was not a trading-signal phase.

### Summary

| Metric                        |                                               Result |
| ----------------------------- | ---------------------------------------------------: |
| Audit role                    | Diagnostic score distribution and content audit only |
| Source phase                  |                                            Phase 12C |
| Phase 12C reports present     |                                                 True |
| Phase 12C result passed       |                                                 True |
| Distribution check passed     |                                                 True |
| Forbidden-column check passed |                                                 True |
| Strategy promotion            |                                                False |
| Candidate promotion           |                                                False |

### Forbidden-Column Audit

| Frame                   | Forbidden Group          | Result |
| ----------------------- | ------------------------ | ------ |
| `component_state_panel` | Numeric score columns    | Passed |
| `component_state_panel` | Signal columns           | Passed |
| `component_state_panel` | Backtest columns         | Passed |
| `component_state_panel` | Empirical weight columns | Passed |
| `aggregate_score`       | Numeric score columns    | Passed |
| `aggregate_score`       | Signal columns           | Passed |
| `aggregate_score`       | Backtest columns         | Passed |
| `aggregate_score`       | Empirical weight columns | Passed |

### Gate Result

| Gate                                                    | Result |
| ------------------------------------------------------- | ------ |
| Phase 12C reports are present                           | Passed |
| Phase 12C conclusion passed                             | Passed |
| Score distribution and aggregate content are valid      | Passed |
| No forbidden score/signal/backtest/weight columns exist | Passed |
| Phase 12E boundary is interpretation-audit only         | Passed |
| Audit role is correct                                   | Passed |

Phase 12D verdict:

> Phase 12D completed the diagnostic score distribution audit.

Correct interpretation:

> Phase 12D confirmed that the Phase 12C diagnostic score was categorical, content-consistent, and bounded. No numeric trading score, signal, allocation rule, strategy backtest, empirical weight, model, new data ingestion, candidate promotion, or final-candidate change exists.

---

## Phase 12E: Diagnostic Score Interpretation and Closeout Audit

Phase 12E interpreted the Phase 12C diagnostic score and closed the score-interpretation branch.

This was not a trading-signal phase.

### Summary

| Metric                                         |                                                  Result |
| ---------------------------------------------- | ------------------------------------------------------: |
| Audit role                                     | Diagnostic score interpretation and closeout audit only |
| Source phase                                   |                                               Phase 12D |
| Source score reports present                   |                                                    True |
| Phase 12D result passed                        |                                                    True |
| Aggregate state                                |                                                 Fragile |
| Aggregate state allowed                        |                                                    True |
| Aggregate state matches expected fragile state |                                                    True |
| Interpretation created                         |                                                    True |
| Interpretation diagnostic-only                 |                                                    True |
| Closeout claims locked                         |                                                    True |
| Strategy promotion                             |                                                   False |
| Candidate promotion                            |                                                   False |
| Final candidate changed                        |                                                   False |

### Interpretation

| Item                   | Result                                                                                                                                                               |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Diagnostic score state | Fragile                                                                                                                                                              |
| Interpretation role    | Diagnostic-only research interpretation                                                                                                                              |
| Interpretation         | Technical and macro evidence were neutral, while validation-risk context was fragile.                                                                                |
| Permitted use          | Research context and caveat stack only                                                                                                                               |
| Prohibited use         | Trading signal, allocation rule, strategy backtest, empirical weighting, model training, live-trading recommendation, candidate promotion, or final-candidate change |

### Closeout Claims

| Claim                        | Result |
| ---------------------------- | ------ |
| Diagnostic score interpreted | True   |
| Score-to-signal created      | False  |
| Allocation rule created      | False  |
| Strategy backtest run        | False  |
| Empirical weights assigned   | False  |
| Model trained                | False  |
| New data ingested            | False  |
| Candidate promoted           | False  |
| Final candidate changed      | False  |

Phase 12E verdict:

> Phase 12E completed the diagnostic score interpretation closeout.

Correct interpretation:

> Phase 12E interpreted the fragile diagnostic score as research-only context. It did not convert the score into a trading signal, allocation rule, strategy test, model, empirical weighting system, candidate promotion, or final-candidate change.

---

## Phase 12F: Final Phase 12 Diagnostic Score Checkpoint Audit

Phase 12F closed the Phase 12 diagnostic regime-score branch.

This was not a trading-signal phase.

### Summary

| Metric                                |                                                                                  Result |
| ------------------------------------- | --------------------------------------------------------------------------------------: |
| Audit role                            |                                   Final Phase 12 diagnostic score checkpoint audit only |
| Checkpoint status                     | Phase 12 closed — diagnostic regime score calculated, audited, interpreted, and bounded |
| Next allowed step                     |                  Separate future score-to-signal pre-registration spec only, if pursued |
| Report prefixes present               |                                                                                    True |
| Markdown reports present              |                                                                                    True |
| Config flags clean for checkpoint run |                                                                                    True |
| Phase conclusions passed              |                                                                                    True |
| Phase gate reports passed             |                                                                                    True |
| Branch closure claims locked          |                                                                                    True |
| Strategy promotion                    |                                                                                   False |
| Candidate promotion                   |                                                                                   False |
| Final candidate changed               |                                                                                   False |

### Branch Closure Claims

| Claim                        | Result |
| ---------------------------- | ------ |
| Diagnostic score exists      | True   |
| Diagnostic score interpreted | True   |
| Score-to-signal created      | False  |
| Allocation rule created      | False  |
| Strategy backtest run        | False  |
| Empirical weights assigned   | False  |
| Model trained                | False  |
| New data ingested            | False  |
| Candidate promoted           | False  |
| Final candidate changed      | False  |

### Future Boundary

| Boundary                      | Result                                                          |
| ----------------------------- | --------------------------------------------------------------- |
| Allowed next step             | Separate score-to-signal pre-registration spec only, if pursued |
| May define signal spec        | True                                                            |
| May create signal immediately | False                                                           |
| May test strategy             | False                                                           |
| May assign empirical weights  | False                                                           |
| May train model               | False                                                           |
| May ingest new data           | False                                                           |
| May promote candidate         | False                                                           |
| May change final candidate    | False                                                           |

Phase 12F verdict:

> Phase 12F completed the final Phase 12 diagnostic score checkpoint.

Correct interpretation:

> Phase 12 closed cleanly. The branch calculated, audited, interpreted, and bounded a fragile diagnostic regime score. No score-to-signal conversion, allocation rule, backtest, empirical weighting, model, new data ingestion, candidate promotion, or final-candidate change exists.

---

## Phase 12 Final Verdict

| Phase | Result                                   | Interpretation                                                                                             |
| ----- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 12A   | Pre-registration completed               | Eligible components, aggregation grammar, missingness rules, and boundaries were locked before calculation |
| 12B   | Readiness audit completed                | Calculation was allowed only after confirming the pre-registration was complete                            |
| 12C   | Diagnostic score calculated              | The final categorical diagnostic state was `fragile`                                                       |
| 12D   | Distribution and content audit completed | The result remained categorical, bounded, and free from signal, backtest, and empirical-weight columns     |
| 12E   | Interpretation closeout completed        | The fragile state was interpreted as research-only context                                                 |
| 12F   | Final checkpoint completed               | The branch closed without signal conversion, testing, or promotion                                         |

Final Phase 12 interpretation:

> Phase 12 synthesised the existing ETF evidence into a fragile categorical diagnostic state under a pre-registered grammar.

The branch established several important principles:

* validation risk can override otherwise neutral component evidence;
* diagnostic states must remain separate from trading actions;
* categorical aggregation does not establish predictive power;
* no score should become a signal without a separate pre-registered conversion phase;
* architecture and audit discipline are not substitutes for out-of-sample trading evidence;
* a fragile result should narrow the project’s claims rather than trigger immediate rule modification.

The correct conclusion was:

> Phase 12 made the existing caveat stack explicit and closed the original SPY regime-switch research arc as a disciplined baseline framework. It did not create a new strategy.

---

# Phase 13: Multi-Factor Model Path and Paper-Trading Route Decision

Phase 13 transitioned the project from the frozen SPY regime-switch baseline towards its broader long-term objective:

> Build a disciplined decision system capable of incorporating technical, macroeconomic, fundamental, sentiment, and model-based information into long-term trading and investment research.

The phase pursued two connected objectives:

1. design and test the first governed multi-factor machine-learning path;
2. determine the fastest responsible route from historical research into paper-trading operations.

The phase began by freezing the original SPY research arc as reusable benchmark and validation infrastructure. It then introduced:

* feature-source contracts;
* timestamp and leakage policies;
* feature schemas;
* technical and macro feature calculation;
* target and split pre-registration;
* ML dataset construction;
* model-readiness and availability audits;
* bounded baseline-model testing;
* target and feature redesign diagnostics;
* a formal commercial continuation or termination decision.

The first technical-plus-macro ML branch did **not** produce evidence strong enough to justify promotion.

Macro-feature availability initially failed and had to be diagnosed separately. Even after the dataset and model pipeline were repaired and audited, the ML v1 branch failed its validation-to-holdout and commercial continuation requirements.

The project therefore did not force an ML result into production.

Instead, Phase 13 redirected the near-term operational path towards the strongest existing non-ML ETF candidate:

> **SPY 3D Confirmed Overlay + `deep_drawdown_guard` + `loose_relief`**

At the Phase 13 checkpoint, this became the preferred route for:

* reproducible visual backtesting;
* signal and exposure mapping;
* operational reconstruction;
* paper-trading readiness work.

The sequence was:

```text
13A–13B: freeze the SPY baseline arc and define the multi-factor roadmap
13C–13H: define feature-source contracts, schemas, and calculation rules
13I–13J: calculate and audit the technical and macro feature panels
13K–13N: prepare and audit the first ML dataset
13O–13R: diagnose and repair macro availability
13S–13W: pre-register, train, audit, and interpret baseline ML models
13X–13AF: checkpoint the failed ML branch and redesign targets/features
13AG–13AK: execute target-feature redesign diagnostics
13AM–13AN: pre-register and audit redesigned-model readiness
13AV–13AW: pause/kill ML v1 commercially and select the non-ML paper-readiness route
```

Phase 13 did not create:

* a promoted ML trading model;
* an approved live signal;
* real-money deployment;
* broker integration;
* a change to the validated ETF hierarchy.

The final Phase 13 conclusion was:

> The technical-plus-macro ML v1 branch was paused commercially after failing to establish reliable validation-to-holdout evidence. The fastest responsible operational route was the existing non-ML `loose_relief` ETF overlay, while the multi-factor architecture, contracts, datasets, and failure evidence were retained for future research.

---

## Phase 13A: Baseline SPY Research Arc Freeze / Transition Spec

Phase 13A froze the SPY regime-switch arc as a baseline research framework and opened the multi-factor model architecture path.

This phase did not convert the fragile diagnostic score into a signal, create an allocation rule, run a backtest, train a model, ingest new data, promote a candidate, or change the final candidate.

### Baseline Freeze

| Item                    | Result                                                                                    |
| ----------------------- | ----------------------------------------------------------------------------------------- |
| Baseline arc            | SPY regime-switch baseline research framework                                             |
| Baseline status         | Frozen as benchmark and validation infrastructure                                         |
| Final candidate         | Phase 6B/6C 3D + `deep_drawdown_guard` + `loose_relief`                                   |
| Final candidate role    | Best execution-realistic risk-adjusted candidate built so far, not final project endpoint |
| Diagnostic score state  | Fragile                                                                                   |
| Diagnostic score role   | Baseline research diagnostic, not signal                                                  |
| Hierarchy changed       | False                                                                                     |
| Candidate promoted      | False                                                                                     |
| Score-to-signal created | False                                                                                     |

### Transition Decision

| Item               | Decision                                                                                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Decision           | Open a new multi-factor model architecture branch                                                                                                        |
| Reason             | The baseline arc built a strong validation framework but did not build the intended technical + macro + fundamental + sentiment long-term decision model |
| Rejected next step | Direct score-to-signal conversion from fragile Phase 12 score                                                                                            |
| Accepted next step | Multi-factor model architecture roadmap spec                                                                                                             |
| Burden of proof    | Any future signal/backtest requires separate pre-registration and out-of-sample validation                                                               |

Phase 13A verdict:

> Phase 13A completed the baseline research arc freeze and transition spec.

Correct interpretation:

> The SPY regime-switch arc is frozen as a reusable baseline framework. It is not the final project endpoint. The project now moves toward the original multi-factor model goal through a separate architecture path.

---

## Phase 13B: Multi-Factor Long-Term Decision-Model Architecture Roadmap Specification

Phase 13B created the roadmap for the long-term multi-factor decision-model path.

This phase did not ingest features, create signals, create allocation rules, run strategy backtests, assign empirical weights, train models, deploy paper trading, promote a candidate, or change the final candidate.

### Feature Families

| Family                   | Status                                     | Role                                                                                              |
| ------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Technical                | Eligible for future feature-source audit   | Trend, momentum, volatility, breadth, drawdown, and market-structure context                      |
| Macro                    | Eligible with existing Phase 10 foundation | Rates, inflation, labour, curve, liquidity, and regime context                                    |
| Fundamental              | Not yet audited                            | Valuation, earnings, margins, profitability, quality, and index-level fundamentals                |
| Sentiment                | Not yet audited                            | Risk appetite, news tone, narrative pressure, positioning proxies, and crowding context           |
| Dissertation integration | Methodology candidate only                 | Optimisation, reporting, and governance methodology, not direct alpha unless separately justified |

### Architecture Candidates

| Architecture                                    | Role                                                              | Status                      |
| ----------------------------------------------- | ----------------------------------------------------------------- | --------------------------- |
| A1 interpretable regime score + exposure policy | Transparent baseline multi-factor decision layer                  | Roadmap only                |
| A2 walk-forward probabilistic classifier        | Probabilistic long-term exposure-confidence model                 | Future after data contracts |
| A3 ensemble decision layer                      | Blend interpretable score, probabilistic model, and risk controls | Future                      |
| A4 visual decision dashboard                    | Human-readable buy/sell/exposure decision system                  | Required reporting layer    |

### Paper-Trading Readiness Plan

| Gate                              | Requirement                                                                       |
| --------------------------------- | --------------------------------------------------------------------------------- |
| PTR1 feature contracts locked     | All feature families must have source, leakage, missingness, and timing contracts |
| PTR2 walk-forward results exist   | Walk-forward validation must exist before paper trading                           |
| PTR3 visual reports exist         | Visual decision and exposure reports must be generated reproducibly               |
| PTR4 no live-money claim          | Paper trading must remain non-production and non-financial-advice                 |
| PTR5 broker execution not assumed | Paper fills and live fills must not be treated as equivalent                      |
| PTR6 freeze model before paper    | The paper-trading model must be frozen before paper-trading starts                |

Phase 13B verdict:

> Phase 13B completed the multi-factor model architecture roadmap spec.

Correct interpretation:

> The project pivoted from the frozen SPY baseline arc toward the actual multi-factor model path. No data ingestion, model, signal, backtest, paper-trading deployment, candidate promotion, or final-candidate change existed yet.

---

## Phase 13C–13H: Feature Contracts, Schemas, and Calculation Pre-Registration

Phases 13C–13H established the feature-governance layer before any model was permitted to train.

The purpose was to prevent a common failure mode in quantitative research:

> Combining poorly timestamped features, future information, revised macro data, and undocumented transforms in a model and then presenting the output as an artificial-intelligence trading system.

This stage therefore required every feature family to document:

* source identity;
* economic observation date;
* public release date;
* conservative availability date;
* decision date;
* revision or vintage treatment;
* missingness policy;
* transformation rules;
* leakage controls;
* contract version;
* audit outputs.

Technical and macro families were permitted to proceed to bounded calculation.

Fundamental and sentiment families remained blocked because their historical point-in-time sources had not yet been audited.

No signal, target-driven feature selection, model training, backtest, paper-trading deployment, or candidate promotion was allowed during these phases.

---

### Phase 13C: Feature-Source Inventory / Leakage-Feasibility Spec

Phase 13C defined the first feature-source inventory and leakage-feasibility contract.

| Family                   | Status                                            | Decision                                                     |
| ------------------------ | ------------------------------------------------- | ------------------------------------------------------------ |
| Technical                | Source contract feasible                          | Eligible for contract design                                 |
| Macro                    | Source contract feasible with Phase 10 foundation | Eligible for contract design with strict lagging             |
| Fundamental              | Requires source audit before use                  | Blocked until dedicated fundamental source/leakage audit     |
| Sentiment                | Requires source audit before use                  | Blocked until dedicated sentiment source/leakage/noise audit |
| Dissertation integration | Methodology only                                  | Allowed as methodology, not direct market feature            |

Required contract controls:

* source identity;
* timestamp policy;
* lag policy;
* revision policy;
* missingness policy;
* transform policy;
* no return-based feature selection;
* audit output.

Phase 13C verdict:

> Phase 13C completed the feature-source inventory and leakage-feasibility spec.

---

### Phase 13D: Feature Contract / Data Availability Readiness Audit

Phase 13D audited the Phase 13C feature-source inventory and contract-readiness state.

| Check                                         | Result |
| --------------------------------------------- | ------ |
| Required feature families present             | Passed |
| Contract requirements present                 | Passed |
| Leakage controls present                      | Passed |
| Technical not blocked                         | Passed |
| Macro not blocked but requires strict lagging | Passed |
| Fundamental blocked until audit               | Passed |
| Sentiment blocked until audit                 | Passed |

Phase 13D verdict:

> Phase 13D completed the feature contract readiness audit.

Correct interpretation:

> Technical and macro could proceed to schema design. Fundamental and sentiment remained blocked.

---

### Phase 13E: Technical and Macro Feature-Contract Schema Design Spec

Phase 13E defined the technical and macro feature-contract schemas.

The universal feature-panel schema includes:

| Field                 | Role                                                     |
| --------------------- | -------------------------------------------------------- |
| `as_of_date`          | Canonical row date for the feature panel                 |
| `observation_date`    | Date the raw value economically refers to                |
| `release_date`        | First public release date where applicable               |
| `availability_date`   | Conservative date on which the feature becomes usable    |
| `decision_date`       | Trading-decision date after required lags                |
| `family_id`           | Feature family identifier                                |
| `feature_id`          | Stable feature identifier                                |
| `source_name`         | Raw source/provider                                      |
| `source_version`      | Version, vintage, download date, or contract version     |
| `raw_value_available` | Whether raw source value exists                          |
| `feature_state`       | Supportive, neutral, fragile, unavailable, or blocked    |
| `missingness_state`   | Available, missing, stale, unavailable, or blocked       |
| `leakage_flag`        | Whether the row violates availability/revision/lag rules |
| `contract_version`    | Feature-contract version used                            |

Technical features registered for schema design:

| Feature                      | Role                                       |
| ---------------------------- | ------------------------------------------ |
| `technical_trend_state`      | Price versus 200-day SMA state             |
| `technical_momentum_state`   | 252-trading-day momentum state             |
| `technical_volatility_state` | 63-trading-day annualised volatility state |
| `technical_drawdown_state`   | Drawdown from 252-trading-day high state   |

Macro features registered for schema design:

| Feature                   | Role                                         |
| ------------------------- | -------------------------------------------- |
| `macro_short_rate_state`  | DGS2 short-rate regime state                 |
| `macro_yield_curve_state` | DGS10 minus DGS2 yield-curve regime state    |
| `macro_inflation_state`   | CPI year-on-year inflation regime state      |
| `macro_labour_state`      | UNRATE level and 3-month change regime state |

Phase 13E verdict:

> Phase 13E completed the technical and macro feature schema design spec.

---

### Phase 13F: Feature Schema Readiness / Visual Report Template Audit

Phase 13F audited schema coverage, visual templates, and ML feature-engineering policy readiness.

| Check                                                              | Result |
| ------------------------------------------------------------------ | ------ |
| Required universal timestamp/state columns present                 | Passed |
| Technical schema has at least four non-calculated features         | Passed |
| Macro schema has at least four non-calculated features             | Passed |
| Required visual templates present                                  | Passed |
| ML leakage policies present                                        | Passed |
| Scope blocks feature/model/signal/backtest/paper-trading/promotion | Passed |

Phase 13F verdict:

> Phase 13F completed the feature schema readiness and visual template audit.

---

### Phase 13G: Technical/Macro Feature Calculation Pre-Registration Spec

Phase 13G locked the exact technical and macro feature-calculation rules.

| Feature                      | Family    | Formula                                |
| ---------------------------- | --------- | -------------------------------------- |
| `technical_trend_state`      | Technical | Price versus 200-day SMA               |
| `technical_momentum_state`   | Technical | 252-trading-day total return           |
| `technical_volatility_state` | Technical | 63-trading-day annualised volatility   |
| `technical_drawdown_state`   | Technical | Drawdown from 252-trading-day high     |
| `macro_short_rate_state`     | Macro     | DGS2 short-rate level regime           |
| `macro_yield_curve_state`    | Macro     | DGS10 minus DGS2 yield-curve regime    |
| `macro_inflation_state`      | Macro     | CPI year-on-year inflation regime      |
| `macro_labour_state`         | Macro     | UNRATE level and 3-month change regime |

Locked output schema:

```text
as_of_date
observation_date
release_date
availability_date
decision_date
family_id
feature_id
formula_id
source_name
source_version
raw_inputs_available
feature_value
feature_state
state_reason
missingness_state
leakage_flag
contract_version
```

ML safeguards:

| Lock                                           | Result |
| ---------------------------------------------- | ------ |
| Train-only scaling required                    | Passed |
| Target leakage forbidden                       | Passed |
| Post-hoc feature selection forbidden           | Passed |
| Outlier policy predeclared                     | Passed |
| Categorical state first                        | Passed |
| Feature importance forbidden until model phase | Passed |

Phase 13G verdict:

> Phase 13G completed the feature calculation pre-registration spec.

---

### Phase 13H: Feature Calculation Readiness Audit

Phase 13H verified that Phase 13G’s formulas, output schema, missingness behaviour, leakage checks, visual checks, and ML locks were ready for feature-calculation execution.

| Boundary                          | Result |
| --------------------------------- | ------ |
| May calculate features            | True   |
| May create feature panels         | True   |
| May create visual feature reports | True   |
| May create signal                 | False  |
| May train model                   | False  |
| May run backtest                  | False  |
| May deploy paper trading          | False  |
| May promote candidate             | False  |

Phase 13H verdict:

> Phase 13H completed the feature calculation readiness audit.

---

## Phase 13I–13J: Technical and Macro Feature Calculation and Quality Audit

Phases 13I and 13J converted the pre-registered contracts into the first governed technical and macro feature panel.

The calculation produced:

* eight registered technical and macro features;
* categorical feature states;
* source and contract metadata;
* availability and missingness states;
* leakage flags;
* visual audit tables;
* a future model-matrix preview.

The resulting panel contained:

```text
53,620 rows
8 registered features
0 leakage flags
```

The panel passed its structural quality audit.

However, structural validity did not imply model readiness. The subsequent Phase 13K interpretation found that all four macro feature states remained unavailable, exposing a material gap between schema compliance and usable historical feature coverage.

---

### Phase 13I: Feature Calculation Execution

Phase 13I executed the first bounded technical and macro feature-calculation phase.

It calculated:

* feature panels;
* feature states;
* availability/missingness outputs;
* leakage audit outputs;
* visual feature-report tables.

It did not create signals, allocation rules, models, backtests, paper-trading logic, candidate promotion, or final-candidate changes.

### Input Sources

| Source Type     | Source                                      |  Rows | Date Range               | Result |
| --------------- | ------------------------------------------- | ----: | ------------------------ | ------ |
| Technical price | In-memory run backtest outputs              | 8,371 | 1993-01-29 to 2026-05-01 | Passed |
| Macro aligned   | `reports/phase10c_macro_aligned_series.csv` | 5,034 | 2006-04-28 to 2026-05-01 | Passed |

### Feature Panel

Phase 13I created:

```text
reports/phase13i_feature_panel.csv
```

Key figures:

| Metric              | Result |
| ------------------- | -----: |
| Feature panel rows  | 53,620 |
| Feature ID count    |      8 |
| Leakage flag count  |      0 |
| Visual report count |      5 |

Visual feature reports created:

| Report                                      | Purpose                                                        |
| ------------------------------------------- | -------------------------------------------------------------- |
| `phase13i_feature_state_timeline.csv`       | Feature-state timeline across dates                            |
| `phase13i_feature_availability_heatmap.csv` | Availability/missingness heatmap                               |
| `phase13i_leakage_audit_panel.csv`          | Release/availability/decision-date leakage audit               |
| `phase13i_model_feature_matrix_preview.csv` | Feature-matrix preview for future model work                   |
| `phase13i_decision_rationale_template.csv`  | Feature-state rationale table for future decision explanations |

Phase 13I verdict:

> Phase 13I completed the feature calculation execution.

---

### Phase 13J: Feature Panel Quality / Leakage Audit

Phase 13J audited the Phase 13I feature panel, visual reports, missingness handling, leakage controls, schema quality, and forbidden-column boundaries.

| Check                                                | Result |
| ---------------------------------------------------- | ------ |
| Feature panel has enough rows                        | Passed |
| Feature panel has enough feature IDs                 | Passed |
| Available-state ratio is acceptable                  | Passed |
| Required feature-panel columns present               | Passed |
| Feature states use allowed categorical states        | Passed |
| Missingness states use allowed vocabulary            | Passed |
| Unavailable rows have state reasons                  | Passed |
| Leakage flag count acceptable                        | Passed |
| Decision date is after or equal to availability date | Passed |
| Forbidden signal/model/backtest columns absent       | Passed |

Key figures:

```text
rows = 53,620
feature_ids = 8
available_ratio = 0.6102
leakage_flags = 0
```

Phase 13J verdict:

> Phase 13J completed the feature panel quality and leakage audit.

---

## Phase 13K–13N: ML Dataset Preparation and Macro-Availability Guard

Phases 13K–13N interpreted the feature panel, pre-registered the first ML target and temporal splits, assembled the dataset, and audited its quality.

The primary target was fixed as:

```text
future_63d_spy_return_state
```

The split design was fixed before model training:

| Split                    | Dates                    |
| ------------------------ | ------------------------ |
| Initial training period  | 2006-04-28 to 2016-12-30 |
| Validation period        | 2017-01-03 to 2020-12-31 |
| Untouched holdout period | 2021-01-01 to 2026-05-01 |

A hard macro-availability guard then identified that the four macro feature states had zero usable availability.

The system responded conservatively:

```text
macro available ratio = 0.0000
macro blocked = True
dataset label = technical_only_macro_blocked_dataset_v1
```

This was an important integrity result.

The project did not silently:

* fill missing macro states;
* label the dataset as multi-factor;
* train on unavailable features;
* weaken the availability threshold;
* reinterpret missingness as neutral information.

The assembled dataset still passed its structural, target, split, and leakage audits, but it was correctly classified as technical-only until the macro branch could be repaired.

The correct conclusion after Phase 13N was:

> The first ML dataset was structurally valid and leak-audited, but it was not yet an honest technical-plus-macro dataset. Macro availability required a dedicated repair and re-audit before the intended multi-factor model path could continue.

### Phase 13K: Feature Panel Interpretation / Model-Readiness Planning

Phase 13K interpreted the Phase 13I/13J feature panel and assessed whether the project was ready to pre-register an ML dataset, target, split, and walk-forward design.

### Feature Availability Summary

| Family    | Feature                      |  Rows | Available Rows | Available Ratio | Date Range               |
| --------- | ---------------------------- | ----: | -------------: | --------------: | ------------------------ |
| Macro     | `macro_inflation_state`      | 5,034 |              0 |          0.0000 | 2006-04-28 to 2026-05-01 |
| Macro     | `macro_labour_state`         | 5,034 |              0 |          0.0000 | 2006-04-28 to 2026-05-01 |
| Macro     | `macro_short_rate_state`     | 5,034 |              0 |          0.0000 | 2006-04-28 to 2026-05-01 |
| Macro     | `macro_yield_curve_state`    | 5,034 |              0 |          0.0000 | 2006-04-28 to 2026-05-01 |
| Technical | `technical_drawdown_state`   | 8,371 |          8,120 |          0.9700 | 1993-01-29 to 2026-05-01 |
| Technical | `technical_momentum_state`   | 8,371 |          8,119 |          0.9699 | 1993-01-29 to 2026-05-01 |
| Technical | `technical_trend_state`      | 8,371 |          8,172 |          0.9762 | 1993-01-29 to 2026-05-01 |
| Technical | `technical_volatility_state` | 8,371 |          8,308 |          0.9925 | 1993-01-29 to 2026-05-01 |

Interpretation:

> The feature panel was structurally valid, but all four macro feature states were unavailable. Macro needed repair before the project could honestly claim a technical + macro model dataset.

Phase 13K verdict:

> Phase 13K completed feature panel interpretation and model-readiness planning.

---

### Phase 13L: Dataset Split and ML Target Design Pre-Registration Spec

Phase 13L pre-registered the ML dataset, target, split, walk-forward, and leakage-control design.

### Primary Target

| Item                       | Result                                                                    |
| -------------------------- | ------------------------------------------------------------------------- |
| Target ID                  | `future_63d_spy_return_state`                                             |
| Target type                | Classification                                                            |
| Target horizon             | 63 trading days                                                           |
| Formula                    | `future_return_63d = adjusted_close_t_plus_63 / adjusted_close_t - 1`     |
| Label policy               | Supportive if future return > 5%; neutral if -5% to +5%; fragile if < -5% |
| Target calculated now      | False                                                                     |
| Trading signal created now | False                                                                     |

### Secondary Target

| Item                       | Result                                                    |
| -------------------------- | --------------------------------------------------------- |
| Target ID                  | `future_63d_drawdown_risk_state`                          |
| Target type                | Classification                                            |
| Target horizon             | 63 trading days                                           |
| Formula                    | Future 63-trading-day window max drawdown                 |
| Label policy               | Fragile if future max drawdown <= -10%; neutral otherwise |
| Target calculated now      | False                                                     |
| Trading signal created now | False                                                     |

### Split Design

| Split                    | Dates                    |
| ------------------------ | ------------------------ |
| Initial training period  | 2006-04-28 to 2016-12-30 |
| Validation period        | 2017-01-03 to 2020-12-31 |
| Untouched holdout period | 2021-01-01 to 2026-05-01 |

Phase 13L verdict:

> Phase 13L completed the dataset split and ML target pre-registration spec.

---

### Phase 13M: ML Dataset Assembly with Macro Availability Guard

Phase 13M assembled the first ML dataset after applying a hard macro availability guard.

The guard correctly blocked macro usage because macro feature availability was still zero.

### Macro Guard Result

| Metric                               |                                    Result |
| ------------------------------------ | ----------------------------------------: |
| Current macro available ratio        |                                    0.0000 |
| Repaired macro available ratio       |                                    0.0000 |
| Minimum macro available ratio to use |                                    0.2000 |
| Repaired successfully                |                                     False |
| Macro blocked for dataset v1         |                                      True |
| Dataset label                        | `technical_only_macro_blocked_dataset_v1` |

### Dataset Summary

| Metric                 | Result |
| ---------------------- | -----: |
| Dataset rows           |  5,034 |
| Target available rows  |  4,788 |
| Target available ratio | 0.9511 |
| Leakage flag count     |      0 |
| Model training         |  False |
| Signal creation        |  False |
| Strategy backtest      |  False |

Interpretation:

> Macro repair failed. The dataset was therefore correctly labelled technical-only / macro-blocked, not multi-factor.

Phase 13M verdict:

> Phase 13M completed ML dataset assembly with macro availability guard.

---

### Phase 13N: ML Dataset Quality / Leakage Audit

Phase 13N audited the Phase 13M dataset, target quality, split quality, macro guard honesty, forbidden-column boundaries, and leakage controls.

| Check                                          | Result |
| ---------------------------------------------- | ------ |
| Dataset has enough rows                        | Passed |
| Dataset has enough feature-value columns       | Passed |
| Primary target column exists                   | Passed |
| Secondary target column exists                 | Passed |
| Target availability ratio acceptable           | Passed |
| Train split has rows                           | Passed |
| Validation split has rows                      | Passed |
| Holdout split has rows                         | Passed |
| Macro was repaired or blocked                  | Passed |
| Dataset label matches macro guard result       | Passed |
| Forbidden model/signal/backtest columns absent | Passed |

Phase 13N verdict:

> Phase 13N completed the ML dataset quality and leakage audit.

---

## Phase 13O–13R: Macro-Availability Repair

Phases 13O–13R investigated and repaired the zero-availability problem affecting the macro feature family.

The issue was not missing macro data. The source existed, but its structure did not match the feature-calculation logic:

```text
Stored source format:
series_id + value

Expected feature format:
DGS2
DGS10
CPIAUCSL
UNRATE
```

The project therefore treated the problem as a source-normalisation defect rather than silently dropping macro data, filling unavailable values, or mislabelling the dataset as multi-factor.

The repair sequence was:

```text
Phase 13O: identify the root cause
Phase 13P: pre-register the repair decision
Phase 13Q: execute long-to-wide normalisation and rebuild the dataset
Phase 13R: audit the repaired dataset
```

The repair succeeded:

```text
macro available ratio = 0.9720
dataset label = multi_factor_technical_macro_dataset_v1
leakage flags = 0
```

This restored the intended technical-plus-macro dataset path.

It did not create a model, signal, strategy backtest, paper-trading system, or promoted candidate.

### Phase 13O: Macro Availability Root-Cause Diagnostic

Phase 13O diagnosed why macro availability remained at zero.

The macro data existed, but it was stored in long format:

```text
series_id + value
```

The feature repair logic expected wide columns like:

```text
DGS2
DGS10
CPIAUCSL
UNRATE
```

### Root Cause

| Metric                              | Result                                       |
| ----------------------------------- | -------------------------------------------- |
| Source found                        | True                                         |
| Long format detected                | True                                         |
| All required columns numeric usable | False                                        |
| Repair panel has available rows     | False                                        |
| Macro blocked for dataset v1        | True                                         |
| Root cause                          | `macro_source_long_format_not_normalised`    |
| Recommended action                  | `implement_long_to_wide_macro_normalisation` |
| Repairability                       | `repairable_with_source_normalisation`       |

Phase 13O verdict:

> Phase 13O completed the macro availability root-cause diagnostic.

---

### Phase 13P: Macro Feature Repair Decision and Specification

Phase 13P converted the Phase 13O root-cause diagnosis into a repair decision and repair specification.

| Item                                   | Result                                       |
| -------------------------------------- | -------------------------------------------- |
| Root cause                             | `macro_source_long_format_not_normalised`    |
| Recommended action                     | `implement_long_to_wide_macro_normalisation` |
| Repairability                          | `repairable_with_source_normalisation`       |
| Dataset label until repair validated   | `technical_only_macro_blocked_dataset_v1`    |
| Future repaired label only after audit | `multi_factor_technical_macro_dataset_v1`    |

Phase 13P verdict:

> Phase 13P completed the macro feature repair decision/spec.

---

### Phase 13Q: Macro Long-to-Wide Repair Execution and Guarded Dataset Reassembly

Phase 13Q repaired the macro availability issue by normalising the long-format macro source into a wide macro panel.

### Macro Repair Result

| Metric                               |                                    Result |
| ------------------------------------ | ----------------------------------------: |
| Macro wide rows                      |                                     5,033 |
| Macro repair panel rows              |                                    20,132 |
| Macro available ratio                |                                    0.9720 |
| Minimum macro available ratio to use |                                    0.2000 |
| Macro repair passed                  |                                      True |
| Dataset label                        | `multi_factor_technical_macro_dataset_v1` |

### Reassembled Dataset

| Metric                      | Result |
| --------------------------- | -----: |
| Dataset rows                |  5,219 |
| Target available rows       |  4,971 |
| Target available ratio      | 0.9525 |
| Value feature columns       |      8 |
| Macro value feature columns |      4 |
| State feature columns       |      8 |
| Missingness feature columns |      8 |
| Leakage flag count          |      0 |

Phase 13Q verdict:

> Phase 13Q completed macro long-to-wide repair and guarded dataset reassembly.

Correct interpretation:

> The macro source issue was repaired. A technical + macro ML dataset was assembled. No model, signal, backtest, paper trading, or promotion occurred.

---

### Phase 13R: Repaired Macro Dataset Quality / Leakage Audit

Phase 13R audited the repaired technical + macro ML dataset.

| Check                                          | Result |
| ---------------------------------------------- | ------ |
| Macro availability ratio passed                | Passed |
| Macro value feature columns exist              | Passed |
| Dataset label is multi-factor after repair     | Passed |
| Dataset has enough rows                        | Passed |
| Dataset has enough value feature columns       | Passed |
| Primary target column exists                   | Passed |
| Secondary target column exists                 | Passed |
| Target availability ratio passed               | Passed |
| Train/validation/holdout splits have rows      | Passed |
| Forbidden model/signal/backtest columns absent | Passed |

Key figures:

```text
dataset_label = multi_factor_technical_macro_dataset_v1
rows = 5,219
value_feature_columns = 8
macro_available_ratio = 0.9720
target_available_ratio = 0.9525
```

Phase 13R verdict:

> Phase 13R completed the repaired macro dataset quality audit.

---

## Phase 13S–13W: Baseline ML Training and Interpretation

Phases 13S–13W executed the first governed machine-learning experiment on the repaired technical-plus-macro dataset.

The protocol was pre-registered before training and enforced:

* fixed model families;
* fixed train and validation periods;
* train-only preprocessing;
* untouched holdout data;
* no feature selection using validation or holdout;
* no threshold tuning;
* no strategy backtest;
* no signal mapping;
* no candidate promotion.

Five registered model families were evaluated:

```text
majority-class dummy
stratified dummy
multinomial logistic regression
random forest
histogram gradient boosting
```

Random Forest produced the strongest validation metrics:

```text
validation balanced accuracy = 0.4253
validation macro F1 = 0.4010
```

However, the apparent validation lead was insufficient for continuation because:

* all substantive models showed material train-validation gaps;
* the diagnostic-leading Random Forest had zero recall for the fragile class;
* the model failed precisely where the future decision system needed the strongest adverse-regime sensitivity.

The Phase 13W continuation decision was therefore:

```text
continue_only_after_model_diagnostic_repair
```

No model was selected, no holdout prediction was permitted, and no trading claim was made.

The correct conclusion was:

> The baseline ML run produced some validation signal, but its overfitting and complete failure to recall the fragile class prevented progression to holdout evaluation.

### Phase 13S: ML Model Training Pre-Registration and Baseline Model Design Spec

Phase 13S pre-registered the ML model-training protocol for the repaired technical + macro dataset.

### Registered Model Families

| Model ID                            | Family            | Role                                   |
| ----------------------------------- | ----------------- | -------------------------------------- |
| `baseline_majority_class`           | Dummy classifier  | Sanity baseline                        |
| `baseline_stratified_dummy`         | Dummy classifier  | Randomised class-frequency baseline    |
| `multinomial_logistic_regression`   | Linear classifier | Interpretable baseline classifier      |
| `random_forest_classifier`          | Tree ensemble     | Non-linear baseline classifier         |
| `hist_gradient_boosting_classifier` | Boosted trees     | Non-linear boosted baseline classifier |

Primary metrics:

```text
balanced_accuracy
macro_f1
macro_recall
```

Phase 13S verdict:

> Phase 13S completed the ML model training pre-registration spec.

---

### Phase 13T: ML Training Readiness and Leakage-Boundary Audit

Phase 13T confirmed dataset readiness, training protocol completeness, train-only preprocessing controls, holdout lockout, and forbidden-output absence.

Key boundary:

```text
Holdout split remains untouched.
No model selection, threshold selection, feature selection, or hyperparameter choice may use holdout.
```

Phase 13T verdict:

> Phase 13T completed the ML training readiness/leakage audit.

---

### Phase 13U: Registered Baseline ML Training Execution

Phase 13U executed the first registered baseline ML training run on the repaired technical + macro dataset.

This was train/validation only.

It did not generate holdout predictions, calculate feature importance, create signals, create allocation rules, run strategy backtests, deploy paper trading, promote a candidate, or change the final candidate.

### Dataset / Feature Matrix

| Metric                      |                                    Result |
| --------------------------- | ----------------------------------------: |
| Dataset label               | `multi_factor_technical_macro_dataset_v1` |
| Numeric feature columns     |                                         8 |
| Categorical feature columns |                                        16 |
| Total feature columns       |                                        24 |
| Train model rows            |                                     2,689 |
| Validation model rows       |                                     1,007 |
| Holdout rows used           |                                         0 |

### Validation Metrics

| Model                  | Validation Balanced Accuracy | Validation Macro F1 | Delta Balanced Accuracy vs Majority | Delta Macro F1 vs Majority |
| ---------------------- | ---------------------------: | ------------------: | ----------------------------------: | -------------------------: |
| Majority dummy         |                       0.3333 |              0.2050 |                              0.0000 |                     0.0000 |
| Stratified dummy       |                       0.3475 |              0.3407 |                             +0.0141 |                    +0.1358 |
| Logistic regression    |                       0.3417 |              0.3105 |                             +0.0084 |                    +0.1055 |
| Random forest          |                       0.4253 |              0.4010 |                             +0.0920 |                    +0.1960 |
| Hist gradient boosting |                       0.3604 |              0.3299 |                             +0.0271 |                    +0.1249 |

Interpretation:

> Random Forest was the strongest validation model in the first registered technical + macro ML run.

Important caveat:

> This was classification evidence only. It was not trading evidence, not a signal, not a backtest, and not a candidate promotion.

Phase 13U verdict:

> Phase 13U completed registered baseline ML train/validation execution.

---

### Phase 13V: ML Training Result Quality / Leakage Audit

Phase 13V audited the Phase 13U ML training outputs.

| Check                             | Result |
| --------------------------------- | ------ |
| Minimum registered models trained | Passed |
| No holdout rows used              | Passed |
| No model selected                 | Passed |
| Metrics sufficient                | Passed |
| Confusion matrices sufficient     | Passed |
| Class support reports sufficient  | Passed |
| Validation predictions only       | Passed |
| No holdout prediction flag        | Passed |
| Forbidden outputs absent          | Passed |

Phase 13V verdict:

> Phase 13V completed the ML training result quality/leakage audit.

---

### Phase 13W: ML Validation Result Interpretation and Continuation Decision

Phase 13W interpreted the validation-only ML evidence.

### Validation Ranking

| Rank | Model                               | Validation Balanced Accuracy | Validation Macro F1 | Delta Balanced Accuracy vs Majority |
| ---: | ----------------------------------- | ---------------------------: | ------------------: | ----------------------------------: |
|    1 | `random_forest_classifier`          |                       0.4253 |              0.4010 |                             +0.0920 |
|    2 | `hist_gradient_boosting_classifier` |                       0.3604 |              0.3299 |                             +0.0271 |
|    3 | `baseline_stratified_dummy`         |                       0.3475 |              0.3407 |                             +0.0141 |
|    4 | `multinomial_logistic_regression`   |                       0.3417 |              0.3105 |                             +0.0084 |
|    5 | `baseline_majority_class`           |                       0.3333 |              0.2050 |                              0.0000 |

### Overfit Diagnostic

| Model                               | Train Balanced Accuracy | Validation Balanced Accuracy |     Gap | Overfit Warning |
| ----------------------------------- | ----------------------: | ---------------------------: | ------: | --------------- |
| `hist_gradient_boosting_classifier` |                  0.9748 |                       0.3604 |  0.6144 | True            |
| `multinomial_logistic_regression`   |                  0.7418 |                       0.3417 |  0.4001 | True            |
| `random_forest_classifier`          |                  0.7708 |                       0.4253 |  0.3455 | True            |
| `baseline_majority_class`           |                  0.3333 |                       0.3333 |  0.0000 | False           |
| `baseline_stratified_dummy`         |                  0.3403 |                       0.3475 | -0.0071 | False           |

### Fragile-Class Recall

| Model                               | Fragile Validation Recall | Warning |
| ----------------------------------- | ------------------------: | ------- |
| `baseline_majority_class`           |                    0.0000 | True    |
| `baseline_stratified_dummy`         |                    0.2157 | False   |
| `hist_gradient_boosting_classifier` |                    0.0000 | True    |
| `multinomial_logistic_regression`   |                    0.0000 | True    |
| `random_forest_classifier`          |                    0.0000 | True    |

Important interpretation:

> The diagnostic-leading Random Forest failed to recall the fragile class. This is serious because the eventual decision system must be especially careful around adverse regimes.

### Continuation Decision

| Item                               | Result                                        |
| ---------------------------------- | --------------------------------------------- |
| Decision                           | `continue_only_after_model_diagnostic_repair` |
| Diagnostic leading model           | `random_forest_classifier`                    |
| Holdout pre-registration justified | False                                         |
| Model selected                     | False                                         |
| Signal permission                  | False                                         |
| Backtest permission                | False                                         |
| Candidate promotion                | False                                         |

Phase 13W verdict:

> Phase 13W completed the ML validation interpretation / continuation decision.

Correct interpretation:

> The ML branch had enough validation signal to continue, but not enough quality to proceed directly to holdout. Overfit and fragile-class recall weakness had to be diagnosed and repaired first.

---

## Phase 13X–13AF: Diagnostic Repair, Failure Attribution, and Architecture Pivot

Phases 13X–13AF tested whether the baseline ML defects could be repaired without opening an unrestricted modelling search.

The repair path was pre-registered and limited to:

* shallower and more regularised Random Forests;
* fragile-class weighting;
* stronger logistic regularisation;
* shallow, L2-regularised histogram gradient boosting.

The repair goals were:

1. improve fragile-class recall;
2. reduce train-validation overfitting;
3. preserve a meaningful edge over dummy baselines.

The repair execution was technically clean but economically unsuccessful.

No registered repair variant achieved acceptable fragile-class recall:

| Repair Variant                         | Fragile Validation Recall |
| -------------------------------------- | ------------------------: |
| Shallow regularised Random Forest      |                    0.0000 |
| Fragile-weighted Random Forest         |                    0.0000 |
| Highly regularised Logistic Regression |                    0.0000 |
| Shallow L2 Hist Gradient Boosting      |                    0.0098 |

The failure-attribution audit showed that:

* the fragile labels were economically meaningful;
* the class was less common, but not absent;
* technical and macro features were insufficient to identify fragile regimes reliably;
* the 63-day horizon or target structure might be poorly aligned;
* additional tuning of the same models was unlikely to solve the core problem.

The architecture decision was therefore:

```text
pivot_to_target_feature_redesign_preregistration
```

Direct holdout evaluation was blocked.

The correct conclusion was:

> The model-family repair attempt failed. The project therefore moved to a pre-registered target and feature redesign rather than continuing incremental tuning of the same technical-plus-macro setup.

### Phase 13X: ML Branch Checkpoint Audit

Phase 13X checkpointed the ML branch after Phase 13W.

It confirmed:

* Phase 13W reports were present;
* interpretation boundaries were clean;
* forbidden overclaim phrases were absent;
* no model was selected;
* no signal, backtest, promotion, or final-candidate change occurred.

Phase 13X verdict:

> Phase 13X completed the ML branch checkpoint audit.

---

### Phase 13Y: ML Diagnostic Repair Pre-Registration Spec

Phase 13Y pre-registered a diagnostic repair path before any holdout evaluation.

### Registered Repair Targets

| Repair Target                | Problem                                                     | Required Direction                                                      |
| ---------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------- |
| `fragile_class_recall`       | Diagnostic-leading model had 0.0 fragile validation recall  | Increase fragile recall without destroying validation balanced accuracy |
| `overfit_control`            | All real models triggered overfit warnings                  | Reduce train-validation metric gap                                      |
| `baseline_edge_preservation` | Random Forest edge exists but not robust enough for holdout | Preserve material edge versus dummy baselines                           |

### Registered Repair Hypotheses

| Repair ID                             | Base Family            | Hypothesis                                                             |
| ------------------------------------- | ---------------------- | ---------------------------------------------------------------------- |
| `rf_repair_shallow_regularised`       | Random Forest          | Shallower trees and larger leaves may reduce overfit                   |
| `rf_repair_fragile_weighted`          | Random Forest          | Fragile-class weighting may improve fragile recall                     |
| `logistic_repair_high_regularisation` | Logistic Regression    | Stronger regularisation may reduce linear-model overfit                |
| `histgb_repair_shallow_l2`            | Hist Gradient Boosting | Shallow boosted trees with L2 regularisation may reduce severe overfit |

Phase 13Y verdict:

> Phase 13Y completed ML diagnostic repair pre-registration.

---

### Phase 13Z: ML Diagnostic Repair Readiness and Boundary Audit

Phase 13Z confirmed that the registered repair path was ready for train/validation-only execution.

Phase 13Z verdict:

> Phase 13Z completed ML diagnostic repair readiness audit.

---

### Phase 13AA: Registered ML Diagnostic Repair Execution

Phase 13AA executed the registered repair variants.

### Repair Metrics

| Repair ID                             | Validation Balanced Accuracy | Validation Macro F1 | Fragile Validation Recall | Result                              |
| ------------------------------------- | ---------------------------: | ------------------: | ------------------------: | ----------------------------------- |
| `rf_repair_shallow_regularised`       |                       0.3968 |              0.3761 |                    0.0000 | Failed fragile recall               |
| `rf_repair_fragile_weighted`          |                       0.4157 |              0.3919 |                    0.0000 | Failed fragile recall               |
| `logistic_repair_high_regularisation` |                       0.3670 |              0.3329 |                    0.0000 | Failed fragile recall and weak edge |
| `histgb_repair_shallow_l2`            |                       0.3857 |              0.3606 |                    0.0098 | Failed fragile recall and overfit   |

Interpretation:

> The repair attempt failed to fix the fragile-class problem. Even fragile-weighted Random Forest still had 0.0 fragile recall.

Phase 13AA verdict:

> Phase 13AA completed registered ML diagnostic repair execution.

Correct interpretation:

> The repair execution was clean, but the repair hypotheses failed. This was a negative research result, not a model-improvement checkpoint.

---

### Phase 13AB: ML Diagnostic Repair Result Quality / Leakage Audit

Phase 13AB audited the Phase 13AA repair outputs.

Phase 13AB verdict:

> Phase 13AB completed ML diagnostic repair result quality audit.

Correct interpretation:

> The repair execution was clean and leakage-bounded, but it did not validate a repaired model or justify holdout evaluation.

---

### Phase 13AC: ML Failure Attribution and Target-Feature Diagnostic

Phase 13AC diagnosed why the registered repair attempt failed.

### Failure Summary

| Metric                                   |                       Result |
| ---------------------------------------- | ---------------------------: |
| Original best model                      |   `random_forest_classifier` |
| Original validation balanced accuracy    |                       0.4253 |
| Original validation macro F1             |                       0.4010 |
| Best repair model                        | `rf_repair_fragile_weighted` |
| Best repair validation balanced accuracy |                       0.4157 |
| Best repair validation macro F1          |                       0.3919 |
| Best repair fragile recall               |                       0.0000 |
| Economic repair success                  |                        False |

### Target Distribution

| Split      | Fragile Rows | Split Rows | Fragile Ratio |
| ---------- | -----------: | ---------: | ------------: |
| Train      |          410 |      2,784 |        14.73% |
| Validation |          102 |      1,043 |         9.78% |
| Holdout    |          157 |      1,391 |        11.29% |

### Target Outcome Profile

| Class      | Mean 63D Return | Mean 63D Max Drawdown |
| ---------- | --------------: | --------------------: |
| Fragile    |         -11.22% |               -18.44% |
| Neutral    |           1.34% |                -6.93% |
| Supportive |           9.03% |                -4.64% |

Interpretation:

> The labels were economically meaningful. The problem was not that the fragile label was irrelevant; the current feature/model setup could not detect it reliably.

### Failure Attribution

| Attribution Family              | Severity | Interpretation                                                         |
| ------------------------------- | -------- | ---------------------------------------------------------------------- |
| `target_definition`             | High     | Fragile class remained unrecalled after repair                         |
| `fragile_threshold`             | High     | Fragile recall stayed below success threshold                          |
| `class_imbalance`               | High     | Validation fragile support was low                                     |
| `feature_insufficiency`         | High     | Technical + macro features failed to identify fragile regimes reliably |
| `horizon_63d`                   | Medium   | 63D horizon may be sparse or poorly aligned                            |
| `model_architecture`            | Medium   | Simple registered model variants did not solve the defect              |
| `missing_fundamental_sentiment` | Medium   | Current dataset was still technical + macro only                       |

Phase 13AC verdict:

> Phase 13AC completed ML failure attribution and target-feature diagnostic.

Correct interpretation:

> The ML branch should not proceed to holdout or another random repair. The next work should pre-register target-feature redesign.

---

### Phase 13AD–13AF: Failure Attribution Checkpoint and Architecture Pivot

Phases 13AD–13AF audited the failure-attribution reports, made the continuation decision, and checkpointed the ML branch.

### Phase 13AE Architecture Decision

| Item                         | Result                                                               |
| ---------------------------- | -------------------------------------------------------------------- |
| Architecture decision        | `pivot_to_target_feature_redesign_preregistration`                   |
| Decision reason              | Fragile recall remained unresolved after registered repair execution |
| Fragile recall unresolved    | True                                                                 |
| Feature insufficiency likely | True                                                                 |
| Direct holdout blocked       | True                                                                 |

Phase 13AF verdict:

> Phase 13AF completed the Phase 13 ML branch checkpoint audit.

Correct interpretation:

> The ML branch pivoted away from immediate holdout. Next work had to pre-register target-feature redesign.

---

## Phase 13AG–13AN: Target and Feature Redesign

Phases 13AG–13AN investigated whether the ML failure was partly caused by the original fragile-class target rather than model choice alone.

The redesign process remained bounded:

1. pre-register alternative target definitions;
2. analyse class balance and economic meaning;
3. select one candidate target path;
4. pre-register a new train/validation-only model run;
5. keep the holdout locked.

The target diagnostic compared:

* the original 63-day return-state target;
* a looser 63-day return threshold;
* a 63-day return-plus-drawdown composite;
* a drawdown-first fragile target;
* blocked 21-day and 126-day future candidates.

The original target had economically meaningful outcomes but weak validation-period class balance.

Three redesigned targets improved class balance while retaining economic ordering.

The selected candidate target was:

```text
return_drawdown_63d_composite
```

This was a target-path decision only.

It did not select a model, create a trading signal, unlock holdout predictions, or authorise backtesting.

The redesigned model run was then pre-registered with:

* fixed model families;
* minimum edge over dummy baselines;
* minimum fragile-class recall;
* maximum overfit gaps;
* no holdout access;
* no feature-importance inspection;
* no signal or strategy testing.

### Phase 13AG: Target-Feature Redesign Pre-Registration Spec

Phase 13AG pre-registered the target-feature redesign diagnostic path.

### Registered Target Variants

| Target Variant                  | Rule Type                              | Status                                   |
| ------------------------------- | -------------------------------------- | ---------------------------------------- |
| `original_63d_return_state`     | Existing 63D return-state column       | Baseline comparison                      |
| `return_63d_fragile_looser`     | Looser 63D return-threshold target     | Diagnostic candidate                     |
| `return_drawdown_63d_composite` | 63D return + drawdown composite target | Diagnostic candidate                     |
| `drawdown_63d_fragile`          | 63D drawdown-first fragile target      | Diagnostic candidate                     |
| `return_21d_future_candidate`   | 21D future-horizon candidate           | Blocked until 21D outcome columns exist  |
| `return_126d_future_candidate`  | 126D future-horizon candidate          | Blocked until 126D outcome columns exist |

Phase 13AG verdict:

> Phase 13AG completed target-feature redesign pre-registration.

---

### Phase 13AH: Target-Feature Redesign Readiness / Boundary Audit

Phase 13AH confirmed that the target-feature redesign diagnostic was ready to execute as a panel-only diagnostic, not as model training.

Phase 13AH verdict:

> Phase 13AH completed target-feature redesign readiness audit.

---

### Phase 13AI: Target-Feature Diagnostic Panel Execution

Phase 13AI executed the target-feature diagnostic panel.

### Class Balance

| Target Variant                  | Train Fragile Ratio | Validation Fragile Ratio | Train Balance | Validation Balance |
| ------------------------------- | ------------------: | -----------------------: | ------------- | ------------------ |
| `original_63d_return_state`     |              14.73% |                    9.78% | Passed        | Failed             |
| `return_63d_fragile_looser`     |              18.46% |                   13.33% | Passed        | Passed             |
| `return_drawdown_63d_composite` |              20.80% |                   21.19% | Passed        | Passed             |
| `drawdown_63d_fragile`          |              18.97% |                   18.70% | Passed        | Passed             |
| `return_21d_future_candidate`   |               0.00% |                    0.00% | Failed        | Failed             |
| `return_126d_future_candidate`  |               0.00% |                    0.00% | Failed        | Failed             |

### Target Outcome Profile

| Target Variant                  | Fragile Mean 63D Return | Fragile Mean 63D Max Drawdown | Interpretation                                   |
| ------------------------------- | ----------------------: | ----------------------------: | ------------------------------------------------ |
| `original_63d_return_state`     |                 -11.22% |                       -18.44% | Strong economic meaning, weak validation balance |
| `return_63d_fragile_looser`     |                  -9.39% |                       -16.53% | Economically meaningful and better balanced      |
| `return_drawdown_63d_composite` |                  -6.73% |                       -16.51% | More balanced, drawdown-aware fragile class      |
| `drawdown_63d_fragile`          |                  -6.84% |                       -17.33% | More balanced, strongest drawdown interpretation |

### Redesign Screen

| Target Variant                  | Feasible | Train Balance | Validation Balance | Economic Ordering | Viable for Future Interpretation |
| ------------------------------- | -------: | ------------: | -----------------: | ----------------: | -------------------------------: |
| `original_63d_return_state`     |     True |          True |              False |              True |                            False |
| `return_63d_fragile_looser`     |     True |          True |               True |              True |                             True |
| `return_drawdown_63d_composite` |     True |          True |               True |              True |                             True |
| `drawdown_63d_fragile`          |     True |          True |               True |              True |                             True |
| `return_21d_future_candidate`   |    False |         False |              False |             False |                            False |
| `return_126d_future_candidate`  |    False |         False |              False |             False |                            False |

Phase 13AI verdict:

> Phase 13AI completed target-feature diagnostic panel execution.

Correct interpretation:

> The redesigned targets preserved economic meaning and improved class balance. No target was selected yet.

---

### Phase 13AJ: Target-Feature Diagnostic Result Audit

Phase 13AJ audited the Phase 13AI target-feature diagnostic panel.

Phase 13AJ verdict:

> Phase 13AJ completed target-feature diagnostic result audit.

---

### Phase 13AK: Target-Feature Redesign Interpretation / Candidate Target Decision

Phase 13AK interpreted the target-feature redesign diagnostic and selected a candidate target variant for a future pre-registered redesigned model run.

### Candidate Target Decision

| Item                          | Result                                              |
| ----------------------------- | --------------------------------------------------- |
| Decision                      | `pre_register_redesigned_model_run`                 |
| Candidate target variant      | `return_drawdown_63d_composite`                     |
| Backup target variants        | `drawdown_63d_fragile`; `return_63d_fragile_looser` |
| Model selected                | False                                               |
| Holdout permission            | False                                               |
| Feature importance permission | False                                               |
| Signal permission             | False                                               |
| Backtest permission           | False                                               |
| Candidate promotion           | False                                               |

Correct interpretation:

> `return_drawdown_63d_composite` was chosen as the candidate target for the next pre-registered model run. This was a target-path decision, not model selection or trading signal creation.

---

## Phase 13AL–13AN: Redesigned Model Run Pre-Registration and Readiness

### Phase 13AL: Target-Feature Redesign Checkpoint Audit

Phase 13AL checkpointed the Phase 13AK target decision.

Phase 13AL verdict:

> Phase 13AL completed the target-feature redesign checkpoint audit.

---

### Phase 13AM: Redesigned Model Run Pre-Registration

Phase 13AM pre-registered the redesigned model run using:

```text
return_drawdown_63d_composite
```

The run remained train/validation-only. Holdout stayed locked.

### Registered Model Families

| Model ID                               | Family                 | Notes                     |
| -------------------------------------- | ---------------------- | ------------------------- |
| `baseline_majority_class`              | Dummy                  | Most-frequent baseline    |
| `baseline_stratified_dummy`            | Dummy                  | Stratified dummy baseline |
| `redesigned_logistic_balanced`         | Logistic Regression    | Balanced class weights    |
| `redesigned_random_forest_regularised` | Random Forest          | Regularised forest        |
| `redesigned_histgb_constrained`        | Hist Gradient Boosting | Constrained boosting      |

### Success Gates

| Gate                                                       | Threshold / Rule |
| ---------------------------------------------------------- | ---------------- |
| Minimum validation balanced-accuracy delta vs majority     | 0.05             |
| Minimum validation macro-F1 delta vs majority              | 0.05             |
| Minimum validation fragile recall                          | 0.20             |
| Maximum balanced-accuracy overfit gap                      | 0.30             |
| Maximum macro-F1 overfit gap                               | 0.30             |
| Real model must beat stratified dummy on balanced accuracy | True             |
| Holdout predictions allowed                                | False            |
| Feature importance allowed                                 | False            |
| Signal/backtest allowed                                    | False            |

Phase 13AM verdict:

> Phase 13AM completed redesigned model run pre-registration.

---

### Phase 13AN: Redesigned Model Run Readiness and Leakage Audit

Phase 13AN audited readiness for the redesigned model run.

| Item                           |                          Result |
| ------------------------------ | ------------------------------: |
| Candidate target variant       | `return_drawdown_63d_composite` |
| Target assignment column ready |                            True |
| Train rows                     |                           2,784 |
| Validation rows                |                           1,043 |
| Train fragile ratio            |                          20.80% |
| Validation fragile ratio       |                          21.19% |
| Target balance ready           |                            True |
| Numeric feature columns        |                               8 |
| Categorical feature columns    |                              16 |
| Total feature columns          |                              24 |
| Feature matrix ready           |                            True |
| Holdout locked                 |                          Passed |

Interpretation:

> The redesigned target fixed the original fragile-sparsity problem enough to justify a train/validation-only redesigned model run.

Phase 13AN verdict:

> Phase 13AN completed redesigned model run readiness and leakage audit.

---

## Phase 13AO–13AQ: Redesigned Model Run Failure

The redesigned model run tested whether the more balanced `return_drawdown_63d_composite` target could resolve the weaknesses of ML v1.

The target redesign improved class balance, but it did not produce a model suitable for holdout evaluation.

The diagnostic-leading model was:

```text
redesigned_random_forest_regularised
```

| Metric                             | Result |
| ---------------------------------- | -----: |
| Validation balanced accuracy       | 0.3942 |
| Validation macro F1                | 0.3517 |
| Fragile-class recall               | 0.0090 |
| Real model passed all gates        |  False |
| Holdout pre-registration justified |  False |

The critical failure remained fragile-class detection.

Despite the more balanced target, the best model correctly recalled less than 1% of fragile validation observations.

The correct interpretation was:

> Target redesign improved the dataset structure but did not resolve the core predictive weakness. The technical-plus-macro ML v1 branch still could not identify adverse regimes reliably enough to justify holdout predictions, signal creation, backtesting, or paper trading.

The detailed Phase 13AO–13AQ reports are not expanded in this README section, but their conclusion is captured by Phase 13AV.

The key result:

> The redesigned technical + macro ML branch still failed validation-to-holdout quality. No model earned holdout testing.

The diagnostic-leading model was:

```text
redesigned_random_forest_regularised
```

Key validation figures:

| Metric                             | Result |
| ---------------------------------- | -----: |
| Validation balanced accuracy       | 0.3942 |
| Validation macro F1                | 0.3517 |
| Fragile recall                     | 0.0090 |
| Holdout pre-registration justified |  False |
| Real model passed all gates        |  False |

Correct interpretation:

> Even after target redesign, the technical + macro ML v1 branch did not detect fragile regimes well enough. It did not justify holdout prediction, signal creation, backtesting, or paper trading.

---
## Phase 13AV–13AW: Commercial Stop Decision and Paper-Trading Route Selection

Phases 13AV and 13AW converted the failed technical-plus-macro ML evidence into a practical project decision.

The decision criterion was no longer:

> Can another minor model adjustment improve validation metrics?

It became:

> What is the shortest responsible path towards a functioning paper-trading workflow?

The ML branch had already undergone:

* source repair;
* dataset reassembly;
* baseline model testing;
* registered model repair;
* failure attribution;
* target redesign;
* redesigned model testing.

It still failed to achieve acceptable fragile-class recall or justify holdout evaluation.

The commercial decision was therefore:

```text
pause_current_technical_macro_ml_v1
```

This blocked:

* further minor tuning of the same technical-plus-macro models;
* direct holdout evaluation;
* ML signal mapping;
* ML strategy backtesting;
* ML paper deployment.

Future ML work remained possible only after genuinely new information families—such as point-in-time fundamentals, sentiment, news, or additional market-stress features—were acquired and audited.

The project then compared three operational routes and selected:

```text
route_3_non_ml_overlay_visual_backtest_paper_readiness
```

The selected system was:

```text
phase6b_loose_relief_execution_realistic_overlay
```

This route was chosen because it:

* used an already validated non-ML candidate;
* avoided forcing a failed ML branch forward;
* had the strongest existing historical evidence;
* represented the fastest bounded path to operational paper testing;
* preserved the long-term multi-factor ambition without blocking near-term progress.

The route selection did not itself enable paper trading, live execution, broker integration, or real-money deployment.

The correct conclusion was:

> ML v1 was paused, and the existing non-ML overlay became the preferred near-term paper-readiness route.

## Phase 13AV: ML Branch Commercial Stop-or-Pivot Decision

Phase 13AV converted the failed Phase 13AQ validation-to-holdout result into a commercial/trading-path decision.

The purpose was to decide whether the current SPY technical + macro ML v1 branch deserved more time under the project’s revised priority:

> the shortest responsible path toward a paper-trading system.

### Failure Summary

| Item                               | Result                                 |
| ---------------------------------- | -------------------------------------- |
| ML branch                          | `technical_macro_ml_v1`                |
| Holdout pre-registration justified | False                                  |
| Diagnostic-leading model           | `redesigned_random_forest_regularised` |
| Best validation balanced accuracy  | 0.3942                                 |
| Best validation macro F1           | 0.3517                                 |
| Best validation fragile recall     | 0.0090                                 |
| Commercial failure                 | True                                   |

### Commercial Decision

| Item                                             | Result                                        |
| ------------------------------------------------ | --------------------------------------------- |
| Decision                                         | `pause_current_technical_macro_ml_v1`         |
| ML v1 status                                     | `pause_or_kill_current_technical_macro_ml_v1` |
| Minor model tuning allowed                       | False                                         |
| Future ML allowed only with new feature families | True                                          |
| Holdout predictions generated                    | False                                         |
| Model selected                                   | False                                         |
| Feature importance permission                    | False                                         |
| Signal permission                                | False                                         |
| Backtest permission                              | False                                         |
| Paper-trading permission                         | False                                         |
| Candidate promotion                              | False                                         |
| Final candidate changed                          | False                                         |

### Blocked Next Steps

| Blocked Next Step                                     | Reason                                                                        |
| ----------------------------------------------------- | ----------------------------------------------------------------------------- |
| `technical_macro_ml_minor_repair`                     | Simple redesign and registered model training already failed validation gates |
| `technical_macro_ml_direct_holdout`                   | Phase 13AQ did not justify holdout pre-registration                           |
| `technical_macro_ml_signal_mapping`                   | No ML model earned holdout                                                    |
| `technical_macro_ml_backtest`                         | No ML signal exists                                                           |
| `multi_asset_expansion_before_spy_candidate_decision` | Scope expansion would delay the fastest SPY paper-trading path                |

Phase 13AV verdict:

> Phase 13AV completed the ML branch commercial kill-or-pivot decision.

Correct interpretation:

> Technical + macro ML v1 is commercially paused for now. It may only be reconsidered later if genuinely new feature families are added, such as fundamental, sentiment, or market-stress features. More tuning of the same technical + macro setup is blocked.

---

## Phase 13AW: Paper-Trading Candidate Route Selection

Phase 13AW selected the fastest responsible route toward a paper-trading candidate after the commercial failure of technical + macro ML v1.

The compared routes were:

1. Pause ML and prepare the existing validated overlay for paper-trading workflow.
2. Defer ML until genuinely new feature families exist.
3. Move the best non-ML overlay into visual backtest and paper-trading readiness.

The selected route was:

```text
route_3_non_ml_overlay_visual_backtest_paper_readiness
```

### Route Comparison

| Route                                                        | Classification | Speed Rank | Validation Strength Rank | Scope Risk Rank | Status    |
| ------------------------------------------------------------ | -------------: | ---------: | -----------------------: | --------------: | --------- |
| `route_3_non_ml_overlay_visual_backtest_paper_readiness`     |              A |          1 |                        1 |               1 | Preferred |
| `route_1_pause_ml_move_validated_overlay_paper_prep`         |            A/B |          2 |                        1 |               1 | Allowed   |
| `route_2_bounded_ml_redesign_only_with_new_feature_families` |              B |          3 |                        3 |               3 | Deferred  |

### Selected Route

| Item                           | Result                                                                                          |
| ------------------------------ | ----------------------------------------------------------------------------------------------- |
| Selected route                 | `route_3_non_ml_overlay_visual_backtest_paper_readiness`                                        |
| Candidate system ID            | `phase6b_loose_relief_execution_realistic_overlay`                                              |
| Selection reason               | Fastest allowed route using existing validated non-ML candidate while avoiding more ML training |
| Backup route                   | `route_1_pause_ml_move_validated_overlay_paper_prep`                                            |
| Deferred route                 | `route_2_bounded_ml_redesign_only_with_new_feature_families`                                    |
| Next phase                     | Phase 14A — non-ML paper-trading candidate visual backtest pre-registration                     |
| ML v1 reopened                 | False                                                                                           |
| Model training permission      | False                                                                                           |
| Holdout prediction permission  | False                                                                                           |
| Feature importance permission  | False                                                                                           |
| Signal creation permission     | False                                                                                           |
| Backtest generation permission | False                                                                                           |
| Paper-trading permission       | False                                                                                           |
| Candidate promotion            | False                                                                                           |

Phase 13AW verdict:

> Phase 13AW completed paper-trading candidate route selection.

Correct interpretation:

> The fastest responsible route is now the non-ML overlay visual-backtest and paper-readiness path. Technical + macro ML v1 is paused/killed for now, and multi-asset expansion remains blocked until the SPY paper-trading candidate path is inspected properly.

---

## Phase 13 Final Verdict

| Area                              | Result                                            | Interpretation                                                                         |
| --------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------- |
| SPY baseline arc                  | Frozen                                            | Preserved as benchmark and validation infrastructure                                   |
| Multi-factor roadmap              | Completed                                         | Technical, macro, fundamental, sentiment, and methodology paths documented             |
| Feature contracts                 | Completed                                         | Timing, leakage, revision, missingness, and schema rules established                   |
| Technical and macro feature panel | Completed                                         | Eight governed features calculated and audited                                         |
| Macro availability                | Repaired                                          | Long-format source correctly normalised into a usable wide panel                       |
| First multi-factor dataset        | Completed                                         | Technical-plus-macro dataset assembled with no leakage flags                           |
| Baseline ML v1                    | Failed                                            | Validation signal existed, but overfitting and zero fragile recall blocked progression |
| Registered model repair           | Failed                                            | Regularisation and class weighting did not resolve fragile recall                      |
| Target redesign                   | Structurally useful but predictively insufficient | Class balance improved, but the redesigned models still failed                         |
| Holdout evaluation                | Blocked                                           | No model justified holdout prediction                                                  |
| ML commercial decision            | Paused                                            | Further minor tuning of technical-plus-macro ML v1 prohibited                          |
| Paper-trading route               | Selected                                          | Existing non-ML `loose_relief` overlay moved to operational-readiness work             |

Final Phase 13 interpretation:

> Phase 13 built the project’s first governed technical-plus-macro ML pipeline, repaired its data issues, trained bounded baseline models, diagnosed failure, redesigned the target, and still rejected the branch when the evidence remained insufficient.

The phase demonstrated that:

* a functioning ML pipeline is not the same as a useful ML model;
* validation improvements are insufficient if adverse-regime recall remains near zero;
* target redesign can improve class balance without improving predictive quality;
* failed models should not receive holdout access merely because significant engineering effort was invested;
* architecture, contracts, and datasets remain valuable even when the model fails;
* commercial project priorities should determine when a research branch is paused;
* the fastest responsible paper route may be a validated non-ML system rather than a weaker ML system.

The correct conclusion was:

> The long-term multi-factor objective remained valid, but technical-plus-macro ML v1 was not good enough. The project therefore preserved the ML infrastructure and failure evidence while moving the validated non-ML ETF overlay towards visual inspection, operational replay, and paper-trading readiness.

# Phase 14: Non-ML Visual Backtest and Signal-Mapping Route

Phase 14 translated the validated non-ML ETF candidate from research outputs into practical visual and operational artefacts.

After Phase 13 commercially paused the technical-plus-macro ML v1 branch, the project selected the fastest responsible near-term route:

> Use the existing Phase 6B/6C `loose_relief` execution-realistic overlay to build reproducible visual backtests, benchmark comparisons, signal previews, and operational reports.

The purpose was not to retest or promote the candidate. It was to answer a different set of questions:

1. Can the intended candidate stream be identified unambiguously?
2. Do the visual reports reconcile with the canonical Phase 6B/6C metrics?
3. Can the candidate’s exposure, switches, and current state be represented operationally?
4. Is the resulting output sufficiently trustworthy to define a paper-trading workflow?

Phase 14 did **not**:

* deploy paper trading;
* integrate with a broker or API;
* run live trading;
* use real money;
* train a model;
* calculate feature importance;
* promote a new candidate;
* change the final ETF hierarchy.

The implementation sequence followed the actual checkpoint history:

```text id="x4dt8p"
14A: visual-backtest and signal-mapping pre-registration
14B: visual-backtest readiness audit
14C: initial visual-backtest execution
14D: initial result audit
14E: candidate-source identity and metric-reconciliation audit
14F: candidate-source correction decision
14I: correct Phase 6B/6C daily-stream export
14J: exported-stream audit
14G: corrected visual-backtest re-run
14H: corrected visual-backtest audit and reconciliation decision
```

Phases 14I and 14J were introduced before the corrected 14G/14H run was finalised because an explicit candidate-stream export and audit were required to repair the source-resolution failure.

The central Phase 14 finding was:

> The first visual backtest was mechanically valid but used the wrong strategy source. The project rejected those results, exported the intended Phase 6B/6C candidate explicitly, reran the visual reports, and reconciled the corrected financial stream with the canonical checkpoint.

By the end of Phase 14:

* candidate-source identity had passed;
* financial metrics had reconciled;
* corrected visual artefacts existed;
* a preview current state could be displayed;
* operational switch reconstruction was still unresolved;
* paper-workflow pre-registration was allowed;
* paper deployment, broker integration, live trading, and real money remained blocked.

---

## Phase 14A: Non-ML Candidate Visual-Backtest and Signal-Mapping Pre-Registration

Phase 14A pre-registered the non-ML visual backtest and signal-mapping preview path after Phase 13AW selected the Phase 6B/6C `loose_relief` overlay as the fastest responsible paper-readiness route.

This phase registered required artefacts only. It did not generate reports, create live signals, deploy paper trading, or make the system paper-trading ready.

### Registered Artefacts

| Artefact                              | Required |
| ------------------------------------- | -------: |
| Equity curve vs SPY Buy & Hold        |     True |
| Drawdown curve                        |     True |
| Exposure / regime timeline            |     True |
| Trade log                             |     True |
| Switch / event log                    |     True |
| Money-made/lost table                 |     True |
| Benchmark comparison                  |     True |
| Rolling relative performance          |     True |
| Paper-trading signal-template preview |     True |

### Gate Result

| Gate                                 | Result |
| ------------------------------------ | ------ |
| Phase 13AW passed                    | Passed |
| Selected route is non-ML overlay     | Passed |
| Artefact registry exists             | Passed |
| Signal-mapping preview policy exists | Passed |
| Boundaries passed                    | Passed |
| Scope blocks forbidden actions       | Passed |
| Spec role is correct                 | Passed |

Phase 14A verdict:

> Phase 14A completed the visual-backtest and signal-preview pre-registration. It did not make the system paper-trading ready.

---

## Phase 14B: Non-ML Visual Backtest Readiness Audit

Phase 14B audited whether the candidate source and report structure were ready for visual backtest generation.

### Candidate Source Resolution

| Item                                      | Result                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------------------- |
| Source resolved                           | True                                                                                        |
| Source name                               | `relative_momentum_outputs.Top 3 Equal Weight Relative Momentum Allocator.allocator_result` |
| Rows                                      | 5,034                                                                                       |
| Date column                               | `date`                                                                                      |
| Candidate return column                   | `strategy_return`                                                                           |
| Benchmark return column                   | `SPY_return`                                                                                |
| Candidate equity column                   | `equity`                                                                                    |
| Candidate and benchmark returns available | True                                                                                        |
| Has exposure                              | True                                                                                        |
| Has mode                                  | True                                                                                        |
| First decision date                       | 2006-04-28                                                                                  |
| Last decision date                        | 2026-05-01                                                                                  |

Important caveat:

> The resolver selected a relative-momentum allocator output, not clearly the intended Phase 6B/6C `loose_relief` execution-realistic overlay. Source identity still had to be verified before paper-workflow progression.

### Gate Result

| Gate                                      | Result |
| ----------------------------------------- | ------ |
| Phase 14A passed                          | Passed |
| Config flags clean                        | Passed |
| Phase 14A reports present                 | Passed |
| Candidate source resolved                 | Passed |
| Candidate source has enough rows          | Passed |
| Candidate and benchmark returns available | Passed |
| Artefact registry complete                | Passed |
| Phase 14C boundary is execution-only      | Passed |
| Scope blocks forbidden actions            | Passed |
| Audit role is correct                     | Passed |

Phase 14B verdict:

> Phase 14B confirmed the visual-backtest pipeline could execute, but candidate-source identity remained unresolved.

---

## Phase 14C: Initial Non-ML Visual Backtest Report Execution

Phase 14C generated the first practical visual backtest artefacts.

Generated outputs included:

* equity curve;
* drawdown curve;
* exposure / regime timeline;
* trade log;
* switch / event log;
* money-made/lost table;
* benchmark comparison;
* rolling relative performance;
* signal-template preview;
* chart files for equity, drawdown, exposure, and rolling relative performance.

However, this run later proved to be based on the wrong candidate source.

### Initial Benchmark Comparison

| Series                    |  End Value | Total Return |     CAGR |                   Max Drawdown | Calmar |
| ------------------------- | ---------: | -----------: | -------: | -----------------------------: | -----: |
| Candidate                 |  55,325.08 |      453.25% |    8.94% |                        -35.74% |  0.250 |
| SPY Buy & Hold            |  79,306.62 |      693.07% |   10.92% |                        -55.19% |  0.198 |
| Candidate minus benchmark | -23,981.54 |     -239.82% | -1.98 pp | +19.45 pp drawdown improvement | +0.052 |

Initial interpretation:

> The visualised candidate made money in absolute terms and reduced drawdown versus SPY Buy & Hold, but it materially underperformed on terminal wealth and CAGR.

Later correction:

> These metrics did **not** match the intended Phase 6B/6C `loose_relief` candidate and were later rejected for paper-workflow purposes.

### Initial Money-Made / Lost Table

| Metric                        |      Value |
| ----------------------------- | ---------: |
| Candidate total PnL           |  45,325.08 |
| Benchmark total PnL           |  69,306.62 |
| Candidate minus benchmark PnL | -23,981.54 |
| Winning trade segments        |         29 |
| Losing trade segments         |         15 |
| Best trade segment PnL        |  20,436.67 |
| Worst trade segment PnL       |  -3,753.74 |

### Initial Report Inventory

| Artefact                     |  Rows |
| ---------------------------- | ----: |
| Equity curve                 | 5,034 |
| Drawdown curve               | 5,034 |
| Exposure timeline            | 5,034 |
| Trade log                    |    44 |
| Switch event log             |    43 |
| Rolling relative performance | 5,034 |
| Signal template preview      |    25 |

### Signal Template Preview

The signal-template preview ended with repeated `cash_or_defensive_preview` actions in late March to May 2026.

Boundary flags remained correct:

| Flag                  | Value |
| --------------------- | ----: |
| Paper trading allowed | False |
| Live trading allowed  | False |
| Real money allowed    | False |

Phase 14C verdict:

> Phase 14C generated the required visual artefacts, but the underlying candidate source still had to be audited.

---

## Phase 14D: Initial Visual Backtest Result Audit

Phase 14D audited the Phase 14C outputs.

It confirmed that the reports existed, chart files existed, report rows were non-empty, the signal template was preview-only, forbidden claims were absent, and the next phase was interpretation-only.

### Report Inventory

| Report                       |  Rows | Result |
| ---------------------------- | ----: | ------ |
| Equity curve                 | 5,034 | Passed |
| Drawdown curve               | 5,034 | Passed |
| Exposure timeline            | 5,034 | Passed |
| Trade log                    |    44 | Passed |
| Switch event log             |    43 | Passed |
| Money-made/lost table        |     7 | Passed |
| Benchmark comparison         |     3 | Passed |
| Rolling relative performance | 5,034 | Passed |
| Signal-template preview      |    25 | Passed |

### Chart Inventory

| Chart                              | Result |
| ---------------------------------- | ------ |
| Equity curve chart                 | Passed |
| Drawdown curve chart               | Passed |
| Exposure timeline chart            | Passed |
| Rolling relative performance chart | Passed |

### Gate Result

| Gate                                      | Result |
| ----------------------------------------- | ------ |
| Phase 14C passed                          | Passed |
| All required reports present              | Passed |
| Chart files present                       | Passed |
| Report rows non-empty                     | Passed |
| Signal preview is preview-only            | Passed |
| Forbidden claims absent                   | Passed |
| Phase 14E boundary is interpretation-only | Passed |
| Scope blocks forbidden actions            | Passed |
| Audit role is correct                     | Passed |

Phase 14D verdict:

> Phase 14D confirmed the visual artefacts were generated and audited cleanly, but it did not validate the candidate source.

---

## Phase 14E: Visual-Backtest Interpretation and Candidate-Source Identity Audit

Phase 14E checked whether the Phase 14C visual backtest used the intended Phase 6B/6C `loose_relief` execution-realistic overlay.

The intended candidate was:

```text
phase6b_loose_relief_execution_realistic_overlay
```

The Phase 14C resolver had selected:

```text
relative_momentum_outputs.Top 3 Equal Weight Relative Momentum Allocator.allocator_result
```

This did not clearly match the intended candidate. The observed metrics also failed reconciliation against the canonical Phase 6B/6C checkpoint.

### Source Identity Audit

| Item                                             | Result                                                                                      |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Intended candidate system ID                     | `phase6b_loose_relief_execution_realistic_overlay`                                          |
| Selected candidate system ID from route          | `phase6b_loose_relief_execution_realistic_overlay`                                          |
| Resolved Phase 14C source                        | `relative_momentum_outputs.Top 3 Equal Weight Relative Momentum Allocator.allocator_result` |
| Expected candidate fragment found in source name | Failed                                                                                      |
| Suspicious allocator source detected             | True                                                                                        |
| Source identity passed                           | False                                                                                       |
| Source identity failed                           | True                                                                                        |

Interpretation:

> The selected route was correct, but the visual-source resolver did not resolve the intended Phase 6B/6C `loose_relief` stream.

### Metric Reconciliation

| System                                                   | Expected CAGR | Observed CAGR | Expected Calmar | Observed Calmar | Expected Max DD | Observed Max DD | Reconciled |
| -------------------------------------------------------- | ------------: | ------------: | --------------: | --------------: | --------------: | --------------: | ---------: |
| Phase 6B/6C `loose_relief` execution-realistic candidate |        10.35% |         8.94% |           0.429 |           0.250 |         -24.12% |         -35.74% |     Failed |

Interpretation:

> The Phase 14C visualised candidate did not reconcile with the canonical Phase 6B/6C `loose_relief` candidate. The gap was too large to ignore.

### Side-by-Side Comparison

| System                                                     | Source                    |   CAGR | Calmar | Max Drawdown | Final Value |
| ---------------------------------------------------------- | ------------------------- | -----: | -----: | -----------: | ----------: |
| SPY Buy & Hold                                             | Canonical checkpoint      | 10.90% |  0.197 |      -55.19% |           — |
| SPY 12M Momentum                                           | Canonical checkpoint      |  9.68% |  0.287 |      -33.72% |           — |
| Phase 4 `deep_drawdown_guard` execution-realistic baseline | Canonical checkpoint      |  9.93% |  0.412 |      -24.12% |           — |
| Phase 6B/6C `loose_relief` execution-realistic candidate   | Canonical checkpoint      | 10.35% |  0.429 |      -24.12% |   71,779.16 |
| Phase 14C visualised candidate                             | Phase 14C visual backtest |  8.94% |  0.250 |      -35.74% |   55,325.08 |

### Initial Current Signal State

| Item                     | Result                                                 |
| ------------------------ | ------------------------------------------------------ |
| Signal determined        | True                                                   |
| Latest decision date     | 2026-05-01                                             |
| Current mode             | `1.0`                                                  |
| Current exposure         | `0.0`                                                  |
| Current candidate action | `cash_or_defensive_preview`                            |
| Preview only             | True                                                   |
| Paper trading allowed    | False                                                  |
| Live trading allowed     | False                                                  |
| Real money allowed       | False                                                  |
| Data source              | `phase14c_visual_backtest_signal_template_preview.csv` |

Interpretation:

> A preview signal existed, but it came from the wrong/questionable source. It could not be treated as a paper-trading instruction.

### Decision

| Item                                    | Result                                                  |
| --------------------------------------- | ------------------------------------------------------- |
| Decision                                | `source_identity_failed_block_paper_workflow`           |
| Next action                             | `candidate_source_correction_and_visual_rerun_required` |
| Source identity failed                  | True                                                    |
| Metric reconciliation failed            | True                                                    |
| Paper-workflow pre-registration allowed | False                                                   |
| Paper-trading deployment allowed        | False                                                   |
| Paper-trading ready                     | False                                                   |
| Candidate promotion                     | False                                                   |
| Final candidate changed                 | False                                                   |

Phase 14E verdict:

> Phase 14E blocked paper-workflow progression because source identity and metric reconciliation failed.

---

## Phase 14F: Candidate-Source Correction and Re-Run Decision

Phase 14F converted the Phase 14E source-identity failure into a correction requirement.

The decision was:

```text
pre_register_candidate_source_correction_and_visual_rerun
```

Phase 14F did not execute the re-run. It only registered that the intended candidate stream had to be resolved explicitly and re-visualised.

### Correction Decision

| Item                                    | Result                                                                            |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| Decision                                | `pre_register_candidate_source_correction_and_visual_rerun`                       |
| Next phase                              | Phase 14G — candidate-source correction implementation and visual backtest re-run |
| Source identity failed                  | True                                                                              |
| Metric reconciliation failed            | True                                                                              |
| Correction required                     | True                                                                              |
| Visual re-run required                  | True                                                                              |
| Paper-workflow pre-registration allowed | False                                                                             |
| Paper-trading deployment allowed        | False                                                                             |
| Paper-trading ready                     | False                                                                             |
| Live trading allowed                    | False                                                                             |
| Real money allowed                      | False                                                                             |
| Candidate promotion                     | False                                                                             |
| Final candidate changed                 | False                                                                             |

### Correction Specification

| Item                                    | Result                                                 |
| --------------------------------------- | ------------------------------------------------------ |
| Intended candidate system ID            | `phase6b_loose_relief_execution_realistic_overlay`     |
| Required corrected source fragments     | `phase6b`; `loose`; `relief`; `execution`; `realistic` |
| Re-run execution allowed in Phase 14F   | False                                                  |
| Paper workflow pre-registration allowed | False                                                  |

Required corrected visual outputs:

* equity curve vs SPY Buy & Hold;
* drawdown curve;
* exposure / regime timeline;
* trade log;
* switch / event log;
* money-made/lost table;
* benchmark comparison;
* rolling relative performance;
* signal-template preview.

Phase 14F verdict:

> Phase 14F confirmed that the next task was candidate-source correction and visual backtest re-run, not paper-trading workflow pre-registration.

---

## Phase 14I: Phase 6B/6C Candidate Daily Stream Export

Phase 14I exported the intended Phase 6B/6C `loose_relief` execution-realistic candidate as a reusable daily stream.

Exported file:

```text
reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv
```

This fixed the missing-source problem from Phase 14C. Phase 14I used the existing final-candidate reconstruction path and wrote the daily stream under a strict discoverable name.

### Exported Stream

| Item                     |                                                               Result |
| ------------------------ | -------------------------------------------------------------------: |
| Export file              | `reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv` |
| Rows                     |                                                                5,034 |
| Start date               |                                                           2006-04-28 |
| End date                 |                                                           2026-05-01 |
| Required columns present |                                                                 True |
| Export status            |                                                               Passed |

Required exported columns included:

* `decision_date`;
* `strategy_return`;
* `SPY_return`;
* `candidate_equity`;
* `benchmark_equity`;
* `exposure`;
* `mode`;
* `turnover`;
* `applied_overlay_slippage_bps`;
* `overlay_slippage_cost_pct`.

### Export Metrics

| Metric                          |    Observed |
| ------------------------------- | ----------: |
| End value                       | 71,779.1604 |
| CAGR                            |      10.37% |
| Calmar                          |      0.4298 |
| Max drawdown                    |     -24.12% |
| Volatility                      |      13.54% |
| Overlay switch count diagnostic |           0 |

### Metric Reconciliation

| Metric               |  Expected |    Observed | Result                          |
| -------------------- | --------: | ----------: | ------------------------------- |
| End value            | 71,779.16 | 71,779.1604 | Passed                          |
| CAGR                 |    10.35% |      10.37% | Passed                          |
| Calmar               |     0.429 |      0.4298 | Passed                          |
| Max drawdown         |   -24.12% |     -24.12% | Passed                          |
| Overlay switch count |        36 |           0 | Operational diagnostic mismatch |

Interpretation:

> Financial reconciliation passed. The exported stream matches the canonical Phase 6B/6C candidate financially. The switch-count mismatch was treated as an operational paper-workflow issue, not as a financial source-identity failure.

Phase 14I verdict:

> Phase 14I successfully exported the intended Phase 6B/6C `loose_relief` execution-realistic daily candidate stream.

---

## Phase 14J: Exported Candidate Stream Audit

Phase 14J audited the exported Phase 6B/6C daily stream before allowing the corrected visual re-run to use it.

### Gate Result

| Gate                                           | Result |
| ---------------------------------------------- | ------ |
| Export file present                            | Passed |
| Required columns present                       | Passed |
| Financial metrics reconciled                   | Passed |
| Switch count checked as operational diagnostic | Passed |
| Config flags clean                             | Passed |
| Phase 14G boundary is corrected-visual-only    | Passed |
| Scope blocks forbidden actions                 | Passed |
| Audit role is correct                          | Passed |

Phase 14J verdict:

> Phase 14J confirmed that the exported Phase 6B/6C stream was suitable for corrected visual backtest generation.

Important caveat:

> The operational switch-count mismatch remained unresolved and had to be handled later in the paper-workflow branch.

---

## Phase 14G: Corrected Visual Backtest Re-Run

Phase 14G re-ran the visual backtest using the corrected exported Phase 6B/6C `loose_relief` stream.

Corrected source:

```text
reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv
```

This fixed the Phase 14C source problem. The corrected run no longer used the raw relative-momentum allocator stream.

### Corrected Source Resolution

| Item                             | Result                                                                              |
| -------------------------------- | ----------------------------------------------------------------------------------- |
| Corrected source resolved        | True                                                                                |
| Source name                      | `reports\phase6b_loose_relief_execution_realistic_overlay_daily.csv`                |
| Rows                             | 5,034                                                                               |
| Corrected source identity passed | True                                                                                |
| Reason                           | Strict source matched required candidate fragments and required return/date columns |

### Corrected Visual Output Inventory

| Report                       |  Rows | Result |
| ---------------------------- | ----: | ------ |
| Equity curve                 | 5,034 | Passed |
| Drawdown curve               | 5,034 | Passed |
| Exposure timeline            | 5,034 | Passed |
| Trade log                    |     1 | Passed |
| Switch event log             |     0 | Passed |
| Money-made/lost table        |     7 | Passed |
| Benchmark comparison         |     3 | Passed |
| Rolling relative performance | 5,034 | Passed |
| Signal-template preview      |    25 | Passed |
| Current signal state report  |     1 | Passed |

Important caveat:

> The corrected visual backtest now uses the right financial stream, but it still produces only one trade segment and zero switch events. Operational switch reconstruction remained necessary before any real paper workflow could be trusted.

### Corrected Benchmark Comparison

| Series                              | End Value |     CAGR |                   Max Drawdown |  Calmar |
| ----------------------------------- | --------: | -------: | -----------------------------: | ------: |
| Corrected candidate                 | 71,779.16 |   10.37% |                        -24.12% |  0.4298 |
| SPY Buy & Hold                      | 79,572.94 |   10.92% |                        -55.19% |  0.1979 |
| Corrected candidate minus benchmark | -7,793.78 | -0.55 pp | +31.06 pp drawdown improvement | +0.2319 |

Interpretation:

> The corrected candidate still does not beat SPY Buy & Hold on final wealth or CAGR, but it materially improves drawdown and Calmar. It remains a defensive/risk-controlled candidate, not a raw wealth maximiser.

### Corrected Current Signal State

| Item                     | Result            |
| ------------------------ | ----------------- |
| Signal determined        | True              |
| Latest decision date     | 2026-05-01        |
| Current mode             | `offensive_spy`   |
| Current exposure         | 1.0               |
| Current candidate action | `risk_on_preview` |
| Preview only             | True              |
| Paper trading allowed    | False             |
| Live trading allowed     | False             |
| Real money allowed       | False             |

Interpretation:

> The corrected preview signal is `risk_on_preview` as of 2026-05-01. It is not a paper-trading instruction.

### Gate Result

| Gate                                     | Result |
| ---------------------------------------- | ------ |
| Phase 14F passed                         | Passed |
| Correction required from Phase 14F       | Passed |
| Strict source resolution report exists   | Passed |
| Corrected source identity passed         | Passed |
| Corrected visual reports generated       | Passed |
| Current signal state report exists       | Passed |
| Side-by-side comparison report exists    | Passed |
| Phase 14H boundary is audit-only         | Passed |
| No paper workflow/live trading/promotion | Passed |
| Execution role is correct                | Passed |

Phase 14G verdict:

> Phase 14G completed the corrected visual backtest re-run using the intended Phase 6B/6C `loose_relief` stream.

---

## Phase 14H: Corrected Visual-Backtest Audit and Reconciliation Decision

Phase 14H audited the corrected visual backtest outputs and made the reconciliation decision.

### Reconciliation Decision

| Item                                    | Result                                      |
| --------------------------------------- | ------------------------------------------- |
| Decision                                | `allow_paper_workflow_preregistration_next` |
| Corrected source identity passed        | True                                        |
| Metric reconciliation passed            | True                                        |
| Current signal state determined         | True                                        |
| Paper-workflow pre-registration allowed | True                                        |
| Paper-trading deployment allowed        | False                                       |
| Paper trading ready                     | False                                       |
| Live trading allowed                    | False                                       |
| Real money allowed                      | False                                       |
| Candidate promotion                     | False                                       |
| Final candidate changed                 | False                                       |

Interpretation:

> The corrected visual outputs are now good enough to pre-register a paper-trading workflow. This does **not** mean the strategy is paper-trading ready or deployable.

### Gate Result

| Gate                                   | Result |
| -------------------------------------- | ------ |
| Phase 14G passed                       | Passed |
| Config flags clean                     | Passed |
| All corrected reports present          | Passed |
| Chart files present                    | Passed |
| Corrected source identity passed       | Passed |
| Metric reconciliation report exists    | Passed |
| Reconciliation decision report exists  | Passed |
| Current signal state report exists     | Passed |
| No paper workflow if failed            | Passed |
| Phase 15A boundary is conditional-only | Passed |
| Scope blocks forbidden actions         | Passed |
| Audit role is correct                  | Passed |

Phase 14H verdict:

> Phase 14H completed the corrected visual backtest audit and allowed paper-workflow pre-registration as the next bounded step.

Note: Phase labels follow the actual implementation/checkpoint history. Phase 14I/14J were added to export and audit the corrected candidate stream before the corrected Phase 14G/14H visual re-run was finalised.

## Phase 14 Final Verdict

| Area                               | Result           | Interpretation                                                                                   |
| ---------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------ |
| Initial visual-report generation   | Completed        | The reporting pipeline could generate the required artefacts                                     |
| Initial candidate-source identity  | Failed           | The resolver selected a relative-momentum allocator rather than the intended final overlay       |
| Initial metric reconciliation      | Failed           | The observed 8.94% CAGR and -35.74% drawdown did not match the canonical candidate               |
| Wrong-source outputs               | Rejected         | They were retained as audit history but excluded from paper-workflow use                         |
| Explicit Phase 6B/6C stream export | Passed           | The intended `loose_relief` daily financial stream was made discoverable                         |
| Corrected financial reconciliation | Passed           | End value, CAGR, Calmar, and max drawdown matched the canonical checkpoint within tolerance      |
| Corrected visual reports           | Passed           | The intended candidate was visualised against SPY Buy & Hold                                     |
| Operational switch reconstruction  | Still unresolved | The corrected stream produced zero reconstructed switches despite 36 expected canonical switches |
| Paper-workflow pre-registration    | Allowed          | The next bounded phase could define the workflow                                                 |
| Paper-trading deployment           | Blocked          | Source reconciliation alone was insufficient for operational execution                           |

Final Phase 14 interpretation:

> Phase 14 successfully corrected and visualised the intended ETF candidate, but it also demonstrated that financial reconciliation and operational replay are separate requirements.

The financial stream showed the correct historical return path:

```text id="n70xme"
End value: approximately $71,779
CAGR: approximately 10.35%–10.37%
Calmar: approximately 0.429
Max drawdown: approximately -24.12%
```

However, the exported daily stream did not yet expose the final executable switch semantics required for a trustworthy paper workflow.

The correct conclusion was:

> The project had a financially reconciled candidate and reliable visual reporting, but it still needed an independently reconstructed operational switch history and a genuinely fresh post-endpoint signal.

---

# Phase 15: Paper-Trading Workflow and Operational Readiness

Phase 15 began the transition from historical strategy reporting into operational paper-trading infrastructure.

The phase did not assume that a validated backtest was automatically executable. Instead, it required the project to reconstruct the exact operational decisions that would have been made and to generate fresh signals without contaminating the pinned historical checkpoint.

The principal questions were:

1. Can the final candidate produce an explainable and reproducible switch history?
2. Can the canonical 36 overlay switches be reconstructed from the correct executable decision field?
3. Can fresh market data be processed beyond the pinned `2026-05-01` endpoint without mutating canonical reports?
4. Can the actual Phase 6B/6C rule logic generate post-endpoint candidate rows?
5. Can a current signal be audited for freshness, provenance, and benchmark consistency?
6. Can paper workflow proceed without guessed weights, manual signal invention, or stale historical state?

The Phase 15 sequence deliberately preserved failed operational attempts because each failure identified a different semantic problem:

```text id="rdfgss"
15A–15B: pre-register the workflow and confirm readiness is blocked
15C–15D: attempt initial switch and signal reconstruction
15E–15F: attribute the missing switch source and define fresh-data controls
15G–15H: reject an incorrect 92-switch reconstruction
15I–15J: reconstruct the correct 36-switch operational history
Later Phase 15 work: generate, hand off, and audit a post-endpoint rule-engine stream
```

The Phase 15 blocking states documented below are **historical checkpoint decisions**. They describe what the system knew at each subphase and should not be interpreted as the project’s current overall status.

The major Phase 15 achievements were eventually:

* reconstruction of the canonical 36-switch operational history;
* preservation of the fixed `2026-05-01` research endpoint;
* separation of fresh data from canonical historical reports;
* rerunning the existing Phase 6B/6C rule logic on a fresh-data extension;
* generation of a valid post-endpoint candidate stream;
* explicit rejection of guessed, manually filled, or carry-forward-only target weights.

At the end of the Phase 15 work described by this historical branch, downstream fresh-signal consumption and audit still remained necessary before paper dry-run progression.

Later project phases subsequently extended this operational foundation into manual paper-session tracking. Those later developments do not change the validity of the blockers recorded at their original Phase 15 checkpoints.

---

## Phase 15A: Paper-Trading Workflow Pre-Registration

Phase 15A pre-registered the paper-trading workflow requirements after Phase 14H allowed workflow pre-registration.

It did not deploy paper trading, integrate with a broker/API, run live trading, use real money, claim paper-trading readiness, or change the final candidate.

### Operational Switch Policy

| Item                                                 | Result |
| ---------------------------------------------------- | -----: |
| Expected canonical switch count                      |     36 |
| Exported switch count observed                       |      0 |
| Switch count reconciled                              |  False |
| Switch reconstruction required before readiness      |   True |
| Switch event log required before readiness           |   True |
| Explainable trade segments required before readiness |   True |

Interpretation:

> The corrected financial stream reconciled with canonical Phase 6B/6C metrics, but the operational switch mechanics were not yet reconstructed.

### Endpoint Freshness Policy

| Item                                    |     Result |
| --------------------------------------- | ---------: |
| Audit current date                      | 2026-06-02 |
| Canonical backtest endpoint             | 2026-05-01 |
| Latest signal date                      | 2026-05-01 |
| Signal staleness                        |    32 days |
| Maximum allowed staleness for readiness |     3 days |
| Signal stale for readiness              |       True |
| Blocks paper-trading readiness          |       True |

Important distinction:

> The 2026-05-01 endpoint is not a flaw in the research baseline. It is the fixed canonical endpoint. It simply cannot be treated as a current executable paper-trading signal.

### Daily Signal File Schema

The registered daily signal file requires:

```text
signal_date
data_as_of_date
candidate_system_id
signal_source_file
current_mode
current_exposure
target_action
previous_mode
previous_exposure
switch_triggered
switch_reason
paper_trading_allowed
paper_readiness_status
blocking_warnings
benchmark_spy_close_or_return_source
generated_at_utc
```

### Execution Checklist

Required checks:

* confirm signal file generated today;
* confirm data-as-of date is current;
* confirm switch reconstruction is available;
* confirm no live or real-money order;
* confirm paper account only;
* confirm current signal is not preview-only;
* confirm stop conditions are not triggered;
* confirm manual entry is logged;
* confirm benchmark snapshot is updated.

### Stop Conditions

Paper workflow must stop if:

* signal file is missing or stale;
* switch reconstruction is missing;
* exposure or mode is missing;
* data source changes without review;
* drawdown exceeds predefined threshold;
* strategy deviates from expected candidate stream;
* manual execution error occurs;
* broker or paper-platform mismatch occurs;
* unexpected live-money risk appears.

### Failure Conditions Triggered Immediately

| Failure Condition                       | Triggered Now | Blocks Readiness | Required Repair                                         |
| --------------------------------------- | ------------: | ---------------: | ------------------------------------------------------- |
| Operational switch mechanics unresolved |          True |             True | Reconstruct/validate expected operational switches      |
| Latest signal not current               |          True |             True | Generate current signal from fresh data                 |
| Signal preview only                     |          True |             True | Create audited paper signal file after readiness passes |

Phase 15A verdict:

> Phase 15A completed paper-trading workflow pre-registration, but paper trading remained blocked.

---

## Phase 15B: Paper-Trading Workflow Readiness Audit

Phase 15B audited whether the pre-registered workflow was ready for execution.

The correct decision was to block readiness.

### Operational Blockers

| Blocker                                 | Present | Blocks Readiness | Result   |
| --------------------------------------- | ------: | ---------------: | -------- |
| Operational switch mechanics unresolved |    True |             True | Blocking |
| Endpoint signal not current             |    True |             True | Blocking |
| Failure conditions triggered            |    True |             True | Blocking |

### Readiness Decision

| Item                             | Result                                                         |
| -------------------------------- | -------------------------------------------------------------- |
| Decision                         | `paper_trading_readiness_blocked_operational_repairs_required` |
| Paper trading ready              | False                                                          |
| Paper-trading deployment allowed | False                                                          |
| Broker/API integration allowed   | False                                                          |
| Live trading allowed             | False                                                          |
| Real money allowed               | False                                                          |
| Candidate promotion              | False                                                          |
| Final candidate changed          | False                                                          |

Phase 15B verdict:

> Phase 15B completed the paper-trading workflow readiness audit with readiness blocked.

Correct interpretation:

> The workflow existed on paper, but the system was not operationally executable yet.

---

## Phase 15C–15D: First Operational Switch and Signal-Reconstruction Attempt

Phases 15C and 15D attempted to resolve the operational blockers from Phase 15B.

They generated switch and current-signal output files, but both key blockers remained unresolved.

### Phase 15C Switch Source Inventory

| Source                                                                    | Candidate Rows | Distance to Expected 36 Switches | Selected |
| ------------------------------------------------------------------------- | -------------: | -------------------------------: | -------: |
| Exported daily stream mode/exposure changes                               |              0 |                               36 |     True |
| `reports/regime_switch_overlay_offensive_relief_changed_switch_audit.csv` |             94 |                               58 |    False |
| `reports/phase14g_corrected_visual_switch_event_log.csv`                  |              0 |                               36 |    False |
| `reports/regime_switch_overlay_guarded_switch_event_summary.csv`          |              0 |                               36 |    False |
| `reports/regime_switch_overlay_offensive_relief_event_summary.csv`        |              0 |                               36 |    False |

### Phase 15C Switch Reconstruction Summary

| Item                          | Result |
| ----------------------------- | -----: |
| Expected switch count         |     36 |
| Reconstructed switch count    |      0 |
| Switch-count tolerance        |      2 |
| Switch count reconciled       |  False |
| Switch signal validity passed |  False |

### Phase 15C Current Signal File

| Item                | Result                                                               |
| ------------------- | -------------------------------------------------------------------- |
| Signal date         | 2026-06-02                                                           |
| Data as-of date     | 2026-05-01                                                           |
| Candidate system ID | `phase6b_loose_relief_execution_realistic_overlay`                   |
| Current mode        | `offensive_spy`                                                      |
| Data source         | `reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv` |

### Phase 15C Freshness Result

| Item                           |     Result |
| ------------------------------ | ---------: |
| Audit current date             | 2026-06-02 |
| Data as-of date                | 2026-05-01 |
| Canonical backtest endpoint    | 2026-05-01 |
| Signal staleness               |    32 days |
| Maximum allowed staleness      |     3 days |
| Data beyond canonical endpoint |      False |
| Signal freshness passed        |      False |

### Phase 15D Decision

| Item                                        | Result                                  |
| ------------------------------------------- | --------------------------------------- |
| Decision                                    | `blocked_both_switch_and_signal_failed` |
| Switch reconstruction passed                | False                                   |
| Current signal freshness passed             | False                                   |
| Current signal validity passed              | False                                   |
| Paper dry-run pre-registration allowed next | False                                   |
| Paper trading ready                         | False                                   |

Phase 15C/15D verdict:

> The first operational reconstruction attempt failed. The project had neither a valid 36-switch operational history nor a fresh current signal.

---

## Phase 15E–15F: Switch-Source Attribution and Fresh-Data Extension Specification

### Phase 15E: Operational Switch Source Attribution

Phase 15E investigated whether the true 36-switch operational event history already existed in current reports.

### Candidate Switch Source Inventory

| Source                                                                    |  Rows | Expected Switch Count | Count Reconciled | Classification                               |
| ------------------------------------------------------------------------- | ----: | --------------------: | ---------------: | -------------------------------------------- |
| `reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv`      | 5,034 |                    36 |            False | Financial daily stream, not final switch log |
| `reports/regime_switch_overlay_offensive_relief_changed_switch_audit.csv` |    94 |                    36 |            False | Intermediate changed-switch diagnostic       |
| `reports/regime_switch_overlay_offensive_relief_event_summary.csv`        |     4 |                    36 |            False | Summary file                                 |
| `reports/regime_switch_overlay_guarded_switch_event_summary.csv`          |     4 |                    36 |            False | Summary file                                 |
| `reports/phase14g_corrected_visual_switch_event_log.csv`                  |     0 |                    36 |            False | Empty generated switch log                   |
| `reports/phase15c_operational_switch_event_log.csv`                       |     0 |                    36 |            False | Empty generated switch log                   |

### Phase 15E Decision

| Item                                            | Result                                           |
| ----------------------------------------------- | ------------------------------------------------ |
| Decision                                        | `true_36_switch_source_not_found_patch_required` |
| True 36-switch source found                     | False                                            |
| Changed-switch audit rows                       | 94                                               |
| Changed-switch audit classified as intermediate | True                                             |
| Source-code patch required                      | True                                             |
| Paper dry-run allowed                           | False                                            |
| Paper trading ready                             | False                                            |

Correct interpretation:

> The 94-row changed-switch file was correctly rejected. The true final operational switch history was not exported yet.

---

### Phase 15F: Fresh Data Extension Pre-Registration

Phase 15F pre-registered how fresh data should be added beyond the pinned endpoint without mutating canonical research outputs.

### Baseline Protection Policy

| Policy                                      | Result |
| ------------------------------------------- | ------ |
| Preserve pinned research reports            | True   |
| Preserve Phase 6B canonical metrics         | True   |
| No mutation of historical backtest outputs  | True   |
| Fresh data labelled out-of-sample extension | True   |

### Fresh Data Source Policy

| Policy                     | Result                                   |
| -------------------------- | ---------------------------------------- |
| Allowed primary source     | `existing_project_market_data_pipeline`  |
| Allowed fallback source    | `manual_fresh_spy_ohlcv_file`            |
| Minimum required fields    | `date`, `SPY_close`, `SPY_return`        |
| Require data beyond endpoint | True                                   |
| Require data-as-of date field | True                                  |
| Require source timestamp field | True                                 |
| Silent forward-fill beyond latest real date | Forbidden               |

### Future Current Signal Schema

Future signal file:

```text
reports/phase15g_current_signal_file.csv
```

Future audit file:

```text
reports/phase15h_current_signal_freshness_audit.csv
```

Maximum signal staleness:

```text
3 days
```

Phase 15F verdict:

> Phase 15F completed fresh data extension pre-registration. Fresh current-signal generation was allowed later, but only after the switch blocker was resolved.

---

## Phase 15G–15H: Failed Switch Log Export Attempt

Phase 15G attempted to export the true final operational switch log.

It created a switch-log-shaped file, but the result was wrong.

### Column Selection

| Column Role                | Selected Column                |
| -------------------------- | ------------------------------ |
| Date column                | `date`                         |
| Mode column                | `position`                     |
| Exposure column            | Missing                        |
| Turnover column            | `turnover`                     |
| Slippage bps column        | `applied_overlay_slippage_bps` |
| Slippage cost column       | Missing                        |
| Raw signal column          | Missing                        |
| Confirmed signal column    | Missing                        |
| Deep drawdown guard column | Missing                        |
| Loose relief column        | Missing                        |

Interpretation:

> Phase 15G selected noisy `position` and `turnover` semantics instead of the final executable allocation column.

### Exported Switch Log

| Item                       | Result |
| -------------------------- | -----: |
| Expected switch count      |     36 |
| Reconstructed switch count |     92 |
| Switch-count tolerance     |      2 |
| Switch count reconciled    |  False |
| Source file written        |   True |
| Required columns present   |   True |
| Paper dry-run allowed      |  False |
| Paper trading ready        |  False |

Correct interpretation:

> A 92-row reconstruction is not the true final 36-switch history.

### Phase 15H Decision

| Item                                   | Result                                  |
| -------------------------------------- | --------------------------------------- |
| Decision                               | `blocked_true_switch_log_export_failed` |
| Switch log reconciled                  | False                                   |
| Fresh signal generation allowed next   | False                                   |
| Paper dry-run pre-registration allowed | False                                   |
| Paper trading ready                    | False                                   |

Phase 15G/15H verdict:

> The switch-log export attempt failed because the switch definition was semantically wrong.

---

## Phase 15I–15J: Correct 36-Switch Operational Reconstruction

Phases 15I and 15J corrected the semantic error in the earlier switch-log attempts.

The earlier reconstruction had treated noisy position or turnover changes as final overlay decisions, producing 92 events instead of the expected 36.

The key correction was identifying the final executable allocation field:

```text id="m6lgbm"
target_offensive_weight
```

This field represented the candidate’s final offensive allocation decision after the applicable confirmation, guard, and relief logic had been resolved.

It was therefore the correct source for reconstructing transitions between:

```text id="m12jbi"
offensive SPY mode
defensive allocator mode
```

The corrected reconstruction was required to:

* produce the expected 36 canonical switches;
* preserve exact decision-date ordering;
* retain previous and new mode;
* retain previous and new exposure;
* identify whether a switch occurred;
* preserve the underlying decision lineage;
* avoid interpreting ordinary turnover as an overlay regime switch;
* remain separate from the candidate’s financial-return reconciliation.

This distinction was essential:

> Financial returns establish what the candidate earned; the operational switch log establishes what the paper workflow would have been instructed to do.

---

## Phase 15I: Final Candidate Column Semantics / Switch Definition Diagnostic

### Column Profile

| Column                         | Present | Semantic Interpretation                         | Unique Values | Min |  Max |
| ------------------------------ | ------: | ----------------------------------------------- | ------------: | --: | ---: |
| `position`                     |    True | Mode/position-state candidate but noisy         |             9 | 0.0 |  1.0 |
| `cash_position`                |    True | Allocation-weight candidate but noisy           |             9 | 0.0 |  1.0 |
| `offensive_weight`             |    True | Allocation-weight candidate                     |             2 | 0.0 |  1.0 |
| `defensive_weight`             |    True | Allocation-weight candidate                     |             2 | 0.0 |  1.0 |
| `target_offensive_weight`      |    True | Final target allocation candidate               |             2 | 0.0 |  1.0 |
| `target_defensive_weight`      |    True | Final target allocation candidate               |             2 | 0.0 |  1.0 |
| `turnover`                     |    True | Execution attribute, not switch definition      |             9 | 0.0 |  2.0 |
| `applied_overlay_slippage_bps` |    True | Execution-cost attribute, not switch definition |             4 | 5.0 | 50.0 |

### Candidate Switch Definitions

| Candidate Column          | Transform          | Candidate Switch Count | Count Reconciled | Valid Exposure Range |
| ------------------------- | ------------------ | ---------------------: | ---------------: | -------------------: |
| `target_offensive_weight` | direct             |                     36 |             True |                 True |
| `offensive_weight`        | direct             |                     36 |             True |                 True |
| `target_defensive_weight` | inverse            |                     36 |             True |                 True |
| `defensive_weight`        | inverse            |                     36 |             True |                 True |
| `cash_position`           | inverse            |                     54 |            False |                 True |
| `position`                | fallback mode-like |                     54 |            False |                 True |

### Selected Switch Definition

| Item                   | Result                                                 |
| ---------------------- | ------------------------------------------------------ |
| Selected column        | `target_offensive_weight`                              |
| Transform              | direct                                                 |
| Candidate switch count | 36                                                     |
| Count reconciled       | True                                                   |
| Selection reason       | `eligible_reconciled_final_target_exposure_definition` |

Phase 15I verdict:

> Phase 15I identified `target_offensive_weight` as the correct executable allocation column.

---

## Phase 15J: Refined 36-Switch Reconstruction Implementation + Audit

Phase 15J reconstructed the final operational switch log using direct changes in `target_offensive_weight`.

Exported file:

```text
reports/phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv
```

### Reconstruction Method

| Item                            | Result                              |
| ------------------------------- | ----------------------------------- |
| Date column                     | `date`                              |
| Final target exposure column    | `target_offensive_weight`           |
| Final target exposure transform | direct                              |
| Turnover column                 | `turnover`                          |
| Slippage bps column             | `applied_overlay_slippage_bps`      |
| Switch trigger                  | Final target allocation change only |
| Turnover used as switch trigger | False                               |

### Reconstructed Switch Log

| Item                           | Result     |
| ------------------------------ | ---------- |
| First switch date              | 2007-08-17 |
| Last switch date               | 2026-04-13 |
| Dates after canonical endpoint | 0          |
| Canonical endpoint             | 2026-05-01 |

The last two switches before the pinned endpoint were:

| Switch Event | Date       | Previous Mode       | Current Mode        | Transition    |
| -----------: | ---------- | ------------------- | ------------------- | ------------- |
|           35 | 2026-03-25 | `offensive_spy`     | `defensive_or_cash` | Risk decrease |
|           36 | 2026-04-13 | `defensive_or_cash` | `offensive_spy`     | Risk increase |

### Refined Switch Summary

| Item                                 | Result |
| ------------------------------------ | -----: |
| Expected switch count                |     36 |
| Reconstructed switch count           |     36 |
| Switch-count tolerance               |      2 |
| Switch count reconciled              |   True |
| Decision dates populated             |   True |
| Previous/current exposure meaningful |   True |
| Transition types populated           |   True |
| Turnover fields coherent             |   True |
| Slippage fields coherent             |   True |
| Signal validity passed               |   True |
| Fresh signal phase allowed next      |   True |
| Paper dry-run allowed                |  False |
| Paper trading ready                  |  False |

### Decision

| Item                                   | Result                                                                    |
| -------------------------------------- | ------------------------------------------------------------------------- |
| Decision                               | `refined_canonical_switch_log_reconciled_fresh_signal_phase_allowed_next` |
| Refined switch log reconciled          | True                                                                      |
| Fresh signal generation allowed next   | True                                                                      |
| Paper dry-run pre-registration allowed | False                                                                     |
| Paper trading ready                    | False                                                                     |

Phase 15J verdict:

> Phase 15J solved the canonical historical switch-log problem. The true 36-switch operational history is now reconstructed and reconciled.

---

## Phase 15K–15L: Endpoint Signal Consistency and Fresh-Signal Pre-Implementation Check

### Phase 15K: Pinned-Endpoint Operational Signal Consistency Audit

Phase 15K checked whether the pinned 2026-05-01 endpoint signal matched the reconstructed switch log.

### Pinned Endpoint Signal

| Item                             | Result                                             |
| -------------------------------- | -------------------------------------------------- |
| Endpoint date                    | 2026-05-01                                         |
| Candidate system ID              | `phase6b_loose_relief_execution_realistic_overlay` |
| Latest reconstructed switch date | 2026-04-13                                         |
| Latest switch previous mode      | `defensive_or_cash`                                |
| Latest switch current mode       | `offensive_spy`                                    |
| Latest switch previous exposure  | 0.0                                                |
| Latest switch current exposure   | 1.0                                                |
| Endpoint mode                    | `offensive_spy`                                    |
| Endpoint exposure                | 1.0                                                |
| Preview-only                     | True                                               |
| Paper dry-run allowed            | False                                              |
| Paper trading allowed            | False                                              |
| Signal consistency passed        | True                                               |

Correct interpretation:

> The pinned endpoint signal is internally consistent. The final switch before the endpoint was the 2026-04-13 move back to `offensive_spy`.

Important endpoint rule:

> 2026-05-01 remains the fixed canonical research endpoint. It is not a flaw. It simply cannot be treated as a current paper-trading signal.

Phase 15K verdict:

> Phase 15K completed the pinned-endpoint operational signal consistency audit.

---

### Phase 15L: Fresh Data Extension / Current Signal Generation Pre-Implementation Check

Phase 15L checked whether the project was ready to generate a bounded post-endpoint current signal.

### Schema Fix

The future current-signal schema now includes:

```text
benchmark_update_flag
```

| Item                        | Result |
| --------------------------- | -----: |
| Required columns            |     23 |
| Present columns             |     23 |
| Missing columns             |   None |
| Current signal schema ready |   True |

### Decision

| Item                                         | Result                                         |
| -------------------------------------------- | ---------------------------------------------- |
| Decision                                     | `fresh_current_signal_generation_allowed_next` |
| Fresh current-signal generation allowed next | True                                           |
| Data pull executed                           | False                                          |
| Current signal generated                     | False                                          |
| Paper dry-run allowed                        | False                                          |
| Paper trading ready                          | False                                          |
| Broker/API integration allowed               | False                                          |

Phase 15L verdict:

> Phase 15L allowed bounded fresh current-signal generation as a separate post-endpoint extension.

---

## Phase 15M–15N: Fresh Current Signal Attempt and Audit

Phases 15M and 15N attempted to generate and audit a fresh current signal.

The machinery worked, but the result failed because there were still no post-endpoint candidate rows.

### Phase 15M Current Signal File

| Item                         | Result                                             |
| ---------------------------- | -------------------------------------------------- |
| Signal date                  | 2026-06-02                                         |
| Data as-of date              | Missing                                            |
| Candidate system ID          | `phase6b_loose_relief_execution_realistic_overlay` |
| Data source                  | `in_memory_final_candidate_frame`                  |
| Pinned research endpoint     | 2026-05-01                                         |
| Output file written          | True                                               |
| Canonical endpoint preserved | True                                               |
| Out-of-sample label present  | True                                               |
| Canonical report mutation    | False                                              |

### Phase 15M Generation Summary

| Item                        |                    Result |
| --------------------------- | ------------------------: |
| Post-endpoint rows          |                         0 |
| Selected exposure column    | `target_offensive_weight` |
| Selected exposure transform |                    direct |
| Signal file generated       |                      True |
| Is out-of-sample extension  |                      True |
| Signal validity passed      |                     False |
| Data freshness passed       |                     False |
| Benchmark update passed     |                     False |
| Paper dry-run allowed       |                     False |
| Paper trading ready         |                     False |

Correct interpretation:

> The current-signal machinery wrote a signal-shaped file, but no real fresh signal existed because the final candidate frame still ended at 2026-05-01.

### Phase 15N Fresh Signal Audit

| Check                           | Result |
| ------------------------------- | -----: |
| Post-endpoint data passed       |  False |
| Signal validity passed          |  False |
| Data freshness passed           |  False |
| Benchmark update passed         |  False |
| Switch context present          |   True |
| All current-signal gates passed |  False |

Failure reason:

```text
not_post_endpoint_data;signal_validity_failed;data_freshness_failed;benchmark_update_failed
```

### Phase 15N Decision

| Item                                        | Result                              |
| ------------------------------------------- | ----------------------------------- |
| Decision                                    | `blocked_fresh_signal_audit_failed` |
| Paper dry-run pre-registration allowed next | False                               |
| Paper trading ready                         | False                               |
| Broker/API integration allowed              | False                               |
| Paper-trading deployment allowed            | False                               |
| Live trading allowed                        | False                               |
| Real money allowed                          | False                               |

Phase 15M/15N verdict:

> Fresh-signal generation failed substantively because there were no post-endpoint candidate rows.

---

## Phase 15Q–15R: Post-Endpoint Candidate Source Creation and Validation

Phases 15Q and 15R attempted to create or validate a real post-endpoint candidate source.

They correctly preserved the canonical baseline but still found no valid source.

### Phase 15Q Creation Summary

| Item                        | Result                |
| --------------------------- | --------------------- |
| Post-endpoint rows          | 0                     |
| Source type                 | `no_source_available` |
| Source path                 | Missing               |
| Benchmark update passed     | False                 |
| Target weight source passed | False                 |
| Stream row validity passed  | False                 |
| Out-of-sample label passed  | False                 |
| Candidate stream valid      | False                 |
| Canonical report mutation   | False                 |
| Handoff file written        | False                 |

The blocked output retained the required schema:

```text
date
SPY_close
SPY_return
target_offensive_weight
current_mode
current_exposure
previous_mode
previous_exposure
switch_triggered
data_source
data_source_timestamp
target_weight_source
target_weight_source_valid_flag
pinned_research_endpoint
is_out_of_sample_extension
benchmark_update_flag
stream_row_validity_flag
blocking_warnings
```

Phase 15Q verdict:

> Phase 15Q confirmed that no valid post-endpoint candidate source was currently available.

---

### Phase 15R Real Source Validation

| Check                           | Result |
| ------------------------------- | -----: |
| Post-endpoint rows              |      0 |
| Post-endpoint rows passed       |  False |
| All dates after endpoint passed |  False |
| Benchmark update passed         |  False |
| Target weight source passed     |  False |
| Target exposure present passed  |  False |
| Target exposure range passed    |  False |

### Phase 15R Decision

| Item                                        | Result                                      |
| ------------------------------------------- | ------------------------------------------- |
| Decision                                    | `blocked_real_post_endpoint_source_invalid` |
| Phase 15O/15P rerun allowed next            | False                                       |
| Phase 15M/15N rerun allowed next            | False                                       |
| Paper dry-run pre-registration allowed next | False                                       |
| Paper trading ready                         | False                                       |

Phase 15R verdict:

> The audit passed because it correctly blocked progression. The missing item was not another audit. The missing item was a real rule-generated post-endpoint stream.

---

## Phase 15S–15T: Rule-Replay Source Discovery and Export Attempt

Phases 15S and 15T investigated whether the Phase 6B/6C rule-output path could generate post-endpoint candidate rows.

The critical finding:

> `_find_final_candidate_frame` exposes the historical final candidate output, but it does not replay the Phase 6B/6C rule logic on fresh post-endpoint data.

---

## Phase 15S: Rule Replay Source Discovery

Phase 15S searched the codebase and final candidate output to identify the source path needed to compute `target_offensive_weight` after the pinned endpoint.

### Relevant Code Path Candidates

Relevant files included:

```text
src\market_strats\strategies\regime_switch_overlay.py
src\market_strats\analysis\phase6b_candidate_stream_export.py
src\market_strats\analysis\regime_switch_overlay_offensive_relief_validation.py
src\market_strats\analysis\bid_ask_market_impact_diagnostic.py
src\market_strats\analysis\true_switch_log_export.py
src\market_strats\analysis\refined_switch_reconstruction.py
src\market_strats\run_backtest.py
```

### Final Candidate Profile

| Item                              |      Result |
| --------------------------------- | ----------: |
| Frame loaded                      |        True |
| Rows                              |       5,034 |
| Date column                       |      `date` |
| Min date                          |  2006-04-28 |
| Max date                          |  2026-05-01 |
| Post-endpoint rows                |           0 |
| `target_offensive_weight` present |        True |
| Benchmark column                  | `adj_close` |
| Benchmark column present          |        True |

### Target Column Discovery

| Target Column             | Present in Final Candidate Frame | Code Paths with Column |
| ------------------------- | -------------------------------: | ---------------------: |
| `target_offensive_weight` |                             True |                      5 |
| `target_defensive_weight` |                             True |                      5 |
| `offensive_weight`        |                             True |                      6 |
| `defensive_weight`        |                             True |                      6 |

### Replay Requirement Report

| Question                                             | Answer                                          |
| ---------------------------------------------------- | ----------------------------------------------- |
| Which function exposes `target_offensive_weight`?    | `_find_final_candidate_frame` output exposes it |
| Does replay require only SPY data?                   | False                                           |
| Does replay require full relative-momentum outputs?  | True                                            |
| Can replay run without mutating the pinned baseline? | True                                            |
| Post-endpoint rows available now                     | 0                                               |
| Replay path discovered                               | True                                            |

### Decision

| Item                                        | Result                                                    |
| ------------------------------------------- | --------------------------------------------------------- |
| Decision                                    | `rule_replay_path_discovered_export_attempt_allowed_next` |
| Rule replay path discovered                 | True                                                      |
| Post-endpoint rows available now            | 0                                                         |
| Phase 15T export attempt allowed next       | True                                                      |
| Phase 15Q/15R rerun allowed next            | False                                                     |
| Paper dry-run pre-registration allowed next | False                                                     |
| Paper trading ready                         | False                                                     |

Phase 15S verdict:

> Phase 15S found the historical final-candidate output path, but not a reusable post-endpoint replay engine.

---

## Phase 15T: Post-Endpoint Rule-Generated Candidate Stream Export Attempt

Phase 15T attempted to export a post-endpoint rule-generated candidate stream using the discovered final-candidate output path.

Intended output files:

```text
reports/phase15t_rule_generated_candidate_stream.csv
data/fresh/phase15q_rule_generated_candidate_stream.csv
```

The handoff file was not written because no valid post-endpoint rows existed.

### Export Summary

| Item                        |                        Result |
| --------------------------- | ----------------------------: |
| Post-endpoint rows          |                             0 |
| Candidate loader            | `_find_final_candidate_frame` |
| Benchmark update passed     |                         False |
| Stream row validity passed  |                         False |
| Target weight source passed |                         False |
| Out-of-sample label passed  |                         False |
| Rule-generated stream valid |                         False |
| Canonical report mutation   |                         False |

### Decision

| Item                                        | Result                                                 |
| ------------------------------------------- | ------------------------------------------------------ |
| Decision                                    | `blocked_rule_generated_stream_unavailable_or_invalid` |
| Phase 15Q/15R rerun allowed next            | False                                                  |
| Phase 15O/15P rerun allowed next            | False                                                  |
| Phase 15M/15N rerun allowed next            | False                                                  |
| Paper dry-run pre-registration allowed next | False                                                  |
| Paper trading ready                         | False                                                  |

Phase 15T verdict:

> Phase 15T correctly blocked progression. The project has discovered the historical rule-output path, but it still has not exposed a true post-endpoint rule-replay engine.

---

---

## Phase 15WXYZ: Fresh Extension Rule-Replay Breakthrough

Phase 15WXYZ resolved the blocker identified in Phase 15T.

The key discovery was that the true Phase 6B/6C target-weight engine was not a static mapper from the pinned historical final-candidate frame. The actual replay logic lives in:

```text
src/market_strats/strategies/regime_switch_overlay.py
```

The key function is:

```text
run_spy_trend_regime_switch_overlay(...)
```

This function computes the executable target allocation through:

```text
target_use_defensive = signal_use_defensive.shift(1)
target_defensive_weight = target_use_defensive.astype(float)
target_offensive_weight = 1.0 - target_defensive_weight
```

Correct interpretation:

> `_find_final_candidate_frame` exposes the pinned historical final candidate, but the fresh extension must rerun the actual project rule engine on extended data.

### Fresh Extension Method

Phase 15WXYZ used the correct bounded replay route:

```text
1. Clone the config.
2. Preserve the canonical 2026-05-01 endpoint in the original config.
3. Remove or extend research_period.end_date only inside the fresh clone.
4. Rerun the existing project pipeline on extended data in a separate fresh reports folder.
5. Extract the fresh final candidate through the existing final-candidate discovery path.
6. Export only rows after the pinned 2026-05-01 endpoint.
```

This preserved the canonical research baseline while creating a separate post-endpoint extension.

### Fresh Extension Result

| Item                           | Result                                                    |
| ------------------------------ | --------------------------------------------------------- |
| Post-endpoint rows             | 8                                                         |
| Fresh final candidate max date | 2026-05-13                                                |
| Rule-generated stream valid    | True                                                      |
| Handoff file written           | True                                                      |
| Decision                       | `phase15q_15r_rerun_allowed_next`                         |
| Handoff file                   | `data/fresh/phase15q_rule_generated_candidate_stream.csv` |

The exported fresh stream covered:

```text
2026-05-04 to 2026-05-13
```

### Signal Price Correction

The first fresh export had a semantic bug: `SPY_close` values were around `71,000` because the overlay output's `adj_close` column represented strategy equity rather than SPY price.

This was corrected so the export uses:

```text
signal_price
```

as the SPY/proxy price field.

Corrected SPY/proxy values were around:

```text
718–742
```

### Phase 15WXYZ Verdict

> Phase 15WXYZ solved the fresh-extension generation blocker. A real rule-generated post-endpoint candidate stream now exists.

Important limitation:

> This does not make the project paper-trading ready. The downstream Phase 15Q/15R/15O/15P/15M/15N chain still has to consume, validate, and audit the fresh handoff file before any paper dry-run can be considered.

---

## Phase 15 Current Bottom Line

Phase 15 resolved the two main operational problems inherited from Phase 14:

1. reconstructing the final candidate’s executable switch history;
2. generating a genuine post-endpoint candidate stream without mutating the pinned historical checkpoint.

The phase established that:

| Area                                 | Phase 15 Result                          |
| ------------------------------------ | ---------------------------------------- |
| Correct Phase 6B/6C financial stream | Solved                                   |
| Correct visual-backtest source       | Solved                                   |
| Canonical historical switch history  | Reconstructed: 36 switches               |
| Correct executable switch field      | `target_offensive_weight`                |
| Pinned endpoint consistency          | Passed                                   |
| Fresh-signal schema                  | Completed                                |
| Historical-frame replay limitation   | Diagnosed                                |
| Fresh rule-engine replay             | Implemented                              |
| Post-endpoint candidate rows         | Generated                                |
| Canonical endpoint mutation          | Prevented                                |
| Fresh handoff file                   | Written                                  |
| Immediate paper deployment           | Still blocked at the Phase 15 checkpoint |

The key architectural distinction was:

> `_find_final_candidate_frame` exposes the pinned historical candidate, whereas a genuine fresh extension requires rerunning the actual Phase 6B/6C strategy engine on newly available data.

Phase 15WXYZ therefore used a bounded fresh-extension process:

```text id="5wrsxj"
1. Preserve the canonical configuration and 2026-05-01 endpoint.
2. Create a separate fresh-data configuration clone.
3. Rerun the existing strategy engine on extended data.
4. Export only rows after the canonical endpoint.
5. Store the result separately from canonical reports.
6. Audit source, benchmark, weight, and out-of-sample metadata.
```

This produced a valid eight-row candidate extension covering:

```text id="u0f3u9"
2026-05-04 to 2026-05-13
```

and wrote the fresh handoff file:

```text id="jzatn8"
data/fresh/phase15q_rule_generated_candidate_stream.csv
```

A signal-price semantic error in the first export was also caught and corrected. The original `SPY_close` field contained strategy-equity-like values; the corrected extension used `signal_price` as the SPY or proxy-price field.

### Historical Phase 15 Checkpoint

At the immediate end of Phase 15, downstream consumption and current-signal auditing still remained incomplete. Therefore:

* paper dry-run remained blocked;
* broker integration remained blocked;
* live trading remained blocked;
* real-money deployment remained blocked.

Those blocking decisions were correct for the information available at that checkpoint.

### Later Progression

Later project phases built on the Phase 15 operational foundation and advanced beyond this checkpoint.

Subsequent work eventually added:

* downstream signal consumption and audit;
* manual paper-session preparation;
* session rollover and archival;
* paper holdings and cash accounting;
* portfolio valuation and performance reporting;
* the first valid entered ETF/multi-asset manual paper session;
* a separate individual-equity research and shadow-portfolio branch.

Phase 15 should therefore be read as the phase that solved **fresh rule replay and historical operational reconstruction**, not as the project’s current overall status.

Final Phase 15 interpretation:

> Phase 15 converted the validated ETF candidate from a historical return stream into an operationally reconstructable strategy with a separately generated post-endpoint extension. It established the infrastructure required for later manual paper tracking, but did not itself authorise broker execution, live trading, or real-money use.

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

This endpoint was introduced after a data-refresh drift caused some exploratory reports to extend to `2026-05-13`. Pinning the research endpoint prevents refreshed data from silently changing validated historical results.

Unless a deliberately refreshed checkpoint is opened, canonical README numbers should be read as **2026-05-01 pinned checkpoint results**.

This distinction matters:

* `2026-05-01` is the fixed canonical research endpoint.
* Any later data must be treated as a separate post-endpoint / out-of-sample extension.
* A pinned historical endpoint is not a flaw in the research baseline.
* A pinned endpoint signal must not be treated as a current executable paper-trading signal.

---

## Lookahead Bias Controls

The framework uses explicit signal/execution separation:

* signals are generated using only data available at the signal date;
* execution occurs on the next trading day;
* positions are applied after execution, not on the signal day;
* signal and execution columns are audited separately where required.

Phase 7B reconstructed the trend SMA and raw 3D confirmation signal from trailing data and found zero mismatches. It found no obvious lookahead issue in the audited final candidate.

This does not prove the system is production-ready. It only supports the integrity of the audited historical signal/execution path.

---

## Cash Returns

Cash returns are modelled using a T-bill proxy, `^IRX`.

Important details:

* `^IRX` is quoted as a bank discount rate.
* The project converts it into an investment yield before applying cash returns.
* Cash returns are aligned to each asset's trading calendar.
* This matters because momentum and defensive strategies can spend meaningful time in cash.

---

## Calendar-Aware Annualisation

The framework infers periods per year from the actual data frequency.

This avoids treating all assets as if they trade on the same calendar:

* ETFs trade on US business days;
* BTC trades every calendar day.

Using one fixed 252-day annualisation factor across all assets would distort BTC volatility, Sharpe, and cash-period return calculations.

---

## Adjusted Close Data

The project primarily uses adjusted close prices from `yfinance`, reflecting dividends and splits through backward adjustment.

Known issue:

> Adjusted close is not perfectly point-in-time because historical prices are retroactively adjusted.

To test sensitivity to this issue, the project added:

* raw-close signal sensitivity;
* secondary-source comparison against Stooq close data;
* attribution of Stooq/yfinance differences.

The secondary-source audit found broad agreement for most tickers and no unresolved source issues after attribution. Larger differences were concentrated in distribution-sensitive ETFs.

Important limitation:

> Stooq close is useful as a broad sanity check, but it is not a full validator of yfinance adjusted-close total-return data.

---

## Slippage and Execution Costs

Baseline runs apply flat 5 basis points slippage per trade.

Phase 3A tested slippage sensitivity at:

```text
10 bps
25 bps
50 bps
```

The strategy survived 10 bps, weakened at 25 bps, and failed the wealth-growth case at 50 bps.

Phase 4 introduced dynamic stress slippage, charging higher costs during deteriorating or stressed markets. This is more realistic than a flat 5 bps assumption, but it still does not fully model:

* bid-ask spreads;
* market impact;
* intraday liquidity;
* broker routing;
* partial fills;
* fund-level liquidity;
* broker-specific execution;
* taxes.

Phase 8B added scenario-based bid-ask / market-impact stress testing, but the project still lacks production-grade execution modelling.

---

## Cached Data

Price and cash-rate data are cached in:

```text
data/processed/
```

The loaders include schema normalisation so older cached files remain compatible after refactors.

This improves reproducibility, but cached data can also create stale-data risk. Any refreshed checkpoint must explicitly distinguish between:

* pinned canonical research data;
* fresh post-endpoint extension data.

---

## Secondary Data-Source API Key

Phase 7C uses Stooq as a secondary data source.

Stooq requires API-key authentication for CSV downloads. The project expects the key through a local environment variable:

```text
STOOQ_API_KEY
```

The key should live in `.env` or the local shell environment, not in committed configuration files.

`.env` must remain ignored by Git.

---

# Known Limitations

This project remains **research-grade and non-production**.

It now includes functioning manual paper and prospective shadow infrastructure, but that does not make it a production trading platform.

The distinction is important:

```text id="9d673o"
Historical backtest
≠ prospective shadow result
≠ manual paper execution
≠ automated broker paper trading
≠ live trading
≠ real-money readiness
```

The ETF/multi-asset branch has recorded a valid entered manual paper session.

The individual-equity branch has generated a genuine post-endpoint ranking, target portfolio, and proposed simulated orders. Its first entered stock-shadow session remains pending valid next-open execution prices.

No broker API, automated execution, live-money workflow, or production approval exists.

---

## Data and Source Limitations

Remaining data concerns include:

* reliance on `yfinance` data;
* adjusted-close retroactive adjustment;
* cached data becoming stale if not refreshed deliberately;
* Stooq close not being a full adjusted-close total-return validator;
* larger source differences in distribution-sensitive ETFs;
* cash proxy assumptions that may overstate retail-accessible yields;
* limited secondary-source validation beyond the audited checks.

Phase 7C attributed secondary-source differences rather than ignoring them, but that does not remove all data risk.

---

## Backtest and Validation Limitations

The project includes extensive validation, but the evidence is still historical.

Remaining validation concerns include:

* limited true out-of-sample evidence;
* asset universe selection bias;
* BTC and ETH selection bias;
* shorter and structurally different crypto histories;
* no formal multiple-comparisons correction across all strategy and asset combinations;
* no guarantee that bootstrap robustness will translate into future performance;
* no full prospective model-selection framework;
* regime-dependent conclusions.

The holdout validation is a robustness check, not a perfectly clean out-of-sample experiment. Several choices were made after earlier diagnostics, so claims must remain narrow.

---

## Strategy-Hierarchy Limitations

SPY Buy & Hold remains the raw wealth benchmark.

The final Phase 6B/6C `loose_relief` candidate is the best execution-realistic **risk-adjusted** candidate built so far, but it does not beat SPY Buy & Hold on raw terminal wealth or raw CAGR.

The correct claim is:

> The final candidate improves drawdown and risk-adjusted performance while giving up some raw upside versus SPY Buy & Hold.

It should not be described as:

* a raw wealth champion;
* a guaranteed edge;
* a broadly proven market-beating system;
* a production strategy;
* a live-trading system;
* paper-trading-ready;
* real-money-ready.

---

## Execution and Friction Limitations

Execution friction remains one of the largest risks.

Phase 3A showed that the strategy is not friction-proof. It survived low/moderate ETF-like slippage, weakened at higher friction, and failed the wealth-growth case at 50 bps.

Phase 4 dynamic stress slippage showed that execution friction can remove the 3D overlay's full-period CAGR edge over SPY 12M.

Phase 8B showed that bid-ask / market-impact stress can erase the final candidate's CAGR edge versus SPY 12M, even if Calmar and drawdown remain better.

The final candidate is materially more sensitive to execution friction than SPY 12M because it has higher turnover.

---

## Tax Limitations

Phase 8A used a simplified turnover-based tax proxy only.

It did not model:

* tax lots;
* dividends;
* final liquidation;
* wash-sale rules;
* holding-period rules;
* jurisdiction-specific treatment;
* investor-specific tax circumstances.

The final candidate survived the 20% tax-drag proxy, but its CAGR edge over SPY 12M disappeared under the harsher 30% proxy.

The strategy should not be described as tax-proof.

---

## Rolling-Window and Behavioural Limitations

Phase 7F rolling-window survivability failed overall.

The final candidate showed useful full-period and medium/long-horizon evidence, but it was not consistently superior across short rolling windows.

Phase 8D showed material behavioural regret versus SPY Buy & Hold. Lower absolute drawdown does not automatically make the strategy easy to hold.

Key behavioural caveat:

> A strategy can reduce absolute drawdown and still be difficult to hold if it spends long periods lagging Buy & Hold.

Tracking-error regret remains a major liveability risk.

---

## Asset Expansion and Scope Limitations

The original controlled ETF expansion did not produce a clean validated successor:

* USO/oil was promising but not validated;
* ETH was rejected;
* oil plus ETH did not improve the overlay sufficiently;
* BTC and ETH remain quarantined research branches.

The project later opened a separate individual-equity research branch. This did not promote individual stocks into the validated ETF strategy.

The two branches remain distinct:

| Branch                     | Scope                                                       |
| -------------------------- | ----------------------------------------------------------- |
| ETF and multi-asset branch | Validated SPY regime-switch and manual paper workflow       |
| Individual-equity branch   | Noncanonical research pilot and prospective shadow workflow |

The individual-equity branch must not be interpreted as a validated expansion of the Phase 6B/6C ETF candidate.

---

## Technical-Indicator Extension Limitations

Phase 9 technical diagnostics were useful but did not produce a validated rule extension.

Phase 9A and 9B identified technical-regime clusters where the candidate helped or lagged, including oversold RSI and negative 12-month momentum regimes. However, this evidence was diagnostic only.

Phase 9C pre-registered two technical-rule hypotheses, and Phase 9D rejected both.

Final Phase 9 conclusion:

> Technical indicators helped explain candidate behaviour, but failed as validated rule extensions.

No technical rule was promoted, and the final candidate hierarchy remained unchanged.

---

## Macro / Rates / Inflation Limitations

Phase 10 showed that macro, rates, and inflation data can be handled safely and can be diagnostically informative.

However, the pre-registered macro-rule test failed.

No macro rule, allocation overlay, model feature, strategy successor, or promoted candidate exists from Phase 10.

Important boundaries:

* Phase 10A and 10B were feasibility/audit phases only.
* Phase 10C loaded and aligned macro data but did not create a trading signal.
* Phase 10D produced diagnostic macro-regime analysis only.
* Phase 10E pre-registered macro hypotheses only.
* Phase 10F rejected the pre-registered macro rules.
* Phase 10G and 10H closed the macro branch without promotion.

The final candidate hierarchy remained unchanged.

---

## Regime-Scoring Limitations

Phase 11 prepared a regime-scoring architecture, rulebook, diagnostic-panel design, templates, and content audits.

Phase 12 calculated and interpreted a categorical diagnostic regime score.

The final diagnostic score state was:

```text
fragile
```

This score is research context only.

It is not:

* a trading signal;
* an allocation rule;
* a backtest result;
* an empirical model;
* a live-trading input;
* a candidate promotion;
* a final-candidate change.

No score-to-signal conversion exists.

---

## ML and Multi-Factor Model Limitations

The Phase 13 technical-plus-macro ML v1 branch did not produce a model strong enough to justify holdout evaluation or trading use.

Its limitations included:

* substantial train-validation gaps;
* near-zero or zero fragile-class recall;
* insufficient predictive value from technical and macro features;
* no justified holdout prediction;
* no promoted model;
* no ML-derived trading signal;
* no ML strategy backtest;
* no ML paper deployment.

The branch was commercially paused after both registered model repair and target redesign failed.

The later individual-equity branch uses an interpretable Ridge cross-sectional ranker, but it is a separate research architecture.

It does not reverse the Phase 13 conclusion.

Future multi-factor work remains dependent on acquiring and auditing genuinely new point-in-time information, including:

* historical index membership;
* filing-time fundamental data;
* amendments and restatements;
* historical news and sentiment;
* transcripts and analyst revisions;
* additional market-stress features.

Fundamental, news, sentiment, transcript, and analyst contracts have been designed for the individual-equity architecture, but the required canonical historical datasets have not yet been acquired and integrated.

---

## Individual-Equity Research Limitations

The individual-equity branch is deliberately labelled as a controlled pilot.

Its current universe contains 16 surviving stocks:

```text id="209xel"
AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, BRK-B,
XOM, JNJ, UNH, PG, COST, CAT, NEE, TSLA
```

The pilot has several material limitations:

* the universe is hand-selected;
* it is survivorship-biased;
* it is not a historical reconstruction of the S&P 500 or Nasdaq-100;
* membership is noncanonical;
* market-data provenance remains research-grade;
* the current feature set is primarily technical, liquidity, and stress based;
* weekly 20-day forward labels overlap;
* the research period is relatively short;
* historical portfolio results may be inflated by universe selection;
* only a small number of securities are ranked on each date;
* no broad-index generalisation claim is permitted.

The Phase 23G Ridge ranker produced encouraging out-of-sample rank-correlation evidence:

```text id="xaw732"
Mean Spearman IC: 0.1225
Median Spearman IC: 0.1485
Positive-IC dates: 62.9%
```

Phase 23H robustness supported continued research, but the top-minus-bottom spread interval remained weaker and crossed slightly below zero.

The Phase 23I historical portfolio results must therefore retain the label:

```text id="ue4zkz"
NONCANONICAL PILOT DIAGNOSTIC — NOT INVESTABLE PERFORMANCE
```

The historical results do not establish:

* canonical stock-selection performance;
* index-wide generalisation;
* production readiness;
* live-trading suitability;
* future profitability.

---

## Paper and Shadow-Trading Limitations

The ETF/multi-asset branch has progressed into manual paper tracking and has recorded a valid entered session.

However, it remains:

* manually operated;
* dependent on explicit session review;
* separate from broker execution;
* research-only;
* subject to stale-data and operational-error risk.

The individual-equity branch has reached a different point.

Completed individual-equity shadow progress includes:

* frozen Phase 23G model specification;
* deterministic model hash;
* cost-aware portfolio construction;
* separate post-endpoint data storage;
* historical overlap validation;
* post-endpoint data for SPY and all 16 pilot stocks;
* genuine prospective feature calculation;
* prospective stock ranking;
* target-portfolio construction;
* proposed shadow orders;
* explicit next-open execution controls.

At the latest recorded checkpoint, the prospective signal date was:

```text id="b4ctq0"
2026-06-12
```

The frozen model ranked the following stocks in its top five:

```text id="i3jt51"
TSLA
META
CAT
AMZN
NVDA
```

The corresponding research target assigned 20% to each stock before integer-share rounding and execution-price validation.

The proposed orders remained blocked because valid next-open execution prices were not yet available:

```text id="yat9qd"
execution_open_price_pending
```

This was the correct result.

The fill helper correctly refused to fabricate execution prices or mark blocked orders as entered.

Until valid next-open prices exist:

* no individual-equity simulated entry may be recorded;
* no entered shadow position exists;
* no prospective stock-performance claim may be made.

Automated broker paper trading, live trading, and real-money deployment remain blocked across both branches.

---

## Current Research-Degrees-of-Freedom Caveat

Phase 8E documented 11 research branches and many tested, rejected, or caveated units.

This is not a formal multiple-comparisons correction, but it matters.

The final candidate emerged after many tested branches, so it should not be described as a statistically definitive or broadly proven market-beating system.

The correct wording is narrow:

> Best execution-realistic risk-adjusted candidate built so far, with documented caveats and no production-readiness claim.

---

# Bugs Caught and Fixed

The project has caught and fixed multiple implementation and research-process issues, including:

* package import setup issue;
* pandas month-end resampling behaviour change;
* cash-rate parquet schema mismatch;
* IRX discount-rate conversion issue;
* calendar annualisation error for BTC;
* annual rebalance audit DataFrame overwrite bug;
* strategy-purpose classification label inconsistency;
* candidate portfolio warmup contamination concern;
* missing Calmar and date fields in final report;
* incorrect `calculate_metrics()` keyword call in holdout validation;
* relative momentum target-weight forward-fill bug;
* missing report fixtures after adding constrained allocator;
* raw 200D regime-switch whipsaw issue diagnosed through audit;
* 3D confirmation logic added after whipsaw audit;
* raw-close signal sensitivity added after adjusted-close concern;
* endpoint drift to `2026-05-13` diagnosed and fixed with `research_period.end_date`;
* dual-momentum branch endpoint bypass fixed;
* duplicate `cash_returns` return-key issue fixed;
* secondary data-source cross-check deferred after ingestion/parsing failure;
* Phase 6B offensive-relief gate logic initially selected the highest headline-score candidate before checking all validation gates, then was fixed to evaluate all candidates independently and select the best passing candidate;
* Phase 7A separated metric trade count from overlay switch count;
* Phase 7B confirmed trend SMA and raw confirmation state could be reconstructed without mismatches;
* Phase 7C fixed Stooq CSV authentication handling and API-key environment-variable support;
* Phase 7C.2 attributed Stooq/yfinance differences to price-basis/distribution treatment rather than leaving them as unresolved source failures;
* Phase 8A tax-drag test switched to approximate float assertions after floating-point precision caused an exact equality test failure.
* Phase 14 visual backtest initially used the wrong source, selecting a relative-momentum allocator stream instead of the intended Phase 6B/6C `loose_relief` candidate;
* Phase 14 source-identity and metric-reconciliation audit blocked paper-workflow progression until the correct Phase 6B/6C stream was exported;
* Phase 14 corrected stream export reconciled financial metrics but exposed an operational switch-count mismatch;
* Phase 15 switch reconstruction initially used noisy `position`, `cash_position`, and turnover semantics, producing incorrect switch counts;
* Phase 15I/15J fixed the operational switch definition by identifying `target_offensive_weight` as the executable final allocation column and reconstructing the correct 36-switch history;
* Phase 15 fresh-signal attempts initially wrote signal-shaped files without real post-endpoint candidate rows, correctly blocking paper dry-run progression;
* Phase 15T revealed that `_find_final_candidate_frame` exposed the pinned historical candidate frame but did not replay Phase 6B/6C logic beyond the endpoint;
* Phase 15WXYZ fixed the fresh-extension architecture by rerunning the existing project pipeline on an extended fresh-data clone while preserving the canonical `2026-05-01` baseline;
* Phase 15WXYZ initial export used strategy equity-like values as `SPY_close`; this was corrected to use `signal_price` as the SPY/proxy price field.
* Phase 21H entered-session processing exposed a dtype compatibility issue during manual paper-session ingestion; the fill path was patched and revalidated.
* Phase 22C tested a dynamic-opportunity return enhancement, but the change failed to improve the strategy sufficiently and was rejected rather than promoted.
* Phase 23F input bootstrapping exposed ticker-alias handling requirements, including consistent treatment of `BRK-B`; the alias path was corrected and tested.
* Phase 23G prediction accounting distinguished 10,560 model/baseline prediction rows from 2,112 unique stock-date observations, preventing an inflated sample-size claim.
* Phase 23H identified overlapping weekly 20-day labels and used moving-block bootstrap and within-date permutation tests instead of treating observations as independent.
* Phase 23I froze the model specification with a deterministic hash so later prospective runs cannot silently change the trained ranker.
* Phase 23I separated historical portfolio diagnostics from prospective shadow reports, preventing noncanonical historical performance from being presented as live evidence.
* The initial Phase 23I shadow workflow could detect newer data but did not itself calculate a genuine new frozen-model ranking; Phase 23J added the required post-endpoint feature calculation and prospective scoring path.
* Phase 23J introduced historical-overlap checks and SHA-256 validation so refreshed data cannot silently modify the canonical pilot files.
* Phase 23J correctly blocked simulated order entry when the next eligible opening prices were unavailable.
* The Phase 23I fill helper correctly rejected attempts to mark blocked orders as entered, preventing fabricated next-open execution.

---

# Project Structure

```text id="7q8779"
Market-strats-lab/
├── configs/
│   └── spy_sma10.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   ├── fresh/
│   ├── individual_equity_pilot/
│   └── individual_equity_post_endpoint/
├── experiments/
├── notebooks/
├── reports/
│   ├── individual_equity_decision_system/
│   └── individual_equity_shadow/
├── scripts/
│   └── fill_phase23i_shadow_session.py
├── src/
│   └── market_strats/
│       ├── __init__.py
│       ├── analysis/
│       │   ├── frozen_cost_aware_portfolio.py
│       │   └── post_endpoint_individual_equity_extension.py
│       ├── data/
│       ├── strategies/
│       └── run_backtest.py
├── tests/
├── pyproject.toml
├── README.md
└── .gitignore
```

Generated reports, market-data extensions, ledgers, caches, filled session files, and paper/shadow account state are local research artefacts and should not be committed unless explicitly intended.

In particular, normal source commits should exclude:

```text id="7ldpgf"
reports/
data/individual_equity_pilot/
data/individual_equity_post_endpoint/
filled session files
manual ledgers
positions and cash state
cache directories
```

---

# Installation

```powershell id="ud2mt5"
git clone <your-repo-url>
cd Market-strats-lab

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

---

# Running the Project

## Full Research Suite

```powershell id="36g5j7"
$env:MPLBACKEND="Agg"

.\.venv\Scripts\python -m market_strats.run_backtest `
  --config configs/spy_sma10.yaml
```

## Phase 23J Post-Endpoint Individual-Equity Extension

```powershell id="r2m9c3"
$env:MPLBACKEND="Agg"

.\.venv\Scripts\python -m market_strats.run_backtest `
  --config configs/spy_sma10.yaml `
  --phase23j-only
```

## Phase 23I Prospective Stock-Shadow Runner

```powershell id="3emdly"
$env:MPLBACKEND="Agg"

.\.venv\Scripts\python -m market_strats.run_backtest `
  --config configs/spy_sma10.yaml `
  --phase23i-shadow-only
```

## Create Explicit Simulated Fills

This command is permitted only after every proposed order has:

```text id="5czv6o"
execution_price_available = True
paper_order_allowed = True
order_blocking_reason = blank
```

Run:

```powershell id="b72vlb"
.\.venv\Scripts\python `
  scripts\fill_phase23i_shadow_session.py `
  --confirm-simulated-fill
```

The helper will reject the operation if the proposed orders remain blocked.

## Tests and Linting

```powershell id="zwwzim"
$env:MPLBACKEND="Agg"

.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest
```

## Save Full Terminal Output

```powershell id="5wfwav"
.\.venv\Scripts\python -m market_strats.run_backtest `
  --config configs/spy_sma10.yaml `
  *> reports\latest_terminal_output.txt
```

## Load Local Environment Variables

```powershell id="uuyfut"
Get-Content .env |
  ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
      [Environment]::SetEnvironmentVariable(
        $matches[1].Trim(),
        $matches[2].Trim(),
        "Process"
      )
    }
  }
```

API keys and secrets must remain outside committed configuration.

---

# Key Reports and Artefacts

The framework writes generated artefacts to:

```text
reports/
```

Most phases produce a combination of:

* raw CSV outputs;
* summary reports;
* gate reports;
* conclusion reports;
* Markdown audit reports;
* chart images where visual inspection is required.

The report inventory below is intentionally detailed. It documents the project’s research progression, validation trail, rejected branches, operational-readiness checks, and paper-trading preparation path.

Not every generated report represents a promoted strategy or validated trading rule. Many reports are diagnostic, audit-only, or pre-registration artefacts. Their purpose is to preserve the decision trail and prevent post-hoc overclaiming.

---

## Phase 15G True Final Switch Log Export Reports

```text
reports/phase6b_loose_relief_execution_realistic_overlay_switch_event_log.csv
reports/phase15g_true_switch_log_export_phase15f_result_check.csv
reports/phase15g_true_switch_log_export_column_selection_report.csv
reports/phase15g_true_switch_log_export_source_rejection_report.csv
reports/phase15g_true_switch_log_export_switch_summary.csv
reports/phase15g_true_switch_log_export_required_column_check.csv
reports/phase15g_true_switch_log_export_phase15h_boundary_check.csv
reports/phase15g_true_switch_log_export_scope_boundary_check.csv
reports/phase15g_true_switch_log_export_summary.csv
reports/phase15g_true_switch_log_export_gate_report.csv
reports/phase15g_true_switch_log_export_conclusion.csv
```

## Phase 15H Switch Log Reconciliation Audit Reports

```text
reports/phase15h_switch_log_reconciliation_config_flag_check.csv
reports/phase15h_switch_log_reconciliation_report_inventory_check.csv
reports/phase15h_switch_log_reconciliation_phase15g_result_check.csv
reports/phase15h_switch_log_reconciliation_required_column_check.csv
reports/phase15h_switch_log_reconciliation_reconciliation_decision_report.csv
reports/phase15h_switch_log_reconciliation_phase15i_boundary_check.csv
reports/phase15h_switch_log_reconciliation_scope_boundary_check.csv
reports/phase15h_switch_log_reconciliation_summary.csv
reports/phase15h_switch_log_reconciliation_gate_report.csv
reports/phase15h_switch_log_reconciliation_conclusion.csv
```

## Expected Phase 15Q/15R/15O/15P Downstream Reports

The following reports are expected after the downstream Phase 15Q/15R/15O/15P rerun consumes the Phase 15WXYZ fresh handoff file. They should not be treated as completed checkpoint artefacts until they exist locally and their conclusion reports have been inspected.

```text
reports/phase15o_post_endpoint_candidate_stream.csv
reports/phase15o_candidate_stream_extension_source_report_check.csv
reports/phase15o_candidate_stream_extension_phase15r_result_check.csv
reports/phase15o_candidate_stream_extension_required_column_check.csv
reports/phase15o_candidate_stream_extension_summary.csv
reports/phase15o_candidate_stream_extension_gate_report.csv
reports/phase15o_candidate_stream_extension_conclusion.csv
reports/phase15p_extended_stream_config_flag_check.csv
reports/phase15p_extended_stream_report_inventory_check.csv
reports/phase15p_extended_stream_phase15o_result_check.csv
reports/phase15p_extended_stream_required_column_check.csv
reports/phase15p_extended_stream_validation_audit.csv
reports/phase15p_extended_stream_decision_report.csv
reports/phase15p_extended_stream_phase15m_boundary_check.csv
reports/phase15p_extended_stream_scope_boundary_check.csv
reports/phase15p_extended_stream_summary.csv
reports/phase15p_extended_stream_gate_report.csv
reports/phase15p_extended_stream_conclusion.csv
reports/phase15q_post_endpoint_candidate_stream.csv
reports/phase15q_data_source_creation_summary.csv
reports/phase15q_data_source_required_column_check.csv
reports/phase15q_data_source_upstream_result_check.csv
reports/phase15q_data_source_phase15r_boundary_check.csv
reports/phase15q_data_source_scope_boundary_check.csv
reports/phase15q_data_source_summary.csv
reports/phase15q_data_source_gate_report.csv
reports/phase15q_data_source_conclusion.csv
reports/phase15r_real_source_config_flag_check.csv
reports/phase15r_real_source_report_inventory_check.csv
reports/phase15r_real_source_phase15q_result_check.csv
reports/phase15r_real_source_required_column_check.csv
reports/phase15r_real_source_real_source_validation_audit.csv
reports/phase15r_real_source_decision_report.csv
reports/phase15r_real_source_phase15o_rerun_boundary_check.csv
reports/phase15r_real_source_scope_boundary_check.csv
reports/phase15r_real_source_summary.csv
reports/phase15r_real_source_gate_report.csv
reports/phase15r_real_source_conclusion.csv
```

## Phase 15S Rule Replay Source Discovery Reports

```text
reports/phase15s_rule_replay_discovery_phase15r_result_check.csv
reports/phase15s_rule_replay_discovery_code_path_inventory.csv
reports/phase15s_rule_replay_discovery_final_candidate_profile.csv
reports/phase15s_rule_replay_discovery_target_column_discovery.csv
reports/phase15s_rule_replay_discovery_replay_requirement_report.csv
reports/phase15s_rule_replay_discovery_decision_report.csv
reports/phase15s_rule_replay_discovery_phase15t_boundary_check.csv
reports/phase15s_rule_replay_discovery_scope_boundary_check.csv
reports/phase15s_rule_replay_discovery_summary.csv
reports/phase15s_rule_replay_discovery_gate_report.csv
reports/phase15s_rule_replay_discovery_conclusion.csv
```

## Phase 15T Rule-Generated Candidate Stream Export Reports

```text
reports/phase15t_rule_generated_candidate_stream.csv
reports/phase15t_rule_export_export_summary.csv
reports/phase15t_rule_export_required_column_check.csv
reports/phase15t_rule_export_phase15s_result_check.csv
reports/phase15t_rule_export_decision_report.csv
reports/phase15t_rule_export_phase15q_rerun_boundary_check.csv
reports/phase15t_rule_export_scope_boundary_check.csv
reports/phase15t_rule_export_summary.csv
reports/phase15t_rule_export_gate_report.csv
reports/phase15t_rule_export_conclusion.csv
```

## Phase 15WXYZ Fresh Extension Pipeline Reports

```text
reports/phase15y_post_endpoint_final_candidate_stream.csv
reports/phase15wxyz_fresh_extension_fresh_config_report.csv
reports/phase15wxyz_fresh_extension_fresh_pipeline_report.csv
reports/phase15wxyz_fresh_extension_export_summary.csv
reports/phase15wxyz_fresh_extension_required_column_check.csv
reports/phase15wxyz_fresh_extension_decision_report.csv
reports/phase15wxyz_fresh_extension_scope_boundary_check.csv
reports/phase15wxyz_fresh_extension_gate_report.csv
reports/phase15wxyz_fresh_extension_conclusion.csv
data/fresh/phase15q_rule_generated_candidate_stream.csv
```

The Phase 15WXYZ reports are separate from the canonical pinned research reports. Their purpose is to generate a post-endpoint / out-of-sample candidate stream without mutating the canonical `2026-05-01` historical checkpoint.

## Phase 23J Post-Endpoint Extension

```text id="sqol94"
reports/individual_equity_decision_system/
└── phase23j_post_endpoint_individual_equity_extension/
    ├── phase23j_summary.csv
    ├── phase23j_download_status.csv
    ├── phase23j_extension_validation.csv
    ├── phase23j_current_features.csv
    ├── phase23j_current_ranking.csv
    ├── phase23j_current_target_portfolio.csv
    └── phase23j_historical_integrity.csv
```

These reports document:

* post-endpoint download status;
* overlap validation;
* historical-file integrity;
* frozen-model verification;
* prospective feature calculation;
* current stock ranking;
* target weights;
* next-open execution readiness.

## Phase 23I Prospective Shadow Reports

```text id="hx4dcs"
reports/individual_equity_shadow/
└── phase23i_prospective_shadow/
    ├── phase23i_shadow_summary.csv
    ├── current_proposed_order_plan.csv
    ├── manual_session_template.csv
    ├── filled_session_validation.csv
    ├── positions.csv
    ├── cash_ledger.csv
    ├── valuation_history.csv
    └── archive/
```

The shadow namespace is deliberately separate from:

* canonical historical reports;
* ETF manual-paper ledgers;
* Phase 21 session files;
* individual-equity historical portfolio diagnostics.

## Historical Phase15 Reports

The existing detailed Phase15 report inventory remains useful as a historical operational audit trail.

Reports labelled as expected, blocked, superseded, or failed should retain those labels. Their existence does not imply that the corresponding subphase passed.

---

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

---


# Current Configuration Overview

The main configuration remains:

```text id="moao2e"
configs/spy_sma10.yaml
```

The configuration now supports two connected research tracks.

## ETF and Multi-Asset Track

The historical suite includes:

* SPY and multi-asset benchmarks;
* absolute and relative momentum;
* trend confirmation;
* constrained tactical allocation;
* regime-switch overlays;
* confirmation, guard, and relief logic;
* execution-cost and tax diagnostics;
* bootstrap and rolling-window validation;
* technical and macro extensions;
* regime-scoring diagnostics;
* visual reporting;
* operational replay;
* fresh-signal extensions;
* manual paper-session infrastructure.

## Individual-Equity Track

The current individual-equity architecture includes:

* universe and membership contracts;
* fundamental-source audit contracts;
* news and sentiment-source contracts;
* point-in-time feature-panel contracts;
* pilot feature calculation;
* target construction;
* purged and embargoed walk-forward ranking;
* Ridge-model robustness;
* frozen model specification and hash;
* cost-aware historical portfolio diagnostics;
* separate prospective shadow reports;
* post-endpoint price acquisition;
* frozen-model prospective ranking;
* target-portfolio and order generation;
* next-open execution controls;
* manual shadow fills, holdings, cash, and valuation infrastructure.

The canonical historical endpoint remains:

```text id="jgd7y9"
2026-05-01
```

Later data must remain separately labelled and stored as post-endpoint research.

---

# Research Phase Status

| Branch                                   | Current Status                                                                      |
| ---------------------------------------- | ----------------------------------------------------------------------------------- |
| ETF historical strategy research         | Mature historical framework; final hierarchy unchanged                              |
| ETF final candidate                      | `3D confirmed + deep_drawdown_guard + loose_relief`                                 |
| ETF raw-wealth benchmark                 | SPY Buy & Hold                                                                      |
| ETF manual paper workflow                | Operational; first valid entered session recorded                                   |
| Phase 22 dynamic-opportunity enhancement | Rejected after failing to improve the research case                                 |
| Individual-equity architecture           | Completed through source, panel, model, robustness, portfolio, and shadow contracts |
| Individual-equity pilot data             | Built for 16 noncanonical surviving stocks                                          |
| Individual-equity model                  | Frozen interpretable Ridge ranker                                                   |
| Individual-equity robustness             | Encouraging IC evidence with material caveats                                       |
| Historical stock portfolio               | Cost-aware diagnostic completed; not investable performance                         |
| Post-endpoint stock data                 | Downloaded and validated separately                                                 |
| Prospective stock ranking                | Generated for the latest recorded signal date                                       |
| Proposed stock-shadow orders             | Generated                                                                           |
| First entered stock-shadow session       | Pending valid next-open execution prices                                            |
| Broker/API integration                   | Blocked                                                                             |
| Automated broker paper trading           | Blocked                                                                             |
| Live trading                             | Blocked                                                                             |
| Real-money deployment                    | Blocked                                                                             |

---

# What Should Happen Next

The immediate priority is operational, not another historical strategy search.

## Immediate Milestone

Complete the first genuine entered individual-equity shadow session.

Required sequence:

```text id="h1jgoc"
1. Refresh Phase 23J after the next eligible execution session is available.
2. Confirm planned execution date and opening prices.
3. Confirm every target-portfolio row has execution_price_available = True.
4. Regenerate the Phase 23I shadow order plan.
5. Confirm current_orders_blocked = False.
6. Explicitly create simulated fills.
7. Rerun Phase 23I to validate and ingest the entered session.
8. Archive the filled session.
9. Confirm positions, cash, and valuation history.
```

The first entered session remains a workflow milestone, not proof of predictive value.

## Next Engineering Phase

After the first entered stock-shadow session, the next bounded phase should be:

```text id="hgrb3z"
Phase 23K — Prospective Shadow Monitoring, Drift, and Operational Controls
```

Phase 23K should monitor:

* weekly rankings;
* selected and rejected securities;
* proposed versus entered orders;
* portfolio valuation;
* cash balances;
* realised and unrealised returns;
* drawdowns;
* turnover and transaction costs;
* maturing 20-day prediction outcomes;
* information coefficient through time;
* top-minus-bottom spread;
* score-distribution drift;
* feature-distribution drift;
* model-hash consistency;
* stale or missing data;
* sector and security concentration;
* skipped, blocked, and failed sessions.

## Evidence Horizon

A practical evaluation schedule is:

| Horizon                     | Interpretation                                                 |
| --------------------------- | -------------------------------------------------------------- |
| First 1–2 sessions          | Operational smoke test only                                    |
| 4–8 weekly sessions         | Early process and data-quality evidence                        |
| At least 12 weekly sessions | Minimum preliminary prospective review                         |
| Preferably 26 weeks         | Stronger evidence before considering broker-sandbox automation |

Broker integration, automated paper execution, live trading, and real money must remain blocked until the prospective process is materially broader, operationally clean, and independently reviewed.

---

# Final Conclusion

Market Strats Lab has progressed from simple ETF backtests into a two-track systematic research and operational-testing framework.

It has not discovered a perfect strategy.

It has established a disciplined process for:

* constructing hypotheses;
* preventing lookahead;
* pinning historical checkpoints;
* testing execution friction;
* documenting failed branches;
* freezing models and rules;
* separating historical and prospective evidence;
* reconstructing operational decisions;
* tracking manual paper and shadow sessions.

## ETF and Multi-Asset Conclusion

The validated ETF hierarchy remains:

| Role                               | System                                                            |
| ---------------------------------- | ----------------------------------------------------------------- |
| Raw wealth benchmark               | SPY Buy & Hold                                                    |
| Simple defensive benchmark         | SPY 12M Absolute Momentum                                         |
| Original canonical overlay         | SPY 3D Confirmed Overlay                                          |
| Execution-realistic baseline       | SPY 3D Confirmed Overlay + `deep_drawdown_guard`                  |
| Best execution-realistic candidate | SPY 3D Confirmed Overlay + `deep_drawdown_guard` + `loose_relief` |

Pinned final-candidate result:

| Metric               |                    Value |
| -------------------- | -----------------------: |
| Period               | 2006-04-28 to 2026-05-01 |
| End value            |               $71,779.16 |
| CAGR                 |                   10.35% |
| Calmar               |                    0.429 |
| Max drawdown         |                  -24.12% |
| Metric trade count   |                       66 |
| Overlay switch count |                       36 |

The correct interpretation remains:

> The ETF candidate materially improved drawdown and risk-adjusted performance while giving up some raw upside relative to SPY Buy & Hold.

The ETF branch has progressed into manual paper tracking, but remains research-only and manually operated.

## Individual-Equity Conclusion

The individual-equity branch has produced:

* a point-in-time research architecture;
* a controlled 16-stock pilot;
* a governed feature and target panel;
* an interpretable frozen Ridge ranker;
* purged and embargoed walk-forward predictions;
* encouraging rank-correlation robustness;
* cost-aware historical portfolio diagnostics;
* a separate post-endpoint extension;
* a genuine prospective ranking;
* a target portfolio;
* proposed next-open shadow orders.

The latest recorded prospective top-five ranking was:

```text id="4f6mxc"
TSLA
META
CAT
AMZN
NVDA
```

These outputs are not investment recommendations.

The branch remains:

```text id="8x0esw"
NONCANONICAL
SURVIVORSHIP-BIASED
RESEARCH-ONLY
NOT INVESTABLE PERFORMANCE
```

The next meaningful milestone is the first valid entered stock-shadow session using actual next-open execution prices.

## Overall Project Position

The project’s strongest achievement is not a single performance number.

It is the research and operational discipline demonstrated by repeatedly:

* rejecting wrong data sources;
* rejecting unreconciled metrics;
* rejecting failed rule extensions;
* rejecting weak ML models;
* blocking stale signals;
* refusing fabricated execution prices;
* preserving historical checkpoints;
* keeping research, paper, broker, and live states separate.

The project is currently best described as:

> A reproducible systematic-strategy research lab with a mature ETF research and manual-paper branch, an emerging individual-equity prospective-shadow branch, and strict controls against premature live or real-money deployment.

It should not be described as:

* a guaranteed edge;
* a production trading system;
* an automated broker strategy;
* a universally validated stock-selection model;
* financial advice;
* live-trading-ready;
* real-money-ready.

Current boundary:

> The project has earned continued prospective manual testing. It has not earned automated broker execution, live trading, or real-money deployment.