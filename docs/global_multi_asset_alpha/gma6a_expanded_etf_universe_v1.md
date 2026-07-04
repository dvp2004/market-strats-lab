# GMA-6A Expanded ETF Universe Contract v1

GMA-6A is a design-only contract for an expanded ETF/ETP universe. GMA-4/GMA-5 V1 remain unchanged and are read-only parent references. GMA-6A has no performance results. This record is observed development evidence, not a pristine final holdout, and no execution or promotion decision is produced.

Parent references:

- parent_gma4_commit: 86a49fc
- gma5_v1_evidence_snapshot_root: C:\Users\Devesh Pansare\Desktop\Personal_Projects\market-strats-lab-gma5-v1-evidence-snapshot-20260623
- gma5_v1_evidence_snapshot_manifest_sha256: 7cd1f1cec9a4bf20a4dad756041efc1a70ba8a7482665af1d23d84178465cf0c

The frozen GMA-4/GMA-5 V1 universe remains exactly 22 instruments in the original order. GMA-6A adds exactly seven design entries: VNQ, TIP, USO, DBA, SLV, EWG, and EWJ. No later universe alteration is allowed without a new version.

Data eligibility gates for any later GMA-6 execution:

- adjusted-price availability
- corporate-action handling
- coverage from 2007-05-30 through the later frozen end date
- no silent ticker substitution
- no silent start-date shortening
- cash/accrual compatibility
- documented handling for ETP/commodity-pool structure

If any instrument fails, later GMA-6 execution must be labelled blocked_data_contract_failure. No automatic fallback is allowed.

Specific overlap and structure notes:

- USO and DBA need commodity-roll/carry review before any later execution phase.
- EWG and EWJ overlap economically with EFA.
- VNQ overlaps with broad equity exposure.
- The additions are not represented as improving returns or diversification.

The deterministic design table is rendered in reports/global_multi_asset_alpha/gma6a_expanded_etf_universe_design_v1.csv and reports/global_multi_asset_alpha/gma6a_expanded_etf_universe_design_v1.md.

