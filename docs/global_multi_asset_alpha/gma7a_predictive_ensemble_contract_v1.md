# GMA-7A Predictive Ensemble Research Contract V1

This document preregisters a design-only predictive multi-asset ETF research contract.

This is observed development evidence and not a pristine final holdout.
The 2021-01-04 through 2026-05-01 period is a GMA-7 model-specific lockbox.
Highest historical CAGR or Sharpe alone is not a selection rule.
No execution or promotion decision is produced.

## Active and Deferred Cohorts

| cohort | status |
| --- | --- |
| etf_multi_asset_core_v1 | active |
| crypto_directional_v1 | deferred |
| direct_futures_and_commodity_v1 | deferred |

## Core-22 Universe

SPY, QQQ, IWM, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, EFA, EEM, BIL, IEF, TLT, AGG, LQD, HYG, GLD, DBC

## Partitions and Timing

Development and nested walk-forward: 2007-05-30 through 2020-12-31.
Locked outer evaluation: 2021-01-04 through 2026-05-01, the GMA-7 model-specific lockbox.
Label horizon and purge embargo are both 20 trading sessions.
Targets start at the next tradable session after the decision timestamp and exclude decision-session close-to-close return.

## Feature Families

- trend_and_momentum
- short_horizon_mean_reversion
- realised_volatility_drawdown_and_correlation_risk
- cross_asset_regime_context

## Model Blocks

| model block | role |
| --- | --- |
| regularised_linear_return_rank_model | return/risk model family |
| bounded_gradient_boosted_tree_return_rank_model | return/risk model family |
| risk_downside_model | risk_overlay_only_not_return_score_component |
| deterministic_cross_asset_regime_model | qualifying_return_score_component_candidate |
| fixed_equal_weight_ensemble_of_qualifying_return_scores | fixed_equal_weight_return_score_ensemble |

## Ensemble and Risk Overlay

Return scores come only from the regularised linear, bounded tree, and deterministic regime components. Qualifying component scores are cross-sectionally standardised at the decision timestamp and combined with fixed equal weights only. The risk/downside model is a risk overlay only and cannot be averaged into return scores.

## Portfolio Construction

The shared monthly score-to-portfolio rule selects up to the top 5 non-BIL assets with positive standardised scores, equal-weights selected risky assets, assigns residual weight to BIL, caps each risky asset at 0.20, and caps total risky exposure at 1.00. Cost scenarios are baseline_1bps, stressed_10bps, stressed_25bps, and severe_50bps.

## P-1 Boundary

P-1 strategy = frozen GMA-5 equal-weight atomic sleeve portfolio. P-1 purpose = forward operational and performance observation. P-1 rule changes = prohibited after its manual-paper contract is locked. GMA-7 research outputs = cannot alter P-1 rules.

## Scope Boundary

GMA-7A creates design and validation-contract evidence only. It does not fetch data, construct a feature store, fit a model, calculate forecasts, generate targets, run a strategy, replay a portfolio, calculate performance, create a paper account, connect to a broker, or create a live-trading path.
