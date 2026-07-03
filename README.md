# Market Strats Lab

A research-only repository for transparent, pre-registered systematic strategy research.
This repository does not provide financial advice, investment advice, or trading recommendations.

---

## Important Disclaimer

This project is for **research and education only**.

It is **not** financial advice, investment advice, or a recommendation to buy or sell any security. Historical backtests and model diagnostics can be misleading, particularly when many strategies, assets, parameters, features, and rules have been tested.

Real-world results can differ materially because of data quality and survivorship bias, lookahead and timestamp errors, transaction costs, bid-ask spreads, market impact, taxes, liquidity, order rejection, corporate actions, changing market regimes, behavioural difficulty, model drift, implementation errors, and future market conditions.

**Not connected to a broker. Not live-tradable. Not approved for real-money deployment.**

---

## What This Repository Is

`market-strats-lab` is a **research-only systematic market-strategy repository**.

It documents a structured research process for evaluating rule-based ETF and multi-asset allocation strategies under strict pre-registration, robustness, and cost controls. The goal is to determine whether transparent systematic methods can improve the return / drawdown / liveability trade-off versus passive benchmarks, not to discover a magic trading rule or generate performance marketing.

All code, contracts, and documentation published here represent **research design and historical evidence only**. No execution decision, promotion decision, broker connection, paper-trading session, or real-money action is produced by this release.

---

## GMA-8: Frozen Broad ETF/ETP Historical Tournament

The current published research release is the **Global Multi-Asset 8 (GMA-8) programme**, a frozen, pre-registered broad ETF/ETP historical strategy tournament.

### Research Scope

GMA-8 investigates systematic long-only rule-based allocation across two pre-frozen ETF/ETP universe arms:

- **Core-22**: 22 diversified ETFs spanning equities, bonds, credit, cash, and commodities.
- **Expanded-29**: the Core-22 plus `VNQ, TIP, USO, DBA, SLV, EWG, EWJ`.

Both arms are ETF/ETP-only. Individual equities, direct futures, direct commodities, crypto, and FX are explicitly deferred to separate future research phases with their own point-in-time data, calendar, roll, liquidity, and cost contracts.

### Pre-registered Design (GMA-8A)

- **80 pre-registered base strategy templates** across 9 rule families.
- **160 arm-level trials** (80 templates × 2 universe arms).
- **4 transaction-cost scenarios**: baseline (1 bps), stressed (10 bps), stressed (25 bps), severe (50 bps).
- All templates, arms, cost scenarios, families, and evaluation rules are frozen before any result is viewed. No template may be added, removed, or changed after any GMA-8 result is observed.

### Tournament Results (GMA-8C) — Observed Development Evidence

The frozen tournament was run under GMA-8C. **All GMA-8 findings are observed development evidence, not a pristine final holdout.** The outer evaluation period (from 2021-01-04) was observed after an earlier research phase and may not be used for strategy selection, parameter changes, universe changes, or post-hoc exclusions.

At the stressed 10 bps threshold across six pre-registered historical robustness gates:

- **8 out of 160 arm trials passed all six historical gates** at the stressed-10-bps threshold.
- The eight passers are concentrated in passive references and long-horizon cross-sectional-momentum variants, not eight independent validated discoveries.
- Passing at stressed 10 bps does not establish cost-insensitive performance at severe 50 bps.
- Highest historical CAGR or Sharpe alone is **not** a selection rule.
- A strategy must be judged across costs, turnover, drawdown, chronological folds, and predefined historical regime windows.

These eight gate-passing results are **observed development evidence only**. No execution, paper-trading, broker, promotion, or real-money decision is produced.

---

## Public Code and Contracts

The following GMA-8 files are published in this repository:

