# Alpaca Execution Harness V0

This folder is an execution-safety experiment.

The QQQ 1-share paper bot is not the final strategy. It is Execution Harness V0 / Broker Plumbing Test. Its purpose is to prove that paper-broker connectivity, signal-to-intent translation, duplicate-order blocking, closed-market blocking, open-order detection, logs, and reports can be handled safely.

The real strategy engine is GMA: Global Multi-Asset Alpha. GMA owns the strategy research, feature, replay, portfolio allocation, risk controls, paper packet, and reconciliation layers.

Alpaca may later execute approved GMA portfolio targets where supported. That future path must remain broker-neutral until execution guards, paper-only status, and reconciliation are validated.

Current order policy:

- Paper-only.
- 1 share maximum for the current harness test.
- Orders disabled unless explicitly enabled through all required safety gates.
- No live trading.
- No real money.
- No broker/API use unless intentionally running the guarded paper harness.

API keys were exposed earlier and must be rotated before further broker/API use.

## Intended Boundary

```text
GMA target portfolio
-> broker-neutral order intent
-> Alpaca paper adapter
-> broker paper order
-> fill log
-> reconciliation back into repository
```

## What Must Not Happen

- No live orders.
- No secrets in repo.
- No automatic strategy promotion.
- No scaling beyond controlled paper tests.
- No treating QQQ MA sweep as the main strategy system.
- No duplicate strategy research architecture under this folder.

## Observed Harness Interface

Current harness files use `paper_bot_config.yaml` to define one active QQQ signal and preview signals. The active config currently keeps `paper_only: true`, `orders_enabled: false`, and `max_shares: 1`.

`config_driven_paper_signal.py` currently performs guarded paper-broker plumbing: it reads the active config, evaluates the signal, checks paper endpoint safety, checks position/open orders, blocks duplicate/open-order cases, blocks closed-market cases, and writes JSONL logs. It can import Alpaca SDKs and read environment variables, so it is not the broker-neutral contract layer.

`execution_contract.py` is intentionally narrower: pure dataclasses and validation only, with no Alpaca imports, no file I/O, and no environment reads.
