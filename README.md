# Market Strats Lab

Market Strats Lab is a research-only system for building and evaluating point-in-time market
signals, long-only individual-stock rankings, periodic portfolios, and transparent ETF
benchmarks. It combines the former Market Intelligence Lab data and signal foundations with the
existing Market Strats portfolio, robustness, and operational research code.

The project objective is:

> A long-only, point-in-time individual-stock ranking and portfolio system that rebalances
> periodically and attempts to outperform SPY Buy & Hold after costs on unseen and prospective
> data.

SPY Buy & Hold is the primary raw-return benchmark. No model in this repository has yet
demonstrated reliable prospective outperformance of that benchmark after costs.

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

The portable consolidation gate covers the migrated intelligence package and its matching tests:

```powershell
.\.venv\Scripts\python -m ruff check --select E,F,I,UP `
  src/market_strats/intelligence tests/test_mi*.py
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

This command may access its configured market-data provider and writes only to ignored local
paths. Validation does not invoke it.

Historical MI-8 replay can execute when valid local MI-1 normalized inputs are supplied. A real
prospective shadow run remains gated by its frozen operating-release checks and should be
re-frozen only after this consolidation is reviewed and merged.

## Repository map

```text
src/market_strats/intelligence/  point-in-time data and signal research
src/market_strats/analysis/      evaluation, diagnostics, and research workflows
src/market_strats/strategies/    transparent portfolio rules and benchmarks
src/market_strats/global_multi_asset/  GMA contracts and tournament research
configs/intelligence/            MI-1 through MI-8 research contracts
tests/                            portable and explicitly marked artifact-backed tests
docs/                             architecture, objective, reproducibility, and history
```

## Documentation

- [Architecture](docs/architecture.md)
- [Model objective](docs/model_objective.md)
- [Reproducibility](docs/reproducibility.md)
- [Repository consolidation](docs/repository_consolidation.md)
- [Detailed research history](docs/research_history.md)
- [Intelligence phases](docs/intelligence/README.md)

## Publication policy

Source code, tests, schemas, small configs, and concise documentation may be published after
review. Raw SEC filings, raw FRED/ALFRED or provider responses, large generated panels, report
releases, archives, credentials, local paths, and redistribution-restricted data must remain
local.

## License

MIT. Third-party data remains subject to its provider terms and is not covered by the code
license.
