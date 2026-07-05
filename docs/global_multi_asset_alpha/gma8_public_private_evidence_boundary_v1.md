# GMA-8 Public / Private Evidence Boundary V1

This document defines the boundary between GMA-8 code that is safe to publish
and GMA-8 historical evidence that must remain local.

## Background

The GMA-8 programme runs a bounded historical ETF/ETP strategy tournament using
immutable adjusted-price inputs inherited from GMA-6. Those inputs exist only as
private immutable adjusted-price evidence on the research operator's machine. They
are not included in this repository, and they cannot be reproduced or reconstructed
from the public code alone.

## What This Repository Contains

The public repository contains:

- `gma8a_broad_multi_asset_tournament_contract.py` — design-only preregistration
  generator (no market data, no backtest).
- `gma8b_historical_data_provenance.py` — deterministic provenance auditor that
  fails closed when private immutable evidence is absent.
- `gma8b_source_pointer_intake.py` — manual source-pointer intake validator that
  fails closed until an operator supplies exact local paths and hashes.
- `gma8c_frozen_etf_etp_tournament.py` — frozen tournament runner that fails closed
  when required private evidence files are absent or their hashes mismatch.
- Matching YAML contracts, documentation, and tests for GMA-8A and GMA-8C.
- Public non-runnable templates for GMA-8B/B.0 (see below).

## What This Repository Does Not Contain

- The private immutable adjusted-price evidence (GMA-6 snapshot), which consists of
  29 per-ticker normalised CSV files on the operator's machine.
- The frozen local GMA-8B/B.0 YAML contracts, which contain machine-specific
  absolute Windows paths to that private evidence.
- Any generated report, lock, manifest, or evidence output from GMA-8B or GMA-8C.

## Frozen Local Contracts and Machine-Specific Paths

The two frozen local GMA-8B/B.0 YAML contracts are retained locally and are not
published because they include machine-specific absolute Windows paths:

```
configs/global_multi_asset_alpha/gma8b_historical_data_provenance_contract_v1.yaml
configs/global_multi_asset_alpha/gma8b_source_pointer_intake_contract_v1.yaml
```

These contracts are historical local evidence and must remain byte-for-byte unchanged.

## Public Templates

Two public templates replace the frozen local contracts for repository users:

```
configs/global_multi_asset_alpha/public_templates/gma8b_historical_data_provenance_public_template_v1.yaml
configs/global_multi_asset_alpha/public_templates/gma8b_source_pointer_intake_public_template_v1.yaml
```

These public templates are illustrative configuration schemas. They show the exact
structure required to run GMA-8B/B.0 on a local machine, with every machine-specific
absolute path replaced by an explicit `REQUIRED_PRIVATE_EVIDENCE_*` placeholder.

Public templates are not reproductions of the private evidence environment, do not
contain synthetic or substitute data, and cannot be executed as-is.

## Fail-Closed Behavior

Published code must fail closed when required private inputs are absent. Each GMA-8B
module raises an explicit error if:

- a required private path placeholder has not been replaced;
- a referenced file does not exist at the supplied path;
- an actual file SHA-256 does not match the frozen expected hash.

No fallback, path discovery, guessing, or silent substitution is permitted.

## Unit Tests and Synthetic Fixtures

Public unit tests rely only on synthetic fixtures and must never load private source
paths. The four GMA-8 test files (`test_gma8a_*.py`, `test_gma8b_*.py`,
`test_gma8c_*.py`) use only `tmp_path` and in-memory data. No test reads a real
adjusted-price file from the operator's machine.

The portability-boundary test (`test_gma8_public_portability_boundary.py`) verifies
that the public templates contain no machine-specific path fragments and that the
frozen local contracts remain byte-identical to their published SHA-256 values.

## Evidence Scope Disclaimer

GMA-8 results remain observed development evidence, not a pristine final holdout.
The outer evaluation period (from 2021-01-04) was observed after an earlier research
phase and may not be used for strategy selection, parameter changes, universe changes,
or post-hoc exclusions.

Highest historical CAGR or Sharpe alone is not a selection rule. A strategy must be
judged across costs, turnover, drawdown, chronological folds, and predefined historical
regimes.

GMA-8 produces no execution or promotion decision of any kind. No execution or promotion decision is produced by any GMA-8 phase.
