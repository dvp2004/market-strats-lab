from __future__ import annotations

from pathlib import Path
from datetime import datetime
import pandas as pd
import math


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiments" / "llm_alpaca_paper_bot"
LOG_DIR = REPO_ROOT / "paper_bot_logs"
OUT_PATH = EXP_DIR / "STRATEGY_RESEARCH_LOG.md"


FILES = {
    "initial_backtest": LOG_DIR / "historical_strategy_backtest_summary.csv",
    "strategy_tournament": LOG_DIR / "strategy_tournament_summary.csv",
    "robust_full": LOG_DIR / "robust_strategy_tournament_full_summary.csv",
    "robust_period": LOG_DIR / "robust_strategy_tournament_period_summary.csv",
    "event_replay": LOG_DIR / "event_replay_tournament_summary.csv",
    "event_period": LOG_DIR / "event_replay_tournament_period_summary.csv",
    "ma_sweep": LOG_DIR / "ma_parameter_sweep_summary.csv",
    "ma_viable": LOG_DIR / "ma_parameter_sweep_viable.csv",
    "ma_cluster": LOG_DIR / "ma_parameter_sweep_qcc_cluster.csv",
    "paper_signal_log": LOG_DIR / "qqq_50_200_paper_signal.jsonl",
}


def read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def clean_value(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass

    if isinstance(x, float):
        if math.isnan(x):
            return ""
        if abs(x - int(x)) < 1e-9:
            return str(int(x))
        return f"{x:.3f}"

    return str(x)


def pct(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
        return f"{float(x):.2f}%"
    except Exception:
        return str(x)


def md_table(df: pd.DataFrame, cols: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_No data available._"

    x = df.copy().head(max_rows)

    for col in cols:
        if col not in x.columns:
            x[col] = ""

    x = x[cols].copy()

    for col in x.columns:
        if col in {"cagr_pct", "total_return_pct", "ann_vol_pct", "max_drawdown_pct"}:
            x[col] = x[col].apply(pct)
        else:
            x[col] = x[col].apply(clean_value)

    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in x.values.tolist()]

    return "\n".join([header, sep] + rows)


def find_strategy(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if df.empty or "strategy" not in df.columns:
        return pd.DataFrame()
    return df[df["strategy"] == strategy].copy()


def first_available(strategy: str, sources: list[tuple[str, pd.DataFrame]]) -> dict:
    for source_name, df in sources:
        hit = find_strategy(df, strategy)
        if not hit.empty:
            row = hit.iloc[0].to_dict()
            row["source"] = source_name
            return row
    return {
        "strategy": strategy,
        "source": "missing",
    }


def current_candidate_table(event: pd.DataFrame, ma: pd.DataFrame) -> pd.DataFrame:
    sources = [
        ("ma_parameter_sweep", ma),
        ("corrected_event_replay", event),
    ]

    strategies = [
        ("Benchmark", "SPY_buy_hold", "Minimum hurdle"),
        ("Benchmark", "QQQ_buy_hold", "High-return but high-drawdown benchmark"),
        ("Benchmark", "XLK_buy_hold", "Sector concentration benchmark"),
        ("Current paper bot", "QQQ_50_200_cross", "Implemented 1-share paper candidate"),
        ("Research candidate", "QQQ_100_225_cross", "Strongest QQQ cross candidate from MA sweep"),
        ("Research candidate", "QQQ_75_300_cross", "Strong slow-trend candidate"),
        ("Research candidate", "QQQ_100_250_cross", "Strong nearby QQQ cross candidate"),
        ("Research candidate", "QQQ_50_250_cross", "Nearby variant showing cluster support"),
        ("Research candidate", "QQQ_40_200_cross", "Nearby variant showing cluster support"),
        ("Conservative candidate", "QQQ_above_175_cash", "Lower drawdown above-MA rule"),
        ("Conservative candidate", "QQQ_above_200_cash", "Simple price-above-MA rule"),
        ("Conservative candidate", "XLK_above_250_cash", "Strong XLK above-MA candidate"),
        ("Parked", "core_inverse_vol_60d", "Good risk metrics but too much turnover"),
    ]

    rows = []

    for category, strategy, note in strategies:
        row = first_available(strategy, sources)
        rows.append(
            {
                "category": category,
                "strategy": strategy,
                "source": row.get("source", ""),
                "symbol": row.get("symbol", ""),
                "rule_type": row.get("rule_type", ""),
                "fast": row.get("fast", ""),
                "slow": row.get("slow", ""),
                "cagr_pct": row.get("cagr_pct", ""),
                "sharpe_0rf": row.get("sharpe_0rf", ""),
                "max_drawdown_pct": row.get("max_drawdown_pct", ""),
                "avg_exposure": row.get("avg_exposure", ""),
                "trade_count": row.get("trade_count", row.get("rebalance_days", "")),
                "note": note,
            }
        )

    return pd.DataFrame(rows)


def section_status(path: Path) -> str:
    return "present" if path.exists() else "missing"


def main() -> None:
    initial = read_csv(FILES["initial_backtest"])
    tournament = read_csv(FILES["strategy_tournament"])
    robust_full = read_csv(FILES["robust_full"])
    event = read_csv(FILES["event_replay"])
    event_period = read_csv(FILES["event_period"])
    ma = read_csv(FILES["ma_sweep"])
    ma_viable = read_csv(FILES["ma_viable"])
    ma_cluster = read_csv(FILES["ma_cluster"])

    for df in [initial, tournament, robust_full, event, event_period, ma, ma_viable, ma_cluster]:
        if not df.empty and "cagr_pct" in df.columns:
            df.sort_values(["cagr_pct", "sharpe_0rf"], ascending=False, inplace=True, na_position="last")

    candidates = current_candidate_table(event, ma)

    main_cols = [
        "category",
        "strategy",
        "source",
        "symbol",
        "rule_type",
        "fast",
        "slow",
        "cagr_pct",
        "sharpe_0rf",
        "max_drawdown_pct",
        "avg_exposure",
        "trade_count",
        "note",
    ]

    compact_cols = [
        "strategy",
        "cagr_pct",
        "sharpe_0rf",
        "max_drawdown_pct",
        "ann_vol_pct",
        "avg_exposure",
        "trade_count",
    ]

    sweep_cols = [
        "strategy",
        "symbol",
        "rule_type",
        "fast",
        "slow",
        "cagr_pct",
        "sharpe_0rf",
        "max_drawdown_pct",
        "ann_vol_pct",
        "avg_exposure",
        "trade_count",
    ]

    period_cols = [
        "period",
        "strategy",
        "cagr_pct",
        "sharpe_0rf",
        "max_drawdown_pct",
        "avg_exposure",
        "trade_count",
    ]

    md = f"""# Strategy Research Log — LLM Alpaca Paper Bot

_Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}_

## Current Purpose

This file tracks the separate Alpaca paper-bot strategy experiment inside:

`experiments\\llm_alpaca_paper_bot`

The goal is to avoid repeating tests, losing context, or confusing older flawed results with current findings.

This log is research documentation only. It is not a live-trading approval.

---

## Current Status

- Current implemented paper bot: `QQQ_50_200_cross`
- Current paper sizing: 1 QQQ share only
- Current execution mode should remain paper-only
- Main research question now: should `QQQ_50_200_cross` stay as default, or should a stronger QQQ MA variant replace it after further validation?
- API keys were exposed earlier and should be rotated before continued broker/API use.

---

## Main Candidate Table

{md_table(candidates, main_cols, max_rows=50)}

---

## What We Tested

### 1. Initial Historical Backtest

File: `paper_bot_logs\\historical_strategy_backtest_summary.csv`  
Status: `{section_status(FILES["initial_backtest"])}`

Purpose:
- Quick first-pass test on simple ETF strategies.
- Included SPY buy-and-hold, equal-weight 5 ETF, crude risk-switch, monthly momentum, and SPY pullback logic.

Result:
- Most first-pass strategies failed to beat SPY convincingly.
- This batch was useful mainly for rejecting weak simple ideas.

Top rows:

{md_table(initial, compact_cols, max_rows=10)}

---

### 2. Strategy Tournament

File: `paper_bot_logs\\strategy_tournament_summary.csv`  
Status: `{section_status(FILES["strategy_tournament"])}`

Purpose:
- Expanded the first tests to include QQQ, trend filters, momentum variants, and defensive rules.

Result:
- QQQ trend filters started showing promise.
- Early results were not enough because the initial Alpaca-data window was too short.

Top rows:

{md_table(tournament, compact_cols, max_rows=10)}

---

### 3. Robust Adjusted-Data Tournament

File: `paper_bot_logs\\robust_strategy_tournament_full_summary.csv`  
Status: `{section_status(FILES["robust_full"])}`

Purpose:
- Longer adjusted-price test from 2006 onward.
- Included QQQ, SPY, GLD, TLT, IWM, XLK, and sector ETFs.

Result:
- QQQ/XLK buy-and-hold had strong CAGR but drawdowns around the -53% zone.
- QQQ trend-following survived as a serious candidate.
- This led to event-style replay testing.

Top rows:

{md_table(robust_full, compact_cols, max_rows=15)}

---

### 4. Corrected Event-Style Replay

File: `paper_bot_logs\\event_replay_tournament_summary.csv`  
Status: `{section_status(FILES["event_replay"])}`

Purpose:
- Simulate strategy execution day-by-day through history.
- Uses target allocation changes to trigger simulated trades.
- More realistic than simple vectorized return math.

Important:
- First version overtraded.
- Corrected version fixed buy-and-hold trade counts to 1 and made replay results usable.

Top rows:

{md_table(event, compact_cols, max_rows=15)}

Subperiod rows:

{md_table(event_period, period_cols, max_rows=40)}

---

### 5. Moving-Average Parameter Sweep

File: `paper_bot_logs\\ma_parameter_sweep_summary.csv`  
Status: `{section_status(FILES["ma_sweep"])}`

Purpose:
- Test whether QQQ 50/200 is robust or just one lucky parameter.
- Symbols: QQQ, XLK
- Fast windows: 10, 20, 30, 40, 50, 75, 100
- Slow windows: 100, 125, 150, 175, 200, 225, 250, 300

Result:
- QQQ 50/200 is not isolated.
- A broader QQQ trend-following cluster exists.
- Stronger variants appeared, especially QQQ 100/225, QQQ 75/300, QQQ 100/250, QQQ 50/250, and QQQ 40/200.
- These should not replace the paper bot until walk-forward and subperiod candidate scoring are done.

Top 25 sweep rows:

{md_table(ma, sweep_cols, max_rows=25)}

Viable rows:

{md_table(ma_viable, sweep_cols, max_rows=30)}

QQQ cross cluster around 50/200:

{md_table(ma_cluster, sweep_cols, max_rows=30)}

---

## Current Interpretation

### Keep as Current Paper Bot Default

`QQQ_50_200_cross`

Reason:
- Already implemented.
- Survived corrected event replay.
- Low trade count.
- Better drawdown control than QQQ buy-and-hold.
- Good enough for 1-share paper monitoring.

### Strongest Research Candidate

`QQQ_100_225_cross`

Reason:
- Strongest non-buy-hold candidate in current MA sweep.
- Higher CAGR and Sharpe than QQQ 50/200 in the sweep.
- Still needs walk-forward validation before promotion.

### Other Serious Candidates

- `QQQ_75_300_cross`
- `QQQ_100_250_cross`
- `QQQ_50_250_cross`
- `QQQ_40_200_cross`
- `QQQ_above_175_cash`
- `XLK_above_250_cash`

### Parked

- `core_inverse_vol_60d`
- `core_inverse_vol_120d`

Reason:
- Good risk-adjusted metrics.
- Too much turnover for the current first paper-bot implementation.

---

## Rejections / Not First Priority

| Strategy group | Reason |
|---|---|
| SPY buy-and-hold | Benchmark only. Lower return than viable QQQ/XLK trend candidates. |
| QQQ buy-and-hold | Strong CAGR but very large drawdown. Useful benchmark, not controlled strategy. |
| XLK buy-and-hold | Strong CAGR but sector concentration and very large drawdown. |
| Initial 5-ETF simple strategies | Mostly failed against SPY in first-pass tests. |
| SPY trend-pullback | Low drawdown but weak return/exposure profile. |
| QQQ 200 or TLT/GLD | Weaker after corrected replay than initial vectorized result suggested. |
| Inverse-vol variants | Not rejected permanently; parked due to turnover/operational complexity. |

---

## Current Decision

Do not replace the paper bot yet.

Current default remains:

`QQQ_50_200_cross`

Next challenger:

`QQQ_100_225_cross`

Promotion requires:
1. walk-forward validation,
2. subperiod scoring,
3. candidate-selection report,
4. config-driven paper bot update,
5. no increase above 1-share paper size until order/fill reporting is stable.

---

## Next Required Work

1. Create `select_paper_candidates.py`
   - reads all summary CSVs,
   - scores strategies,
   - creates candidate and rejection CSVs,
   - writes a short markdown decision report.

2. Create walk-forward validation
   - select parameters on past window,
   - test next unseen window,
   - repeat across the full history.

3. Convert the paper bot from hardcoded 50/200 to config-driven MA strategy.

4. Add market-hours / holiday guard.

5. Add daily paper report.

---

## Generated Files Checked

| File | Status |
|---|---|
| `historical_strategy_backtest_summary.csv` | {section_status(FILES["initial_backtest"])} |
| `strategy_tournament_summary.csv` | {section_status(FILES["strategy_tournament"])} |
| `robust_strategy_tournament_full_summary.csv` | {section_status(FILES["robust_full"])} |
| `robust_strategy_tournament_period_summary.csv` | {section_status(FILES["robust_period"])} |
| `event_replay_tournament_summary.csv` | {section_status(FILES["event_replay"])} |
| `event_replay_tournament_period_summary.csv` | {section_status(FILES["event_period"])} |
| `ma_parameter_sweep_summary.csv` | {section_status(FILES["ma_sweep"])} |
| `ma_parameter_sweep_viable.csv` | {section_status(FILES["ma_viable"])} |
| `ma_parameter_sweep_qcc_cluster.csv` | {section_status(FILES["ma_cluster"])} |
| `qqq_50_200_paper_signal.jsonl` | {section_status(FILES["paper_signal_log"])} |
"""

    OUT_PATH.write_text(md, encoding="utf-8")
    print(f"Wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
