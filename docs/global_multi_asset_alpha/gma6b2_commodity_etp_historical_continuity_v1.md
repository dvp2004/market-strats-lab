# GMA-6B.2 Historical Commodity-ETP Methodology Continuity v1

This additive overlay reviews official historical disclosures for USO and DBA across the frozen GMA-6B window: `2007-05-30` through `2026-05-01`.

USO and DBA are analysed only as historical traded ETP return exposures.
Their adjusted-price paths are not asserted to represent spot commodity returns.
Documented futures-roll, collateral, fee, distribution, split, benchmark, and vehicle-structure effects remain part of the realised traded-instrument return.
This is observed development evidence and not a pristine final holdout.
No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.

## Source Standard

The audit uses SEC EDGAR prospectus materials only. It does not rely on market-data websites, blogs, general web summaries, third-party ETF databases, or spot commodity interpretations.

## Interpretation

The GMA-6B.1 interpretation is preserved: USO is a futures-linked oil ETP return exposure, and DBA is a futures-linked agriculture ETP return exposure. Both retain `traded_etp_total_return_interpretation = true` and `spot_proxy_claim_permitted = false`.

## Overlay Rule

A documented material methodology change does not block later research, but later diagnostics must carry the explicit methodology-regime flag. Incomplete continuity evidence blocks the later phase.
