# Point-in-Time Stock Universe Plan

## Purpose

This document defines the minimum viable data foundation for a long-only
individual-stock ranking model evaluated against SPY Buy & Hold after costs.
It is a design plan, not an executable universe contract or a research result.

The first implementation must produce a versioned, immutable universe contract
and a qualification report. No feature construction, model training, backtest,
portfolio construction, or prospective prediction may begin until that
universe contract passes every acceptance gate in this plan.

## Research Boundary

The minimum viable research population is the historical membership of one
specified US large-cap index whose investable proxy is SPY. The executable
contract must identify the index, source, license, coverage dates, and exact
membership convention before any data is processed.

The universe is not today's constituent list projected backward. A security is
eligible only when the point-in-time membership and data rules below establish
that it was eligible on that decision date.

This foundation does not authorize:

- model fitting or hyperparameter selection;
- feature or target generation;
- historical or prospective portfolio simulation;
- orders, paper trading, broker access, or live actions;
- publication or redistribution of licensed source data.

## Point-in-Time Security Identity

Every security must have a stable internal `security_id` that does not change
when its ticker, name, exchange, or share class label changes. Ticker is an
effective-dated attribute, not the primary key.

The security master must support:

- `security_id`;
- issuer identifier, including SEC CIK when available;
- share-class identifier;
- ticker and exchange with valid-from and valid-through dates;
- index membership with effective-from and effective-through dates;
- source publication or observation timestamp;
- corporate-action event type, effective date, and source identity;
- successor and predecessor identifiers when an economic lineage exists.

No record may infer two securities are identical from ticker text alone.
Ticker reuse must create separate security identities.

## Historical Membership

The membership ledger must represent each addition and removal as a sourced,
effective-dated event. For every decision date:

1. Include a security no earlier than its index addition effective date.
2. Retain it through the session immediately before its removal effective date.
3. Do not remove a future constituent early because its later deletion is now
   known.
4. Do not add a future constituent early because its later inclusion is now
   known.
5. Preserve the source announcement timestamp separately from the effective
   date.

The ledger must include delisted, acquired, bankrupt, renamed, and otherwise
removed securities. Current-survivor filtering is prohibited.

If an addition or removal cannot be sourced and reconciled, the affected
decision dates fail closed. They may not be filled from a current constituent
list or inferred from later prices.

## Corporate Actions and Delistings

The security master and return data must account explicitly for:

- ticker and exchange changes;
- ordinary and special cash dividends;
- stock splits and reverse splits;
- mergers and cash or stock acquisitions;
- spin-offs and distributions;
- bankruptcies and liquidations;
- share-class conversions;
- delistings and delisting returns.

Adjusted prices may be used only when the adjustment methodology and vintage
are documented. Raw prices and corporate-action records must be retained
locally when licensing permits so adjustments can be audited.

A missing delisting return may not be replaced with zero. The affected
security-period must fail qualification unless a separately documented,
conservative treatment was frozen before results were inspected.

## Availability Rules

### Prices

The monthly decision cutoff is the official US equity close on the last
eligible exchange session of each calendar month. A signal may use only price,
volume, and corporate-action information available by that close. The earliest
permitted execution timestamp is the next eligible US equity session open.
Same-close execution is prohibited.

Price observations must be keyed by `security_id`, session date, source, and
retrieval or snapshot identity. Missing prices may not be forward-filled across
halts, delistings, identity changes, or corporate actions.

### Filings

SEC filing data becomes available at its EDGAR acceptance timestamp. A filing
is eligible only if that timestamp is on or before the decision cutoff.
Fiscal-period end dates, later amendments, or current XBRL facts must not be
used as substitutes for historical availability.

Amendments are separate observations. They may supersede earlier values only
from the amendment acceptance timestamp onward.

### Membership Announcements

Membership announcement time and membership effective time must both be
recorded. Baseline eligibility follows the effective membership interval.
Any future experiment that trades between announcement and effective date
requires a separate preregistered contract and is outside this foundation.

## Decision Cadence

The minimum viable cadence is monthly:

- decision time: close of the last eligible US equity session each month;
- execution convention: next eligible US equity session open;
- holding period: until the next scheduled rebalance;
- missed decision: skip rather than use late or retrospectively repaired data.

The calendar implementation must use an exchange calendar and save the exact
decision and execution sessions in the frozen contract.

## Eligibility

A security is eligible on a decision date only when all of these conditions
hold:

- active index membership under the effective-dated ledger;
- at least 252 prior eligible trading sessions of price history;
- a valid close and volume observation at the decision cutoff;
- a trailing 60-session median daily dollar volume of at least USD 20 million;
- a decision-date close of at least USD 5;
- no unresolved security-identity or corporate-action conflict;
- no unresolved trading halt or stale-price condition;
- all features used later can satisfy their own point-in-time availability
  rules.

