# GMA-6B.1 Commodity-Pool Structure Review v1

This overlay resolves the structure interpretation for USO and DBA only. It does not modify the frozen GMA-6A universe contract or the existing GMA-6B data bundle artifacts.

USO and DBA are evaluated only as traded ETP return exposures.
Their adjusted-price history is not asserted to be a spot commodity return series.
Any embedded futures-roll, collateral, fee, distribution, split, or vehicle-structure effects remain part of the historical traded-instrument return.
This is observed development evidence and not a pristine final holdout.
No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.

## Source Standard

Only primary official materials are accepted. The current review uses SEC-filed prospectus material for both instruments. Third-party summaries, finance portals, and informal descriptions are out of scope.

## Interpretation Rule

A ticker can be eligible for a later GMA-6 research phase only as a traded commodity-ETP return instrument when vehicle structure, objective, futures-linked or contract-based exposure, contract roll or contract management, adjusted-price interpretation, and the no-extra-roll-deduction assumption are all documented.

The overlay does not claim spot commodity exposure. The economic labels are descriptive exposure labels for traded ETP returns only.

## Outputs

The review writes:

- `reports/global_multi_asset_alpha/gma6b_commodity_pool_structure_review_v1.csv`
- `reports/global_multi_asset_alpha/gma6b_commodity_pool_structure_review_v1.md`
- `reports/global_multi_asset_alpha/gma6b_commodity_pool_source_manifest_v1.csv`

The later GMA-6 universe may proceed only if `gma6b_commodity_pool_overlay_status` is `both_documented_for_later_research_execution`.
