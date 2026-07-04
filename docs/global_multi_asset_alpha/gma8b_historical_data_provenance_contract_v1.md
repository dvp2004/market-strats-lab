# GMA-8B Frozen ETF/ETP Historical Data Universe and Provenance Contract V1

GMA-8B freezes the inherited historical ETF/ETP adjusted-price evidence for the GMA-8 tournament.
It does not calculate a strategy signal, portfolio target, backtest result, strategy ranking, paper decision, broker instruction, or real-money action.
Highest historical CAGR or Sharpe alone is not a selection rule.
No execution or promotion decision is produced.

## Deterministic Source Resolution

The inherited source consists of 29 separately normalized ticker CSVs. The only resolver roots are the frozen GMA-6 snapshot manifest and the original GMA-6B normalized-file hash inventory named in the contract.

For each ordered Expanded-29 inventory row, the resolver matches `normalised_series_file_hash` to exactly one snapshot-manifest `snapshot_sha256`, requires `hash_match = true`, confines the resulting `snapshot_path` beneath the immutable snapshot root, and verifies the file's actual SHA-256. `source_path` is retained only as provenance and is never a data source.

The same exact-row mechanism resolves the frozen GMA-6B bundle configuration and bundle manifest. Their provider settings, requested universe, bundle-manifest hash, and normalized-inventory hash are verified before any ticker CSV is read. No directory traversal, candidate search, path guessing, fallback source, or manual pointer is used.

## Price Interpretation and Quality

The frozen GMA-6B provider contract uses `auto_adjust: false` with actions enabled. The immutable normalized files have the exact locked schema `date,open,high,low,close,adj_close,volume`; only `adj_close` is audited as the adjusted-price evidence.

Every date must parse, remain unique, and be strictly ascending. Every adjusted price must be present, numeric, finite, and positive. Values and rows are never filled, interpolated, substituted, removed, repaired, or backfilled.

`adjusted_price_interpretation = historical_total_return_adjusted_price_evidence_under_inherited_convention`

`real_time_vendor_publication_timing_verified = false`

The inherited end-of-history adjusted-price files do not independently prove real-time vendor publication or point-in-time corporate-action availability.

## Availability

The maximum fixed GMA-8A lookback is 252 sessions, so each ticker becomes eligible only on its own 253rd observed valid session. Core-22 and Expanded-29 receive separate all-assets eligible dates. Cross-arm comparison begins at the later date and otherwise remains `not_comparable_due_to_effective_start`.

## Terminal Boundary

GMA-8B creates provenance, quality, and availability records only. It does not calculate indicators, returns, signals, weights, turnover, costs, backtests, rankings, paper targets, broker instructions, or live actions. GMA-8C may begin only after the 29 resolved paths and hashes and all eligibility dates are reviewed.
