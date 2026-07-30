# Architecture

## Research flow

```text
point-in-time sources
  -> immutable local snapshots and availability evidence (MI-1, MI-5, MI-6, MI-7)
  -> feature and target contracts (MI-2, MI-3)
  -> fixed model comparisons (MI-2, MI-4)
  -> research-only signal exports
  -> shadow records and matured outcomes (MI-8)
  -> separately governed portfolio evaluation in market_strats
```

`market_strats.intelligence` owns source qualification, retrieval-time evidence, feature
construction, model comparison, and observation records. It never owns broker communication,
orders, or live portfolio mutation.

The existing `market_strats.data` package remains the lightweight backtest data interface. The
intelligence data package was retained because it enforces a different contract: immutable raw
snapshots, availability timestamps, corporate-action records, coverage audits, and decision-time
eligibility. Replacing it with the backtest loader would remove point-in-time evidence.

Existing `market_strats.analysis` and `market_strats.strategies` modules remain authoritative for
evaluation, costs, portfolio rules, robustness, and benchmarks. Intelligence code does not copy
those implementations.

## Package boundary

- `intelligence/contracts`: source-neutral records.
- `intelligence/data`: MI-1 source adapters, snapshots, registry, and pipeline.
- `intelligence/quality`: availability and coverage validation.
- `intelligence/mi2` through `mi8`: phase-specific research components.
- `intelligence/reporting`: small local audit writers.
- `intelligence/cli.py`: explicit research commands.

All generated data and reports are supplied through explicit path arguments and remain ignored.
