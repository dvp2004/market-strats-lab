# GMA-6B Expanded ETF Data Eligibility and Frozen Historical Bundle v1

GMA-6B creates data eligibility evidence only for the frozen GMA-6A 29-instrument ETF/ETP universe. This is observed development evidence and not a pristine final holdout. No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced. A data-eligible universe does not imply that it improves return, diversification, or risk-adjusted performance.

The required coverage window is 2007-05-30 through 2026-05-01. No silent ticker substitution, shortened start date, or automatic fallback is allowed.

Required data gates:

- adjusted-price availability
- raw-close availability
- corporate-action handling capability from the source response
- coverage over the frozen observed session set
- ticker identity preservation
- cash/accrual compatibility for BIL and fixed-income instruments
- documented ETP or commodity-pool structure handling

USO and DBA remain structure_review_pending unless a later version documents commodity-pool structure and roll/carry handling for execution. A structure_review_pending ticker blocks the universe-level GMA-6 research execution verdict.

All raw provider snapshots and normalised series are stored only under reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1/.
