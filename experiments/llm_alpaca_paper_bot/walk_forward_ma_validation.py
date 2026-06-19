from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_DIR = REPO_ROOT / "experiments" / "llm_alpaca_paper_bot"
LOG_DIR = REPO_ROOT / "paper_bot_logs"

CLOSE_PATH = LOG_DIR / "robust_adjusted_close_prices.csv"
SWEEP_SUMMARY_PATH = LOG_DIR / "ma_parameter_sweep_summary.csv"
SWEEP_VIABLE_PATH = LOG_DIR / "ma_parameter_sweep_viable.csv"
SELECTION_SUMMARY_PATH = LOG_DIR / "paper_candidate_selection_summary.csv"
CONFIG_PATH = BOT_DIR / "paper_bot_config.yaml"

WINDOWS_PATH = LOG_DIR / "walk_forward_ma_validation_windows.csv"
FIXED_PATH = LOG_DIR / "walk_forward_ma_validation_fixed_candidates.csv"
SUMMARY_PATH = LOG_DIR / "walk_forward_ma_validation_summary.csv"
REPORT_PATH = LOG_DIR / "walk_forward_ma_validation_report.md"

INITIAL_CASH = 100_000.0
TRANSACTION_COST_BPS = 2.0
SLIPPAGE_BPS = 3.0
FRICTION = (TRANSACTION_COST_BPS + SLIPPAGE_BPS) / 10_000.0

TRAIN_YEARS = 8
TEST_YEARS = 2
STEP_YEARS = 2
MIN_TRAIN_DAYS = 252 * 6
MIN_TEST_DAYS = 252

MINIMUM_CANDIDATES = [
    "QQQ_50_200_cross",
    "QQQ_75_250_cross",
    "QQQ_100_225_cross",
    "QQQ_100_250_cross",
    "QQQ_75_300_cross",
    "QQQ_50_250_cross",
    "QQQ_40_200_cross",
    "QQQ_above_175_cash",
    "QQQ_above_200_cash",
    "SPY_buy_hold",
    "QQQ_buy_hold",
]

FIXED_TEST_CANDIDATES = [
    "QQQ_50_200_cross",
    "QQQ_75_250_cross",
    "QQQ_100_225_cross",
    "QQQ_above_175_cash",
    "SPY_buy_hold",
    "QQQ_buy_hold",
]


@dataclass(frozen=True)
class CandidateSpec:
    strategy: str
    symbol: str
    rule_type: str
    fast: int | None = None
    slow: int | None = None
    deployable: bool = True


def load_close() -> pd.DataFrame:
    close = pd.read_csv(CLOSE_PATH, index_col=0, parse_dates=True)
    close = close.sort_index().ffill().dropna(how="all")
    required = ["SPY", "QQQ"]
    missing = [symbol for symbol in required if symbol not in close.columns]
    if missing:
        raise RuntimeError(f"Missing required close columns: {missing}")
    return close.dropna(subset=required)[required]


def read_active_strategy_name() -> str:
    if not CONFIG_PATH.exists():
        return "unknown"
    text = CONFIG_PATH.read_text(encoding="utf-8")
    in_active = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("active_strategy:"):
            in_active = True
            continue
        if in_active and line and not line.startswith(" "):
            break
        if in_active and line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def parse_candidate_name(strategy: str) -> CandidateSpec:
    if strategy in {"SPY_buy_hold", "QQQ_buy_hold"}:
        return CandidateSpec(
            strategy=strategy,
            symbol=strategy.split("_", 1)[0],
            rule_type="buy_hold",
            deployable=False,
        )

    if strategy.startswith("QQQ_above_") and strategy.endswith("_cash"):
        parts = strategy.split("_")
        return CandidateSpec(
            strategy=strategy,
            symbol="QQQ",
            rule_type="above_ma",
            slow=int(parts[2]),
            deployable=True,
        )

    if strategy.startswith("QQQ_") and strategy.endswith("_cross"):
        parts = strategy.split("_")
        return CandidateSpec(
            strategy=strategy,
            symbol="QQQ",
            rule_type="cross",
            fast=int(parts[1]),
            slow=int(parts[2]),
            deployable=True,
        )

    raise ValueError(f"Unsupported candidate name: {strategy}")