| Category | Files |
|---|---|
| **GMA-8A design contract** | `configs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.yaml` |
| **GMA-8C tournament contract** | `configs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.yaml` |
| **GMA-8B public templates** | `configs/global_multi_asset_alpha/public_templates/gma8b_historical_data_provenance_public_template_v1.yaml`<br>`configs/global_multi_asset_alpha/public_templates/gma8b_source_pointer_intake_public_template_v1.yaml` |
| **Design documentation** | `docs/global_multi_asset_alpha/gma8a_broad_multi_asset_tournament_contract_v1.md`<br>`docs/global_multi_asset_alpha/gma8c_frozen_etf_etp_tournament_contract_v1.md`<br>`docs/global_multi_asset_alpha/gma8_public_private_evidence_boundary_v1.md` |
| **Source modules** | `src/market_strats/global_multi_asset/gma8a_broad_multi_asset_tournament_contract.py`<br>`src/market_strats/global_multi_asset/gma8b_historical_data_provenance.py`<br>`src/market_strats/global_multi_asset/gma8b_source_pointer_intake.py`<br>`src/market_strats/global_multi_asset/gma8c_frozen_etf_etp_tournament.py` |
| **Unit tests** | `tests/test_gma8a_broad_multi_asset_tournament_contract.py`<br>`tests/test_gma8b_historical_data_provenance.py`<br>`tests/test_gma8b_source_pointer_intake.py`<br>`tests/test_gma8c_frozen_etf_etp_tournament.py`<br>`tests/test_gma8_public_template_boundary.py` |

All public GMA-8 tests use synthetic fixtures or fail-closed private-input checks only. No test reads private market data, makes network requests, or accesses private evidence files.

### GMA-8B Public Templates

The GMA-8B data-provenance phase requires private immutable adjusted-price evidence (a local GMA-6 snapshot) that is **not included in this repository**. A public clone cannot reproduce the historical evidence without independently supplied verified private inputs.

Two public non-runnable configuration templates are provided under `configs/global_multi_asset_alpha/public_templates/`. These cannot be executed as-is; every machine-specific path is replaced by a `REQUIRED_PRIVATE_*` placeholder. The GMA-8B source modules raise an explicit error if any private input is absent, path-mismatched, or hash-mismatched. See `docs/global_multi_asset_alpha/gma8_public_private_evidence_boundary_v1.md` for a full explanation.

---

## Older Experimental Code

This repository also contains earlier experimental work from prior research phases (GMA-1 through GMA-7, plus individual-equity and macro research modules). That code is part of the research history and is **separate from the GMA-8 release evidence**. It should not be interpreted as the current canonical GMA conclusion or as a validated published result. The GMA-8 programme is the current frozen, pre-registered research release.

---

## What Is Intentionally Excluded from Git

The following are excluded by `.gitignore` and must never be committed:

| Excluded content | Reason |
|---|---|
| `data/raw/` and `data/global_multi_asset_alpha/` | Raw and processed price data; not redistributable |
| `reports/` | Generated evidence outputs; not part of the public code release |
| `.venv/` | Python virtual environment; recreate from `pyproject.toml` |
| `.env`, `*.local` | Secrets and machine-specific environment settings |
| `paper_bot_state/`, `paper_bot_logs/` | Paper-trading runtime state |
| `state/global_multi_asset_alpha/` | Operational state |
| `experiments/` | Scratch and exploratory work |

---

## Repository Structure

```
src/market_strats/global_multi_asset/   GMA source modules
configs/global_multi_asset_alpha/       YAML contracts and public templates
docs/global_multi_asset_alpha/          Research documentation
tests/                                  Unit tests (synthetic fixtures only)
reports/                                [local only — excluded by .gitignore]
data/                                   [local only — excluded by .gitignore]
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/test_gma8a_broad_multi_asset_tournament_contract.py
pytest tests/test_gma8_public_template_boundary.py
```

GMA-8B and GMA-8C tests require local private evidence supplied separately by the operator. They are excluded from the default public CI run.

---

## Research-Only / Not Financial Advice

This project does not constitute financial advice. Past historical results do not guarantee future performance. This repository is shared for research transparency and methodology documentation only.
