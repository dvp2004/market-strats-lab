# GMA-7B Point-in-Time ETF Feature Store Contract V1

This is a point-in-time feature store built from frozen adjusted-price evidence.
All feature values use only information available by the monthly decision-session close.
Forward target values, forecasts, model outputs, portfolio weights, and performance results are not generated in GMA-7B.
This is observed development evidence and not a pristine final holdout.
No execution or promotion decision is produced.

## Frozen Evidence

GMA-7B reads the frozen GMA-6B adjusted-price evidence snapshot and validates the snapshot manifest, bundle manifest, normalised hash inventory, Core-22 ticker order, per-file hashes, and complete adjusted-price panel before deriving features.

## Timing Convention

The decision session is the final available tradable session of each calendar month. The signal observation cutoff is the decision-session close. The decision timestamp is a deterministic UTC bookkeeping timestamp one hour after the New York close and is not a claim about intraday provider publication timing. The next executable and target-start session is the first subsequent tradable session.

## Feature Boundary

Feature columns are exactly the GMA-7B dictionary columns. BIL is used as benchmark, fallback, and excess-return reference, but BIL is not emitted as a prediction-asset row. `forward_label_window_available` is scheduling metadata only and is excluded from the feature dictionary hash and model-input set.

## Terminal Boundary

After GMA-7B, the feature-store outputs must be inspected and frozen before labels or models are created. GMA-7C must create labels from the frozen feature-store schedule rather than rebuilding features independently.
