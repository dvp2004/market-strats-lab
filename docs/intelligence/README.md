# Market Intelligence Phases

The intelligence package is research-only. It produces evidence and candidate signals, not orders,
broker instructions, or authority to modify a portfolio.

## Phase boundary

- MI-1: daily market-data snapshots, normalized records, coverage, and availability evidence.
  Macro data begins no earlier than MI-3. MI-1 excludes broker integration and portfolio
  construction or simulation. It also excludes portfolio construction or simulation as an
  operating capability.
- MI-2: technical baseline, fixed walk-forward evaluation, signal export parity, and prospective
  observation contracts.
- MI-3: revision-aware macro observations and vintage-safe forecast comparison.
- MI-4: fixed random-forest comparator on the same MI-2 rows.
- MI-5: official FOMC statement discovery, timestamping, text descriptors, and event windows.
- MI-6: BLS release-source and timestamp qualification.
- MI-7: SEC EDGAR 8-K acceptance-timestamp qualification.
- MI-8: immutable shadow prediction batches and delayed outcome maturity.

Configurations are in `configs/intelligence`. All data and report roots are explicit CLI arguments.
Real source access is never part of the portable test suite.

No phase is a claim of technical-family qualification, trading readiness, or reliable prospective
outperformance. SPY Buy & Hold remains the raw-return benchmark.
