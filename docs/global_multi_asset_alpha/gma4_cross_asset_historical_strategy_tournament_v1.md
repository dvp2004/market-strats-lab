# GMA-4A Cross-Asset Historical Strategy Tournament V1

GMA-4A is a contract and registry phase only. It defines the permanent boundary for a future cross-asset historical strategy tournament, but it does not implement a strategy runner, invoke the GMA-2 replay foundation, invoke the GMA-3A simulator, write reports, write data outputs, or produce backtest results.

## Boundary

- `phase_id`: `gma4_cross_asset_historical_strategy_tournament_v1`
- `evidence_class`: `observed_development_evidence`
- `canonical_research_end_date`: `2026-05-01`
- `historical_final_holdout_claim_allowed`: `false`

Historical GMA-4 outputs may not claim a pristine final holdout. Any later candidate assessment must consider net results after costs, drawdown, turnover, concentration, exposure, rolling windows, regime dependence, cost sensitivity, and parameter-neighbour stability. Ranking by highest Sharpe alone is prohibited.

## Safety

The GMA-4A contract fixes the following safety flags:

- `paper_only = true`
- `live_trading_allowed = false`
- `real_money_allowed = false`
- `broker_api_integration_allowed = false`
- `manual_tradingview_packet_generation_allowed = false`
- `active_gma_paper_workflow_influence_allowed = false`
- `prospective_shadow_generation_allowed = false`

No GMA paper workflow, broker integration, order generation, prospective shadow generation, or live-trading path is introduced by this phase.

## Universe

The tradable research universe is exactly:

`SPY`, `QQQ`, `IWM`, `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`, `EFA`, `EEM`, `BIL`, `IEF`, `TLT`, `AGG`, `LQD`, `HYG`, `GLD`, `DBC`.

BIL is the tradeable defensive cash-proxy ETF. Internal accounting `CASH` may exist in a later portfolio simulation, but it is not a universe asset. Symbols outside the fixed list, including `SHY`, `VNQ`, `UUP`, `BTC-USD`, `ETH-USD`, individual stocks, and futures, are prohibited.

## Registry

`configs/global_multi_asset_alpha/gma4_trial_registry_v1.yaml` preregisters exactly 20 trials:

- 3 benchmarks
- 4 absolute-trend trials
- 4 cross-sectional momentum trials
- 3 short-horizon mean-reversion trials
- 3 defensive or risk-regime allocation trials
- 3 simple blends

Every trial starts as `preregistered_not_run` and is ineligible for paper trading, live trading, GMA allocation, prospective shadow, and broker execution. Blend records must reference non-blend component trials and require `component_robustness_required_before_candidate_consideration`.

## Evaluation Contract

The permanent contract predeclares cost scenarios, evaluation scopes, regime windows, and scoreboard columns in `configs/global_multi_asset_alpha/gma4_cross_asset_tournament_v1.yaml`. The code-level validation API is:

- `load_gma4_tournament_config(path)`
- `load_gma4_trial_registry(path)`
- `validate_gma4_contract(config, registry)`
- `build_gma4_contract_summary(config, registry)`

These functions validate configuration and registry structure only. They do not run any historical tournament and do not produce candidates.

## GMA-4B Replay Adapter

GMA-4B adds `src/market_strats/global_multi_asset/gma4_replay_adapter.py` as an in-memory adapter for future tournament work. The adapter validates the fixed 22-ETF universe, supports only generic rebalance schedules, and delegates portfolio accounting to the GMA-3A simulation seam.

The adapter does not load files, download data, write reports, write output data, create a CLI command, generate TradingView packets, submit broker orders, create a prospective-shadow release, run the 20 preregistered trials, or claim a candidate.

Supported scheduling primitives:

- `weekly_friday_next_open`
- `monthly_last_session_next_open`

Both primitives preserve the existing next-valid-session-open execution convention. Same-close execution remains prohibited.

## GMA-4E Cash Adoption And Run History

GMA-4E uses the existing validated GMA-3A historical tournament cash series as the isolated GMA-4 cash input. The copied GMA-4 bundle file is:

`data/global_multi_asset_alpha/gma4_fixed_22_etf_v1/cash/canonical_cash_accrual.csv`

The copy retains only fixed-22 common-session accrual intervals through `2026-05-01`, preserves the source `period_return` values, records source and copied-file hashes in the GMA-4 bundle manifest, and labels the methodology as derived from the existing GMA historical tournament cash series rather than a newly introduced cash methodology.

GMA-4E also writes local comparison files under:

`reports/global_multi_asset_alpha/gma4_cross_asset_tournament_v1/`

- `gma4_tournament_run_history_v1.csv`
- `gma4_latest_results_v1.csv`
- `gma4_latest_results_v1.md`

These files are historical research records only. They do not create paper orders, broker integration, prospective shadow records, strategy candidates, or allocation decisions.
