# GMA Manual Paper Operator Runbook V0

Manual paper only. No live trading. No real money. No broker API. No automatic submission. Do not read or use `.env`.

## Daily Command

Run the full safe daily cycle:

```powershell
.\.venv\Scripts\python -m market_strats.global_multi_asset.cli --config configs/global_multi_asset_alpha/gma3a_full_history_tournament.yaml daily-paper-cycle
```

This runs:

1. `refresh-post-endpoint-market`
2. `run-transparent-tournament`
3. `paper-readiness`

## Readiness Check

To check readiness without refreshing/regenerating:

```powershell
.\.venv\Scripts\python -m market_strats.global_multi_asset.cli --config configs/global_multi_asset_alpha/gma3a_full_history_tournament.yaml paper-readiness
```

Review:

- `manual TradingView entry active`
- `readiness status`
- `execution status`
- `target blocking reason`
- `order packet row count`

The TradingView manual entry sheet is:

```text
reports/global_multi_asset_alpha/gma3a_full_history_tournament/gma3a_manual_tradingview_entry_sheet.md
```

The order packet CSV is:

```text
reports/global_multi_asset_alpha/gma3a_full_history_tournament/gma3a_tradingview_order_packet.csv
```

## Decision Rules

- If readiness is blocked, do nothing.
- If `manual_tradingview_entry_active=False`, do not trade.
- If `order_packet_rows=0`, do not trade.
- If the packet is stale or `retroactive_blocked`, do not trade.
- Only manually enter orders in TradingView Paper when readiness explicitly says manual TradingView entry is active.

Current expected blocked state:

```text
execution_status = retroactive_blocked
target_blocking_reason = non_retroactive_execution_block: execution window 2026-06-18 has passed as of 2026-06-19
```

## Fill Validation

After manually entering an active packet in TradingView Paper, copy/fill:

```text
reports/global_multi_asset_alpha/gma3a_full_history_tournament/gma3a_tradingview_manual_fill_template.csv
```

Validate the user-entered fill file:

```powershell
.\.venv\Scripts\python -m market_strats.global_multi_asset.cli --config configs/global_multi_asset_alpha/gma3a_full_history_tournament.yaml validate-manual-fills --fills path\to\manual_fills.csv
```

Fill rules:

- No inferred fills.
- No fabricated fills.
- Only user-entered TradingView paper fills.
- V0 validation is report-only.
- V0 must not persistently update canonical GMA holdings or cash.

Validation outputs are written under:

```text
reports/global_multi_asset_alpha/gma3a_full_history_tournament/
```

Key files:

- `gma3a_manual_fill_validation_summary.csv`
- `gma3a_manual_fill_row_validation.csv`
- `gma3a_manual_fill_reconciliation.csv`
- `gma3a_manual_fill_validation.md`

## Safety Boundary

This workflow never submits orders. It never connects to Alpaca, TradingView, or any broker API. It is a manual paper process only.