Dollar-volume and price thresholds must use only information available at the
decision cutoff. Threshold changes require a new frozen universe-contract
version and may not be selected after model results are observed.

## Benchmark and Cost Convention

The primary benchmark is SPY Buy & Hold total return after costs over exactly
the same evaluation interval as the candidate model.

The executable evaluation contract must freeze one symmetric one-way cost rate
before any results are produced. The same rate applies to both candidate and
benchmark transactions:

- SPY incurs the cost on initial purchase and terminal liquidation;
- the candidate incurs it on every purchase and sale;
- dividends and distributions are included consistently;
- gross-return comparison is secondary and cannot replace the net benchmark.

The benchmark is not redefined by volatility, drawdown, Sharpe ratio, or cash
returns. Those may be reported as secondary diagnostics only.

## Evaluation Segments

Exact calendar boundaries may be frozen only after the qualified data coverage
is known. They must be written to the universe and evaluation contracts before
feature inspection or model training.

The minimum segmentation is:

1. **Frozen training period:** earliest qualified contiguous history, with at
   least 60 monthly decisions.
2. **Walk-forward validation:** at least 60 subsequent monthly decisions using
   expanding or rolling training windows fixed before the first validation
   result.
3. **Untouched holdout:** at least 36 subsequent monthly decisions. It is
   opened once after the model, features, costs, and portfolio rules are locked.
4. **Prospective shadow:** begins only after holdout review and a separate
   authorization. It requires at least 12 scheduled monthly decisions, records
   predictions before outcomes mature, and has zero portfolio authority.

There may be no overlap between the untouched holdout and any model-selection
activity. Prospective records may not be backfilled.

## Allowed Sources and Licensing

Permitted source classes are:

- an official index-provider membership history under a license that permits
  this research use;
- a licensed institutional security master or point-in-time constituent
  database;
- SEC EDGAR submissions and filing facts, subject to SEC access policies;
- licensed exchange or market-data prices, corporate actions, and delisting
  returns;
- issuer or exchange notices used as sourced event evidence;
- public data only when its terms permit the intended local use and the
  evidence is sufficient for point-in-time reconstruction.

Provider convenience APIs and current web pages are not authoritative evidence
of historical membership. Free provider data may be used for a synthetic
adapter test, but not silently promoted to the canonical historical dataset.

Raw licensed data, provider responses, and redistribution-restricted
identifiers must remain local and ignored by Git. The repository may contain
schemas, source-neutral fixtures, checksums, coverage summaries, and documented
retrieval procedures only when licensing permits.

Before intake, each source must have a recorded:

- provider and dataset identifier;
- terms or license classification;
- permitted local storage and derived-output policy;
- point-in-time timestamp semantics;
- coverage range and known survivorship limitations;
- immutable local snapshot or checksum policy.

## Fail-Closed Rules

The universe qualification fails when any required condition is unresolved,
including:

- missing or contradictory historical membership;
- missing prices for an eligible security without a sourced explanation;
- absent or ambiguous permanent security identity;
- unreconciled ticker reuse or corporate action;
- missing delisting treatment;
- filing availability based only on fiscal dates rather than acceptance time;
- source or license terms that do not permit the planned use;
- a decision date constructed from information observed after its cutoff;
- incomplete benchmark or cost data for the same evaluation interval.

Failed dates and securities must be reported with reason codes. They may not be
silently dropped, imputed from current data, or repaired after outcome
inspection.

## Required Contract Artifacts

The future implementation may begin only with these small, source-neutral
artifacts:

- a versioned universe-contract YAML;
- a membership and identity schema;
- a source and license registry;
- a decision-calendar manifest;
- a coverage and exclusion report;
- a checksum manifest for local evidence;
- hermetic synthetic tests for additions, removals, delistings, ticker changes,
  corporate actions, late filings, and missing-price failures.

Raw data and generated research results remain outside Git.

## Acceptance Gate

The universe contract passes only when:

- all decision dates reconstruct membership without current-survivor
  filtering;
- sampled additions, removals, delistings, and ticker changes reconcile to
  independent source evidence;
- all included prices and filings satisfy decision-time availability;
- eligibility and exclusion rules reproduce deterministically;
- benchmark dates and costs align with candidate evaluation dates;
- licensing permits the retained local evidence and published derived
  summaries;
- fail-closed synthetic tests and a bounded historical coverage audit pass.

The terminal rule is explicit:

> No model training begins until the point-in-time stock universe contract
> passes and its version, sources, coverage, decision calendar, and hashes are
> frozen.
