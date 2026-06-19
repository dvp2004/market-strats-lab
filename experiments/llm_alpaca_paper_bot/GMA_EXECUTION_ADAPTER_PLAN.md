# GMA to Alpaca Execution Adapter Plan

This is a future design note only. It does not implement order submission.

GMA remains the main multi-asset portfolio strategy research and paper-trading system. The Alpaca experiment folder should only provide a broker-paper execution harness, adapter design, guard validation, and later order/fill logging.

## Observed GMA Interface Shape

Inspected GMA files:

- `configs\global_multi_asset_alpha\gma3a_full_history_tournament.yaml`
- `src\market_strats\global_multi_asset\gma3a_tournament.py`
- `reports\global_multi_asset_alpha\gma3a_full_history_tournament\gma3a_tradingview_order_packet.csv`
- `reports\global_multi_asset_alpha\gma3a_full_history_tournament\gma3a_tradingview_manual_fill_template.csv`

Observed configuration boundary:

- `paper_only: true`
- `live_trading_allowed: false`
- `real_money_allowed: false`
- `broker_api_integration_allowed: false`
- manual TradingView packet mode has `broker_submission_allowed: false`

Observed order packet schema:

```text
order_packet_id
account_id
decision_date
expected_execution_date
symbol
asset_class
side
current_confirmed_quantity
target_quantity
order_quantity
target_weight
reference_price
reference_price_date
reason_codes
contributing_strategies
paper_only
live_trading_allowed
real_money_allowed
blocking_reason
```

Observed manual fill template schema:

```text
order_packet_id
symbol
submitted_quantity
submitted_side
submitted_at
fill_status
filled_quantity
fill_price
fill_timestamp
rejection_reason
partial_fill_reason
notes
```

The inspected packet files are currently header-only at the configured report path. That means the adapter should treat missing rows as "no current GMA paper order intent", not as an invitation to infer orders from summary metrics.

## Future Bridge

```text
Read GMA generated order packet
-> convert rows to broker-neutral BrokerOrderIntent objects
-> apply execution guards
-> only then allow an Alpaca paper adapter to submit orders
-> record fills
-> reconcile fills back to GMA actual holdings/cash
```

## Guard Requirements

Before any future Alpaca paper adapter can submit an order:

- GMA packet row must exist.
- GMA packet must be paper-only.
- GMA packet must not permit live trading or real money.
- Alpaca adapter must use broker-neutral `BrokerOrderIntent` first.
- Execution guard must pass.
- Duplicate open-order checks must pass.
- Market/session guard must pass.
- Quantity limits must pass.
- Fill records must be written and reconciled back into GMA.

## Non-Goals For This Task

- No execution implementation.
- No broker calls.
- No Alpaca imports.
- No environment reads.
- No changes to GMA strategy rules, gates, weights, historical selection, or portfolio targets.
- No duplicate portfolio research system under `experiments\llm_alpaca_paper_bot`.