def load_candidate_specs() -> dict[str, CandidateSpec]:
    names = set(MINIMUM_CANDIDATES)

    for path in [SWEEP_VIABLE_PATH, SELECTION_SUMMARY_PATH]:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if "strategy" in df.columns:
            names.update(str(value) for value in df["strategy"].dropna().head(40))

    specs: dict[str, CandidateSpec] = {}
    for name in sorted(names):
        try:
            specs[name] = parse_candidate_name(name)
        except (ValueError, IndexError):
            continue

    return specs


def weights_for_candidate(close: pd.DataFrame, spec: CandidateSpec) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)

    if spec.rule_type == "buy_hold":
        weights[spec.symbol] = 1.0
        return weights

    px = close[spec.symbol]
    if spec.rule_type == "above_ma":
        signal = px > px.rolling(int(spec.slow)).mean()
    elif spec.rule_type == "cross":
        signal = px.rolling(int(spec.fast)).mean() > px.rolling(int(spec.slow)).mean()
    else:
        raise ValueError(f"Unsupported rule type: {spec.rule_type}")

    weights.loc[signal.fillna(False), spec.symbol] = 1.0
    return weights


def replay(close: pd.DataFrame, raw_weights: pd.DataFrame) -> tuple[pd.Series, pd.Series, int]:
    raw_weights = raw_weights.reindex(close.index).fillna(0.0).clip(lower=0.0)

    cash = INITIAL_CASH
    shares = pd.Series(0, index=close.columns, dtype=int)

    equity_rows: list[tuple[pd.Timestamp, float]] = []
    exposure_rows: list[tuple[pd.Timestamp, float]] = []
    trade_count = 0

    pending_weights: pd.Series | None = None
    last_executed_weights: pd.Series | None = None

    for dt in close.index:
        prices = close.loc[dt]

        should_execute = False
        if pending_weights is not None:
            if last_executed_weights is None:
                should_execute = True
            else:
                weight_change = (pending_weights - last_executed_weights).abs().sum()
                should_execute = bool(weight_change > 0.001)

        if pending_weights is not None and should_execute:
            equity_before = cash + float((shares * prices).sum())
            target_values = pending_weights * equity_before

            for symbol in close.columns:
                price = float(prices[symbol])
                if pd.isna(price) or price <= 0:
                    continue

                target_shares = math.floor(float(target_values[symbol]) / (price * (1.0 + FRICTION)))
                diff = int(target_shares - shares[symbol])

                if diff > 0:
                    affordable = math.floor(cash / (price * (1.0 + FRICTION)))
                    qty = min(diff, affordable)
                    if qty > 0:
                        cash -= qty * price * (1.0 + FRICTION)
                        shares[symbol] += qty
                        trade_count += 1
                elif diff < 0:
                    qty = min(abs(diff), int(shares[symbol]))
                    if qty > 0:
                        cash += qty * price * (1.0 - FRICTION)
                        shares[symbol] -= qty
                        trade_count += 1

            last_executed_weights = pending_weights.copy()

        equity = cash + float((shares * prices).sum())
        exposure = 0.0 if equity <= 0 else float((shares * prices).sum()) / equity

        equity_rows.append((dt, equity))
        exposure_rows.append((dt, exposure))
        pending_weights = raw_weights.loc[dt]

    equity = pd.Series(dict(equity_rows)).sort_index()
    exposure = pd.Series(dict(exposure_rows)).sort_index()
    return equity, exposure, trade_count


