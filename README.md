# Market Strats Lab

Market Strats Lab is a research-only system for building and evaluating point-in-time market
signals, long-only individual-stock rankings, periodic portfolios, and transparent ETF
benchmarks. It combines the former Market Intelligence Lab data and signal foundations with the
existing Market Strats portfolio, robustness, and operational research code.

## Project story

### 1. Start: test transparent long-term market strategies

The project began by asking whether systematic ETF and multi-asset rules could improve the
return, drawdown, and practical liveability trade-off relative to simply holding SPY.

The research covered buy-and-hold, absolute momentum, relative momentum, regime-switch overlays,
transaction costs, market-impact diagnostics, walk-forward validation, bootstrap robustness,
behavioural-regret analysis, and paper-operating controls.

### 2. First result: there was no single winner on every dimension

The frozen comparison below covers 2006-04-28 through 2026-05-01. These are historical research
results, not current signals or prospective performance claims.

| Strategy | Role | End value | CAGR | Calmar | Max drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| SPY Buy & Hold | Raw-wealth benchmark | $79,306.63 | 10.90% | 0.197 | -55.19% |
| SPY 12M Absolute Momentum | Simple defensive benchmark | $63,497.24 | 9.68% | 0.287 | -33.72% |
| Top 3 Trend-Confirmed Relative Momentum | Balanced allocator | $58,401.74 | 9.22% | 0.317 | -29.06% |
| Top 3 Constrained Relative Momentum | Defensive allocator | $52,197.16 | 8.61% | 0.351 | -24.54% |
| SPY 3D Confirmed Overlay | Original risk-adjusted system | $70,048.61 | 10.22% | 0.429 | -23.84% |
| SPY 3D Overlay + deep-drawdown guard | Execution-realistic baseline | $66,429.13 | 9.93% | 0.412 | -24.12% |
| SPY 3D Overlay + guard + loose relief | Best risk-adjusted ETF candidate | $71,779.16 | 10.35% | 0.429 | -24.12% |

The conclusion was deliberately two-part:

- **SPY Buy & Hold remained the raw-return and terminal-wealth winner.**
- **SPY 3D Overlay + deep-drawdown guard + loose relief became the best
  execution-realistic risk-adjusted ETF candidate built in the project.**

The selected overlay gave up some return but reduced the historical maximum drawdown from about
55% to about 24%. In the 2016-01-04 through 2026-05-01 holdout, SPY still had the higher CAGR,
while the overlay retained the lower drawdown and stronger Calmar ratio.

No tested strategy dominated SPY Buy & Hold on raw wealth while also improving every risk and
liveability metric.

### 3. New idea: try to improve the trade-off with individual stocks

The ETF research exposed a clear limitation: defensive timing reduced drawdowns, but it also
sacrificed upside participation.

That led to the next hypothesis:

> Can a point-in-time model rank individual stocks well enough to outperform SPY Buy & Hold after
> costs, while preserving more of the drawdown control achieved by the best ETF overlay?

The project therefore expanded into an autonomous, long-only individual-stock research system
using technical, liquidity, fundamental, macroeconomic, and event information only when it was
actually available at the historical decision time.

### 4. Current objective and benchmark ladder

The current objective is:

> A long-only, point-in-time individual-stock ranking and portfolio system that rebalances
> periodically and attempts to outperform SPY Buy & Hold after costs on unseen and prospective
> data.

Success is intentionally harder than beating one convenient historical number:

1. **Primary raw-return hurdle:** outperform SPY Buy & Hold after comparable costs.
2. **Risk hurdle:** match or improve the final ETF overlay's drawdown and risk-adjusted profile.
3. **Research hurdle:** survive frozen walk-forward validation and one untouched holdout.
4. **Forward hurdle:** continue producing acceptable results in prospective shadow observation.

No model in this repository has yet passed all four hurdles.

## What has been built

### ETF and multi-asset research

- buy-and-hold, trend, momentum, allocation, and regime-switch strategies;
- transaction-cost, spread, market-impact, and tax-drag diagnostics;
- walk-forward, bootstrap, rolling-window, and behavioural robustness checks;
- a frozen best execution-realistic risk-adjusted ETF candidate;
- manual paper-session, fill-validation, holdings, cash, and reconciliation infrastructure.

### Individual-equity and intelligence research

- a controlled 16-stock research-only pilot;
- technical, liquidity, and market-stress features;
- forward-return targets and purged, embargoed walk-forward evaluation;
- an interpretable Ridge cross-sectional stock ranker;
- one fixed tree-model comparator;
- cost-aware portfolio diagnostics;
- point-in-time SEC filing, macro-vintage, FOMC, BLS, and SEC event contracts;
- prospective shadow records and delayed outcome maturity;
- source qualification, immutable snapshots, hashes, and fail-closed validation.

The 16-stock pilot produced encouraging rank-correlation evidence, but it is noncanonical,
survivorship-biased, and not evidence that the model can beat SPY across a historical index
universe.

## Current work: remove survivorship bias at zero data cost

The first executable free-source universe qualifier is implemented. It uses an MIT-licensed,
commit-pinned historical membership seed, a revision-pinned Wikimedia reconciliation, a fixed sample
of public S&P Global announcements, official SEC identity endpoints, and Yahoo Finance prices through
`yfinance` under personal-research terms.

