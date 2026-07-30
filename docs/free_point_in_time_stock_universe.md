# Free Point-in-Time Stock Universe V1

## Boundary

`market-strats-universe` qualifies whether zero-cost evidence is sufficient to construct a
point-in-time S&P 500 research universe. It does not create features, targets, models, strategies,
portfolios, orders, or trading instructions.

The frozen contract is
`configs/universe/free_sp500_point_in_time_universe_v1.yaml`. Source policy is recorded in
`configs/universe/free_source_registry_v1.yaml`. Runtime data and reports require explicit absolute
roots and remain ignored by Git.

## Command

```powershell
market-strats-universe qualify-free-sp500 `
  --contract configs/universe/free_sp500_point_in_time_universe_v1.yaml `
  --source-registry configs/universe/free_source_registry_v1.yaml `
  --data-root <EXPLICIT_LOCAL_IGNORED_ROOT> `
  --report-root <EXPLICIT_LOCAL_IGNORED_ROOT> `
  --as-of 2026-05-01
```

`SEC_USER_AGENT` must be supplied by the operator and must contain an application or organization
name plus a contact email. The value is never persisted or printed. `ALPHA_VANTAGE_API_KEY` is
optional and, when present, is used only with the free `LISTING_STATUS` endpoint for supplemental
lifecycle evidence.

The adapter records raw close, adjusted close, volume, dividends, splits, request parameters,
retrieval time, and snapshot hashes separately. Missing prices and delisting outcomes are never
converted to zero. Tickers are effective-dated attributes; they are not permanent identity keys.

## Frozen Sources

| Source | Frozen identity | Terms class | Role |
| --- | --- | --- | --- |
| hanshof historical constituents | commit `a91ef88fad5ace83bed1f3452f451247295bcd18` | MIT | noncanonical membership seed |
| English Wikipedia S&P 500 page | revision `1349933445`, SHA-1 `baf197c44ad0db24ba89ba650fbe9149e76b0bda` | CC BY-SA 4.0 | reconciliation |
| S&P Global announcements | fixed 2018, 2020, and 2024 sample | public official factual metadata | independent sample evidence |
| SEC EDGAR | response hashes at runtime | public official, Fair Access applies | issuer CIK and filing timestamps |
| Yahoo Finance through `yfinance` | package and snapshot hashes at runtime | personal research access, not open-licensed | resumable effective-dated prices and actions |
| Alpha Vantage | optional free `LISTING_STATUS` endpoint | personal research access, not open-licensed | supplemental lifecycle evidence only |

## Bounded Qualification Result

The local run at the frozen endpoint completed normally with
`blocked_identity_reconciliation_failure`.

- Historical membership seed: 1996-01-02 through 2025-08-23, 3,482 snapshots.
- Reconstructed membership: 1,172 additions, 669 removals, 1,126 provisional identities.
- Independent announcement sample: 3 passed, 0 failed.
- Frozen Wikimedia reconciliation: 36 unresolved current-set differences.
- Price audit: 24 provider tickers requested, including SPY; 23 historical security identities had
  data and 1,103 remained outside the bounded price audit.
- Delisting treatment: 648 removed-security outcomes unresolved.
- SEC identity mapping: unavailable because the official endpoint returned HTTP 403 in the run
  environment.
- Qualified monthly decisions: 0 of 365 scheduled.

All downloaded source content, normalized snapshots, Parquet outputs, JSON reports, and Markdown
reports remain under ignored local roots. Total data cost was zero. No paid API, paid trial,
subscription, model, backtest, portfolio, paper workflow, broker action, or live action was used.

## Final Remediation Status

The final free-source remediation is implemented and covered by network-free tests. Its real rerun
stopped before source acquisition because `SEC_USER_AGENT` was not supplied in the execution
environment. The optional Alpha Vantage source was also not used because no free API key was
present. Therefore the last completed strict verdict remains
`blocked_identity_reconciliation_failure`; no new verdict was fabricated.

See `docs/free_data_limit_reached.md` for the canonical evidence limit and the conditions under which
a separately preregistered noncanonical universe could be considered.
