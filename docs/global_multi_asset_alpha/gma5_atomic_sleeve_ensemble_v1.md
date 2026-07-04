# GMA-5A Atomic Sleeve Walk-Forward Ensemble

GMA-5A is a historical research-only ensemble over four manually locked GMA-4 atomic
sleeves:

- `gma4_abs_trend_12m_equal_weight_v1`
- `gma4_xsmom_12m_top5_inverse_vol_v1`
- `gma4_defensive_drawdown_guard_v1`
- `gma4_defensive_spy_200d_rotation_v1`

The XSMOM top-3 alternate, all GMA-4 blends, and GMA-4 benchmarks are comparison
references only. They are not learned sleeve inputs.

## Evidence Status

The phase is labelled `observed_development_evidence` and
`not_a_pristine_final_holdout`. Highest historical CAGR or Sharpe alone is not a
selection rule. No execution or promotion decision is produced.

## Variants

GMA-5A implements exactly three ensemble variants:

- `gma5_equal_weight_atomic_sleeves_v1`
- `gma5_risk_weighted_atomic_sleeves_v1`
- `gma5_fixed_alpha_ridge_atomic_ensemble_v1`

The equal-weight variant assigns 25% to each atomic sleeve. The risk-weighted
variant uses a fixed formula from configuration after 36 completed monthly sleeve
observations. The ridge variant uses a fixed alpha from configuration, a rolling
60-month training window, and only completed target rows strictly before the
current monthly decision date.

## Portfolio Accounting

Each atomic sleeve first produces its frozen ETF target weights. GMA-5A then
combines those targets as:

```text
composite_etf_target_weight = sleeve_allocation_weight * sleeve_etf_target_weight
```

Overlapping ETF positions are netted before replay. Any residual allocation from
zero predictions or sleeve and family caps goes to `BIL`. The resulting composite
ETF targets, not sleeve equity curves, are routed through the shared replay
adapter so trades, turnover, costs, equity, and drawdowns are measured from the
same accounting path as GMA-4.

## Controls

The two defensive sleeves share the `defensive_risk_regime` family, so the 50%
family cap applies jointly to both defensive sleeves. The 40% individual sleeve
cap is applied before the family cap. HHI is not a learned feature or weight input;
the manifest records whether frozen GMA-4 scoreboard HHI values were available.

## Command

```powershell
python -m market_strats.global_multi_asset.gma5_atomic_sleeve_ensemble `
  --config configs\global_multi_asset_alpha\gma5_atomic_sleeve_ensemble_v1.yaml
```

This command uses existing local frozen inputs only. It does not rebuild the
GMA-4 tournament, fetch data, or create any paper, broker, live, or
prospective-shadow path.