The bounded 2026-05-01 qualification run returned
`blocked_identity_reconciliation_failure`. The seed covers 1996-01-02 through 2025-08-23, but free
evidence did not establish historical identity continuity or delisting treatment, the seed and
Wikimedia endpoint sets had unresolved differences, complete historical prices were outside the
bounded audit, and the SEC identity endpoint refused access from the run environment.

No model was trained, no feature or target panel was created, and the result does not authorize a
backtest, portfolio, paper workflow, broker action, or trading decision.

## Status and boundaries

- Research and education only; not financial advice.
- No broker connection, order authority, or real-money execution.
- Historical results do not establish prospective performance.
- Provider data, raw filings, API responses, generated panels, reports, and environments remain
  local and are excluded from Git.
- Prospective shadow records are observation artifacts, not trading instructions.

The repository has two cooperating layers:

1. `market_strats.intelligence` creates point-in-time evidence, features, model comparisons,
   research-only signal exports, shadow records, and matured outcomes.
2. The existing `market_strats` analysis, strategy, data, and global multi-asset modules evaluate
   portfolios, costs, robustness, and operational constraints.

Signals cross the boundary only through explicit, research-only contracts. Intelligence modules
do not place orders or modify portfolio state.

## Intelligence capabilities

| Phase | Capability | Current role |
| --- | --- | --- |
| MI-1 | Point-in-time EOD market-data snapshots and availability audits | Data foundation |
| MI-2 | Technical baseline, signal export parity, and prospective snapshot contracts | Baseline research |
| MI-3 | Vintage-aware macro forecast comparison | Macro research |
| MI-4 | Fixed random-forest comparator | Model comparator |
| MI-5 | FOMC event and text foundation | Event/text research |
| MI-6 | BLS release-source qualification | Source qualification |
| MI-7 | SEC EDGAR 8-K acceptance-time qualification | Source qualification |
| MI-8 | Shadow prediction records and outcome maturity | Forward observation |

These modules preserve the former Market Intelligence Lab semantics under
`src/market_strats/intelligence/`. Their portable tests use synthetic inputs. Network-backed runs
and artifact-backed evaluations remain explicit local operations.

## Installation

Python 3.11 is the supported runtime.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

## Validation

The portable gate covers the intelligence and point-in-time universe packages and their matching
synthetic tests:

```powershell
.\.venv\Scripts\python -m ruff check --select E,F,I,UP `
  src/market_strats/intelligence src/market_strats/universe `
  tests/test_mi*.py tests/universe
.\.venv\Scripts\python -m pytest -q -m "not artifact"
```

Tests marked `artifact` require local generated evidence and are intentionally excluded from the
portable suite. They are not deleted or silently treated as passing.

The full legacy `src` and `tests` tree is not Ruff-clean. At consolidation, the unscoped command
`python -m ruff check src tests` reported 735 pre-existing findings. That backlog is technical debt,
not a passing release gate and not part of this consolidation change.

## Intelligence CLI

The installed entry point is `market-strats-intelligence`. Equivalent module invocation is:

```powershell
.\.venv\Scripts\python -m market_strats.intelligence.cli --help
```

Example local MI-1 refresh:

```powershell
.\.venv\Scripts\python -m market_strats.intelligence.cli refresh-mi1-market-data `
  --universe-config configs/intelligence/universe_mi1.yaml `
  --source-config configs/intelligence/market_data_source_mi1.yaml `
  --mi2-registry-config configs/intelligence/mi2_research_registry.yaml `
  --data-root data/private/mi1 `
  --report-root reports/mi1 `
  --start 2000-01-01
```

This command may access its configured market-data provider and writes only to ignored local paths.
Validation does not invoke it.

Historical MI-8 replay can execute when valid local MI-1 normalized inputs are supplied. A real
prospective shadow run remains gated by its frozen operating-release checks.

## Repository map

```text
src/market_strats/intelligence/        point-in-time data and signal research
src/market_strats/analysis/            evaluation, diagnostics, and research workflows
src/market_strats/strategies/          transparent portfolio rules and benchmarks
src/market_strats/global_multi_asset/  GMA contracts and tournament research
configs/intelligence/                  MI-1 through MI-8 research contracts
tests/                                 portable and explicitly marked artifact-backed tests
docs/                                  architecture, objective, reproducibility, and history
```

## Documentation

- [Architecture](docs/architecture.md)
- [Model objective](docs/model_objective.md)
- [Point-in-time stock universe plan](docs/point_in_time_stock_universe_plan.md)
- [Reproducibility](docs/reproducibility.md)
- [Repository consolidation](docs/repository_consolidation.md)
- [Detailed research history](docs/research_history.md)
- [Intelligence phases](docs/intelligence/README.md)

## Publication policy

Source code, tests, schemas, small configs, and concise documentation may be published after
review. Raw SEC filings, raw FRED/ALFRED or provider responses, large generated panels, report
releases, archives, credentials, local paths, and redistribution-restricted data must remain local.

## License

MIT. Third-party data remains subject to its provider terms and is not covered by the code license.
