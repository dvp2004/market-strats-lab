# GMA-6C Cross-Universe Tournament v1

This is observed development evidence and not a pristine final holdout.
No strategy, portfolio replay, model fit, allocation, execution, or promotion decision is produced.
GMA-4 and GMA-5 V1 remain unchanged.
GMA-6C is a frozen design contract only and contains no performance results.

## Purpose

GMA-6C freezes the design for one later GMA-6D cross-universe historical tournament execution. It compares the frozen 22-instrument core universe against the frozen 29-instrument expanded universe using the same 20 GMA-4 trial templates, the same cost scenarios, and matched-sample comparison rules.

## Universe Arms

- `gma6_core_22_control_v1`: SPY, QQQ, IWM, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, EFA, EEM, BIL, IEF, TLT, AGG, LQD, HYG, GLD, DBC.
- `gma6_expanded_29_v1`: the core 22 plus VNQ, TIP, USO, DBA, SLV, EWG, EWJ.

No 27-instrument fallback arm is allowed. USO and DBA may not be silently omitted.

## Trial Inventory Lock

The trial inventory is derived from `configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml`. GMA-6C preserves the exact source GMA-4 trial order and records both `source_gma4_trial_id` and deterministic `arm_trial_id` values for each universe arm.

The universe equal-weight benchmark keeps its source template reference while labelling actual construction as `equal_weight_current_universe_monthly` with the arm-specific universe size.

## Matched-Sample Comparison

Later execution must compare each same-template core-versus-expanded pair on the same valid decision and execution dates. If either arm lacks required history on a date, both arms must start at the later common valid date. Later reports must include `comparison_period_start`, `comparison_period_end`, and `sample_comparability_status`.

Highest historical CAGR or Sharpe alone is not a selection rule.

## USO Methodology-Regime Rule

Expanded-arm results must carry `uso_roll_methodology_pre_may_2020_vs_from_may_2020`. Later diagnostics must produce descriptive pre-flag and from-flag slices, must not interpret the flag as proof of performance causation, and must not remove USO or alter its return series after outcomes are reviewed.

DBA carries `not_required`.

## Future Required Result Metadata

Later GMA-6D outputs must identify `universe_version`, `trial_id`, `cost_scenario`, `evaluation_scope`, and `methodology_regime_flag`.

## Terminal Stop Rule

After GMA-6C passes, the next and only permitted GMA-6 task is one frozen GMA-6D cross-universe tournament execution.

No GMA-6C.1, new strategy family, parameter sweep, additional asset, or universe alteration is permitted before that execution and results review.
