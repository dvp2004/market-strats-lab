# Repository Consolidation

## Decision

`dvp2004/market-strats-lab` is the canonical repository. The former
`dvp2004/market-intelligence-lab` remains available during review and is not archived or deleted by
this change.

## Migrated capability inventory

- MI-1 market-data records, registry, source protocol, provider adapter, immutable snapshots,
  availability logic, quality validation, coverage audit, pipeline, and local reporting.
- MI-2 technical baseline, signal-export parity, prospective source adapter, snapshot runner, and
  associated research contracts.
- MI-3 vintage-aware macro forecast and source adapter.
- MI-4 fixed tree comparator.
- MI-5 FOMC event/text parsing and event-window foundation.
- MI-6 BLS release-source qualification.
- MI-7 SEC EDGAR 8-K acceptance-time qualification.
- MI-8 frozen shadow-record and outcome-maturity workflow.
- Corresponding YAML contracts and portable tests.

No raw data, reports, generated outputs, caches, environments, credentials, `.env` files, release
archives, or duplicate phase-history documents were migrated.

## Duplicate decisions

| Area | Selected implementation | Reason |
| --- | --- | --- |
| Point-in-time source records and snapshots | `market_strats.intelligence.data` | Existing backtest loaders do not retain retrieval and availability evidence. |
| Generic ETF download utility | Existing `market_strats.data` for backtests; MI-1 adapter only inside intelligence pipeline | The adapters serve different contracts and are not interchangeable APIs. |
| Portfolio simulation, costs, metrics, and benchmarks | Existing `market_strats` modules | The intelligence repository did not own the canonical portfolio layer. |
| Technical baseline and tree comparator | Migrated MI-2/MI-4 implementations | They preserve fixed point-in-time comparison contracts absent from the canonical package. |
| Research history | Existing canonical README moved to `docs/research_history.md` | Avoids two competing top-level narratives while preserving lineage. |

Imports now use `market_strats.intelligence`. Configs live under `configs/intelligence`. The CLI is
available as `market-strats-intelligence` or `python -m market_strats.intelligence.cli`.

## Deferred operating step

MI-8 prospective mode retains its frozen operating-release guard. A new canonical operating branch
and annotated tag must be deliberately approved after this pull request is reviewed and merged.
Historical replay and hermetic shadow-cycle tests do not require that future release decision.