def compute_metrics(equity: pd.Series, exposure: pd.Series, trade_count: int) -> dict[str, float | int]:
    returns = equity.pct_change().fillna(0.0)
    drawdown = equity / equity.cummax() - 1.0
    years = max(len(equity) / 252.0, 1 / 252.0)
    start_value = float(equity.iloc[0])
    final_value = float(equity.iloc[-1])
    cagr = (final_value / start_value) ** (1 / years) - 1.0
    volatility = float(returns.std() * np.sqrt(252))
    sharpe = np.nan if volatility == 0 else float(returns.mean() * 252 / volatility)

    return {
        "days": int(len(equity)),
        "final_equity": round(final_value, 2),
        "total_return_pct": round((final_value / start_value - 1.0) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "ann_vol_pct": round(volatility * 100, 2),
        "sharpe_0rf": np.nan if pd.isna(sharpe) else round(sharpe, 3),
        "max_drawdown_pct": round(float(drawdown.min()) * 100, 2),
        "avg_exposure": round(float(exposure.mean()), 3),
        "active_days": int((exposure > 0).sum()),
        "trade_count": int(trade_count),
    }


def balanced_score(metrics: dict[str, float | int]) -> float:
    cagr = float(metrics["cagr_pct"])
    sharpe = 0.0 if pd.isna(metrics["sharpe_0rf"]) else float(metrics["sharpe_0rf"])
    max_drawdown = float(metrics["max_drawdown_pct"])
    trade_count = int(metrics["trade_count"])

    score = cagr + (8.0 * sharpe) + (0.35 * max_drawdown)
    if max_drawdown < -35.0:
        score -= abs(max_drawdown + 35.0) * 1.25
    if trade_count > 150:
        score -= (trade_count - 150) * 0.08
    return round(score, 4)


def metric_row(
    strategy: str,
    window_id: int,
    split: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    close: pd.DataFrame,
    weights: pd.DataFrame,
) -> dict[str, object]:
    window_close = close.loc[start:end]
    window_weights = weights.reindex(window_close.index).fillna(0.0)
    equity, exposure, trade_count = replay(window_close, window_weights)
    row: dict[str, object] = {
        "window_id": window_id,
        "split": split,
        "strategy": strategy,
        "start": str(window_close.index[0].date()),
        "end": str(window_close.index[-1].date()),
    }
    row.update(compute_metrics(equity, exposure, trade_count))
    row["balanced_score"] = balanced_score(row)  # type: ignore[arg-type]
    return row


def make_walk_forward_windows(close: pd.DataFrame) -> list[dict[str, pd.Timestamp | int]]:
    first_date = close.index.min()
    last_date = close.index.max()
    start = max(first_date, pd.Timestamp("2006-01-03"))
    windows: list[dict[str, pd.Timestamp | int]] = []
    window_id = 1

    while True:
        train_start = start
        train_end = train_start + pd.DateOffset(years=TRAIN_YEARS) - pd.DateOffset(days=1)
        test_start = train_end + pd.DateOffset(days=1)
        test_end = test_start + pd.DateOffset(years=TEST_YEARS) - pd.DateOffset(days=1)

        train_days = int(len(close.loc[train_start:train_end]))
        test_days = int(len(close.loc[test_start:test_end]))
        if test_start > last_date:
            break
        if train_days >= MIN_TRAIN_DAYS and test_days >= MIN_TEST_DAYS:
            windows.append(
                {
                    "window_id": window_id,
                    "train_start": close.loc[train_start:train_end].index[0],
                    "train_end": close.loc[train_start:train_end].index[-1],
                    "test_start": close.loc[test_start:test_end].index[0],
                    "test_end": close.loc[test_start:test_end].index[-1],
                }
            )
            window_id += 1

        start = start + pd.DateOffset(years=STEP_YEARS)

    return windows


def aggregate_test_rows(rows: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    for strategy, group in rows.groupby("strategy"):
        chained_equity = INITIAL_CASH
        for _, row in group.sort_values("window_id").iterrows():
            chained_equity *= 1.0 + float(row["total_return_pct"]) / 100.0

        qqq_50 = rows[rows["strategy"] == "QQQ_50_200_cross"][
            ["window_id", "total_return_pct", "cagr_pct", "max_drawdown_pct"]
        ].rename(
            columns={
                "total_return_pct": "qqq_50_200_total_return_pct",
                "cagr_pct": "qqq_50_200_cagr_pct",
                "max_drawdown_pct": "qqq_50_200_max_drawdown_pct",
            }
        )
        comp = group.merge(qqq_50, on="window_id", how="left")
        wins_vs_50_200 = int(
            (comp["total_return_pct"] > comp["qqq_50_200_total_return_pct"]).fillna(False).sum()
        )

        summary_rows.append(
            {
                "strategy": strategy,
                "test_window_count": int(len(group)),
                "selected_window_count": int(group.get("selected_strategy", pd.Series(dtype=str)).notna().sum())
                if "selected_strategy" in group.columns
                else 0,
                "chained_final_equity": round(chained_equity, 2),
                "chained_total_return_pct": round((chained_equity / INITIAL_CASH - 1.0) * 100, 2),
                "mean_test_cagr_pct": round(float(group["cagr_pct"].mean()), 2),
                "median_test_cagr_pct": round(float(group["cagr_pct"].median()), 2),
                "mean_test_sharpe": round(float(group["sharpe_0rf"].mean()), 3),
                "worst_test_drawdown_pct": round(float(group["max_drawdown_pct"].min()), 2),
                "total_test_trades": int(group["trade_count"].sum()),
                "wins_vs_qqq_50_200": wins_vs_50_200,
            }
        )

    return pd.DataFrame(summary_rows).sort_values(
        ["chained_total_return_pct", "mean_test_sharpe"],
        ascending=False,
    )


def build_report(
    windows: pd.DataFrame,
    fixed: pd.DataFrame,
    summary: pd.DataFrame,
    active_strategy: str,
) -> str:
    def row_for(strategy: str) -> pd.Series | None:
        found = summary[summary["strategy"] == strategy]
        if found.empty:
            return None
        return found.iloc[0]

    wf = row_for("walk_forward_selected")
    qqq_50 = row_for("QQQ_50_200_cross")
    qqq_75 = row_for("QQQ_75_250_cross")
    qqq_100 = row_for("QQQ_100_225_cross")
    conservative = row_for("QQQ_above_175_cash")

    wf_outperformed = bool(
        wf is not None
        and qqq_50 is not None
        and float(wf["chained_total_return_pct"]) > float(qqq_50["chained_total_return_pct"])
    )
    qqq_75_outperformed = bool(
        qqq_75 is not None
        and qqq_50 is not None
        and float(qqq_75["chained_total_return_pct"]) > float(qqq_50["chained_total_return_pct"])
    )
    qqq_75_drawdown_ok = bool(
        qqq_75 is not None
        and qqq_50 is not None
        and float(qqq_75["worst_test_drawdown_pct"]) >= float(qqq_50["worst_test_drawdown_pct"]) - 2.0
    )
    qqq_75_ready = qqq_75_outperformed and qqq_75_drawdown_ok

    qqq_100_overfit = bool(
        qqq_100 is not None
        and qqq_75 is not None
        and (
            float(qqq_100["wins_vs_qqq_50_200"]) < max(1.0, float(qqq_75["wins_vs_qqq_50_200"]) - 1.0)
            or float(qqq_100["worst_test_drawdown_pct"]) < float(qqq_75["worst_test_drawdown_pct"]) - 3.0
        )
    )

    selected_counts = (
        windows["selected_strategy"].value_counts().rename_axis("strategy").reset_index(name="selected_windows")
        if not windows.empty
        else pd.DataFrame(columns=["strategy", "selected_windows"])
    )

    top_rows = summary.head(8).copy()
    top_table = top_rows[
        [
            "strategy",
            "chained_total_return_pct",
            "mean_test_cagr_pct",
            "mean_test_sharpe",
            "worst_test_drawdown_pct",
            "total_test_trades",
            "wins_vs_qqq_50_200",
        ]
    ].to_markdown(index=False)

    selection_table = selected_counts.to_markdown(index=False)

    primary_candidate = "QQQ_75_250_cross" if qqq_75_ready else active_strategy
    conservative_candidate = "QQQ_above_175_cash" if conservative is not None else active_strategy
    aggressive_candidate = "QQQ_100_225_cross" if qqq_100 is not None else primary_candidate

    replacement_text = (
        "QQQ_75_250_cross is walk-forward supported enough for a no-order promotion review, but the script does not change config."
        if qqq_75_ready
        else "Keep QQQ_50_200_cross active; QQQ_75_250_cross is not strong enough to replace it automatically."
    )
    config_action = (
        "Do not update paper_bot_config.yaml automatically. Next safe step: run QQQ_75_250_cross as a no-order active-candidate dry run before any manual config promotion."
        if qqq_75_ready
        else "Leave paper_bot_config.yaml unchanged and continue preview monitoring."
    )

    lines = [
        "# Walk-Forward MA Validation Report",
        "",
        "Research-only validation. No broker calls, no orders, no live trading, and no config edits were performed.",
        "",
        "## Setup",
        "",
        f"- Active paper-bot config strategy: `{active_strategy}`",
        f"- Train window: {TRAIN_YEARS} years",
        f"- Test window: {TEST_YEARS} years",
        f"- Step: {STEP_YEARS} years",
        f"- Replay friction: {TRANSACTION_COST_BPS:.1f} bps transaction cost + {SLIPPAGE_BPS:.1f} bps slippage",
        "- Execution model: target signal at day T executes on day T+1 when allocation changes.",
        "",
        "## Top Walk-Forward Test Results",
        "",
        top_table,
        "",
        "## Train-Window Selections",
        "",
        selection_table,
        "",
        "## Answers",
        "",
        f"- Did walk-forward selection outperform fixed QQQ 50/200? `{wf_outperformed}`.",
        f"- Did QQQ 75/250 justify replacing QQQ 50/200? `{qqq_75_ready}`. {replacement_text}",
        f"- Is QQQ 100/225 overfit or robust? `{'overfit_or_less_robust' if qqq_100_overfit else 'walk_forward_robust_but_aggressive'}`.",
        f"- Strategy that should remain active now: `{active_strategy if not qqq_75_ready else active_strategy}`.",
        f"- Recommended next implementation step: {config_action}",
        "",
        "## Candidate Roles",
        "",
        f"- Best primary paper candidate: `{primary_candidate}`",
        f"- Best conservative candidate: `{conservative_candidate}`",
        f"- Best aggressive candidate: `{aggressive_candidate}`",
        "",
        "## Rejected Or Cautioned Candidates",
        "",
        "- Buy-and-hold strategies were evaluated as benchmarks but excluded from deployable walk-forward selection.",
        "- Any candidate that only wins in a narrow recent window should remain preview-only until it survives another no-order dry run.",
        "- High trade-count variants are penalized because this bot is intended to stay simple and operationally quiet.",
        "",
        "## Data Sufficiency",
        "",
        f"- Walk-forward test windows evaluated: {len(windows)}",
        "- The analysis uses available adjusted close data only. It does not model taxes, borrow constraints, intraday fills, or broker-specific execution behavior.",
        "",
        "## Safety",
        "",
        "- No orders submitted.",
        "- No Alpaca API calls made.",
        "- No secrets read or printed.",
        "- `paper_bot_config.yaml` was not modified.",
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    close = load_close()
    specs = load_candidate_specs()
    active_strategy = read_active_strategy_name()

    weights_by_strategy = {
        name: weights_for_candidate(close, spec)
        for name, spec in specs.items()
        if spec.symbol in close.columns
    }
    windows = make_walk_forward_windows(close)
    if not windows:
        raise RuntimeError("No valid walk-forward windows could be created from available data.")

    window_rows: list[dict[str, object]] = []
    fixed_rows: list[dict[str, object]] = []
    selected_test_rows: list[dict[str, object]] = []

    deployable_names = [name for name, spec in specs.items() if spec.deployable and name in weights_by_strategy]

    for window in windows:
        window_id = int(window["window_id"])
        train_start = pd.Timestamp(window["train_start"])
        train_end = pd.Timestamp(window["train_end"])
        test_start = pd.Timestamp(window["test_start"])
        test_end = pd.Timestamp(window["test_end"])

        train_scores = []
        for name in deployable_names:
            row = metric_row(
                name,
                window_id,
                "train",
                train_start,
                train_end,
                close,
                weights_by_strategy[name],
            )
            train_scores.append(row)

        train_df = pd.DataFrame(train_scores).sort_values("balanced_score", ascending=False)
        selected = str(train_df.iloc[0]["strategy"])
        selected_train = train_df.iloc[0].to_dict()

        selected_test = metric_row(
            selected,
            window_id,
            "test",
            test_start,
            test_end,
            close,
            weights_by_strategy[selected],
        )

        qqq_50_test = metric_row(
            "QQQ_50_200_cross",
            window_id,
            "test",
            test_start,
            test_end,
            close,
            weights_by_strategy["QQQ_50_200_cross"],
        )

        window_rows.append(
            {
                "window_id": window_id,
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "selected_strategy": selected,
                "selected_train_cagr_pct": selected_train["cagr_pct"],
                "selected_train_sharpe_0rf": selected_train["sharpe_0rf"],
                "selected_train_max_drawdown_pct": selected_train["max_drawdown_pct"],
                "selected_train_trade_count": selected_train["trade_count"],
                "selected_train_score": selected_train["balanced_score"],
                "selected_test_cagr_pct": selected_test["cagr_pct"],
                "selected_test_sharpe_0rf": selected_test["sharpe_0rf"],
                "selected_test_max_drawdown_pct": selected_test["max_drawdown_pct"],
                "selected_test_trade_count": selected_test["trade_count"],
                "selected_test_total_return_pct": selected_test["total_return_pct"],
                "qqq_50_200_test_total_return_pct": qqq_50_test["total_return_pct"],
                "qqq_50_200_test_cagr_pct": qqq_50_test["cagr_pct"],
                "selected_outperformed_qqq_50_200": bool(
                    float(selected_test["total_return_pct"]) > float(qqq_50_test["total_return_pct"])
                ),
            }
        )

        selected_test["strategy"] = "walk_forward_selected"
        selected_test["selected_strategy"] = selected
        selected_test_rows.append(selected_test)

        for name in FIXED_TEST_CANDIDATES:
            row = metric_row(
                name,
                window_id,
                "test",
                test_start,
                test_end,
                close,
                weights_by_strategy[name],
            )
            row["selected_strategy"] = np.nan
            fixed_rows.append(row)

    windows_df = pd.DataFrame(window_rows)
    fixed_df = pd.DataFrame(fixed_rows)
    selected_df = pd.DataFrame(selected_test_rows)

    all_test_rows = pd.concat([fixed_df, selected_df], ignore_index=True)
    summary_df = aggregate_test_rows(all_test_rows)

    windows_df.to_csv(WINDOWS_PATH, index=False)
    fixed_df.to_csv(FIXED_PATH, index=False)
    summary_df.to_csv(SUMMARY_PATH, index=False)
    REPORT_PATH.write_text(
        build_report(windows_df, fixed_df, summary_df, active_strategy),
        encoding="utf-8",
    )

    print("Walk-forward MA validation complete.")
    print(f"Windows written: {WINDOWS_PATH}")
    print(f"Fixed candidates written: {FIXED_PATH}")
    print(f"Summary written: {SUMMARY_PATH}")
    print(f"Report written: {REPORT_PATH}")
    print("")
    print(summary_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
