# GMA-8A Broad Multi-Asset Strategy Tournament Contract V1

GMA-8A is a bounded, design-only preregistration for a future historical strategy tournament. Its active V1 scope is `broad_etf_etp_strategy_tournament_v1`. The programme name does not widen the evidence claim: future GMA-8 V1 results apply only to the two frozen ETF/ETP universe arms and are not evidence for direct commodities, crypto, stock selection, direct futures, or FX.

Highest historical CAGR or Sharpe alone is not a selection rule. A strategy must be judged across costs, turnover, drawdown, chronological folds, and predefined historical regimes. No execution or promotion decision is produced.

## Universe Boundary

The active arms are the ordered Core-22 and Expanded-29 registries in the YAML contract. Expanded-29 retains USO and DBA as historically traded commodity-pool ETPs. Future USO diagnostics must carry `uso_roll_methodology_pre_may_2020_vs_from_may_2020`.

These arms are a new GMA-8 comparison. GMA-6 V1 classifications remain unchanged, Expanded-29 is not a GMA-6 subset or rescue search, and no 27-instrument fallback arm exists.

Individual equities, crypto, direct futures, and FX are deferred until separate point-in-time data, calendar, venue, roll, liquidity, cost, and provenance contracts exist.

## Frozen Grid

The contract explicitly enumerates 80 base strategy templates across nine families. Every template applies to both arms, producing exactly 160 preregistered arm trials. The deterministic grid hash is recorded in the YAML contract, generated CSV registry, lock, and execution manifest.

The grid is finite. No parameter combination is deferred to GMA-8B, and no template may be added, removed, or changed after any GMA-8 result is viewed. Learned predictive ensembles are excluded because GMA-7 V1 ended fail-closed with no qualifying ensemble.

## Evaluation Boundary

Development and selection are fixed to 2007-05-30 through 2020-12-31. The GMA-8-specific outer evaluation starts on 2021-01-04 and ends at the GMA-8B frozen data endpoint. GMA-8B must pin that endpoint before any market data is read. This outer period is not a pristine programme-wide holdout and may not influence strategy selection, parameters, universes, or exclusions.

Each arm's monthly equal-weight portfolio, including BIL, is its primary active-return comparator. SPY and BIL are reference benchmarks only. All strategies are long-only and unlevered, gross exposure cannot exceed 1.00, risk overlays may only reduce risky exposure, and residual weight goes to BIL.

Fold and regime concentration use positive active-return contributions only. A zero denominator fails the corresponding gate. Regime windows are descriptive reporting windows, not tuning periods, and the recent geopolitical-stress window ends only at the pre-pinned GMA-8B endpoint.

## Design-Only Validation

The generator reads the YAML contract and emits registries, a preregistration, a lock, and an execution manifest. It does not read market data, calculate indicators, fit models, run backtests, rank strategies, generate targets, open paper sessions, connect to a broker, or create a live path.

After review, the next separate phase is GMA-8B: the point-in-time historical data-universe and provenance contract for the active ETF/ETP arms.
