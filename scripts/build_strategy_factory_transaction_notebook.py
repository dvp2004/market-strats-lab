from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_strats.analysis.strategy_factory_transactions import (  # noqa: E402
    save_strategy_factory_transaction_reports,
)


NOTEBOOK_PATH = ROOT / "notebooks" / "phase17c_strategy_factory_transaction_visuals.ipynb"
WATCHLIST_DISPLAY_COLUMNS = [
    "candidate_id",
    "watchlist_role",
    "low_friction_cagr_pct",
    "realistic_stress_cagr_pct",
    "max_drawdown_pct",
    "rolling_3y_candidate_beats_spy_pct",
    "worst_3y_active_cagr",
    "median_3y_active_cagr",
    "latest_3y_active_cagr",
    "btc_cap_dependency_flag",
    "promotion_allowed",
    "paper_watchlist_only",
]
ROLLING_COLUMN_ALIASES = {
    "rolling_3y_candidate_beats_spy_pct": [
        "rolling_3y_candidate_beats_spy_pct",
        "rolling_3y_beat_spy_pct",
        "rolling_3y_active_cagr_beats_spy_pct",
    ],
    "worst_3y_active_cagr": ["worst_3y_active_cagr"],
    "median_3y_active_cagr": ["median_3y_active_cagr"],
    "latest_3y_active_cagr": ["latest_3y_active_cagr"],
}


def _candidate_id_column(frame: pd.DataFrame) -> str | None:
    if "candidate_id" in frame.columns:
        return "candidate_id"
    if "strategy" in frame.columns:
        return "strategy"
    if "strategy_id" in frame.columns:
        return "strategy_id"
    return None


def _canonical_rolling_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["candidate_id", *ROLLING_COLUMN_ALIASES])
    id_col = _candidate_id_column(frame)
    if id_col is None:
        return pd.DataFrame(columns=["candidate_id", *ROLLING_COLUMN_ALIASES])

    out = pd.DataFrame({"candidate_id": frame[id_col].astype(str)})
    for canonical, aliases in ROLLING_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in frame.columns:
                out[canonical] = frame[alias]
                break
    return out.drop_duplicates("candidate_id", keep="last")


def normalise_watchlist_for_display(
    watchlist: pd.DataFrame,
    watchlist_rolling: pd.DataFrame | None = None,
    phase17b_rolling: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    if watchlist.empty:
        out = pd.DataFrame(columns=WATCHLIST_DISPLAY_COLUMNS)
        return out, WATCHLIST_DISPLAY_COLUMNS.copy()

    id_col = _candidate_id_column(watchlist)
    if id_col is None:
        out = watchlist.copy()
        out["candidate_id"] = pd.NA
    else:
        out = watchlist.rename(columns={id_col: "candidate_id"}).copy()
        out["candidate_id"] = out["candidate_id"].astype(str)

    own_rolling = _canonical_rolling_frame(out)
    sources = [
        own_rolling,
        _canonical_rolling_frame(
            watchlist_rolling if watchlist_rolling is not None else pd.DataFrame()
        ),
        _canonical_rolling_frame(
            phase17b_rolling if phase17b_rolling is not None else pd.DataFrame()
        ),
    ]

    for canonical in ROLLING_COLUMN_ALIASES:
        if canonical not in out.columns:
            out[canonical] = pd.NA

    for source in sources:
        if source.empty:
            continue
        out = out.merge(source, on="candidate_id", how="left", suffixes=("", "__source"))
        for canonical in ROLLING_COLUMN_ALIASES:
            source_col = f"{canonical}__source"
            if source_col in out.columns:
                out[canonical] = out[canonical].combine_first(out[source_col])
                out = out.drop(columns=[source_col])

    missing = []
    for column in WATCHLIST_DISPLAY_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
            missing.append(column)
        elif out[column].isna().all():
            missing.append(column)
    return out, missing


def _markdown(source: str) -> dict[str, Any]:
    text = dedent(source).strip()
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in text.splitlines()],
    }


def _code(source: str) -> dict[str, Any]:
    text = dedent(source).strip()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in text.splitlines()],
    }


def _notebook() -> dict[str, Any]:
    return {
        "cells": [
            _markdown(
                """
                # Phase 17C Strategy Factory Transaction Visuals

                This notebook is a static research and paper-watchlist report for Strategy Factory
                transaction behaviour. It explains inferred target-weight changes for SPY, QQQ,
                BTC-USD, GLD, TLT, and cash.

                This is not live trading. It is not broker/API integration. It does not use real
                money, does not optimise parameters, and does not promote any candidate.
                """
            ),
            _markdown(
                """
                ## Load Data

                The notebook reads existing Phase 17A/17B/17C reports plus the transaction
                artefacts generated under `reports/strategy_factory/transactions/`.
                """
            ),
            _code(
                """
                from pathlib import Path
                import sys

                import matplotlib
                matplotlib.use("Agg")

                import matplotlib.pyplot as plt
                import pandas as pd
                from IPython.display import Image, display

                cwd = Path.cwd().resolve()
                root = cwd if (cwd / "reports").exists() else cwd.parent
                if str(root) not in sys.path:
                    sys.path.insert(0, str(root))

                from scripts.build_strategy_factory_transaction_notebook import (  # noqa: E402
                    WATCHLIST_DISPLAY_COLUMNS,
                    normalise_watchlist_for_display,
                )
                ROLLING_3Y_BEAT_RATE_FIELD = "rolling_3y_candidate_beats_spy_pct"

                strategy_dir = root / "reports" / "strategy_factory"
                transaction_dir = strategy_dir / "transactions"
                chart_dir = transaction_dir / "charts"

                files = {
                    "phase17a_metrics": strategy_dir / "phase17a_strategy_factory_metrics.csv",
                    "phase17b_friction": strategy_dir / "phase17b_friction_metrics.csv",
                    "phase17b_btc_gap": strategy_dir / "phase17b_btc_weekend_gap_diagnostic.csv",
                    "phase17b_rolling": strategy_dir / "phase17b_rolling_relative_summary.csv",
                    "phase17c_watchlist": strategy_dir / "watchlist" / "phase17c_watchlist_candidates.csv",
                    "watchlist_rolling_snapshot": (
                        strategy_dir / "watchlist" / "dashboard" / "watchlist_rolling_snapshot.csv"
                    ),
                    "transaction_ledger": transaction_dir / "strategy_transaction_ledger.csv",
                    "drift_ledger": transaction_dir / "strategy_drift_rebalance_ledger.csv",
                    "drift_summary": transaction_dir / "strategy_drift_rebalance_summary.csv",
                    "trade_matrix": transaction_dir / "strategy_rebalance_trade_matrix.csv",
                    "rebalance_summary": transaction_dir / "strategy_rebalance_summary.csv",
                    "turnover_timeline": transaction_dir / "strategy_turnover_timeline.csv",
                    "allocation_long": transaction_dir / "strategy_asset_allocation_long.csv",
                    "latest_allocations": transaction_dir / "strategy_latest_allocations.csv",
                }
                pd.DataFrame(
                    [{"name": name, "path": str(path), "exists": path.exists()} for name, path in files.items()]
                )
                """
            ),
            _code(
                """
                metrics = pd.read_csv(files["phase17a_metrics"])
                friction = pd.read_csv(files["phase17b_friction"])
                btc_gap = pd.read_csv(files["phase17b_btc_gap"])
                watchlist = pd.read_csv(files["phase17c_watchlist"])
                watchlist_rolling = (
                    pd.read_csv(files["watchlist_rolling_snapshot"])
                    if files["watchlist_rolling_snapshot"].exists()
                    else pd.DataFrame()
                )
                phase17b_rolling = (
                    pd.read_csv(files["phase17b_rolling"])
                    if files["phase17b_rolling"].exists()
                    else pd.DataFrame()
                )
                ledger = pd.read_csv(files["transaction_ledger"])
                drift_ledger = pd.read_csv(files["drift_ledger"])
                drift_summary = pd.read_csv(files["drift_summary"])
                trade_matrix = pd.read_csv(files["trade_matrix"])
                summary = pd.read_csv(files["rebalance_summary"])
                turnover = pd.read_csv(files["turnover_timeline"])
                allocation = pd.read_csv(files["allocation_long"])
                latest_allocations = pd.read_csv(files["latest_allocations"])

                watchlist_ids = watchlist["candidate_id"].astype(str).tolist()
                watchlist_enriched, missing_watchlist_display_cols = normalise_watchlist_for_display(
                    watchlist,
                    watchlist_rolling=watchlist_rolling,
                    phase17b_rolling=phase17b_rolling,
                )
                all_strategy_ids = sorted(allocation["strategy_id"].astype(str).unique())
                watchlist_ids
                """
            ),
            _markdown(
                """
                ## Strategy Explanation

                - `sf_spy_buy_hold`: holds 100% SPY.
                - `sf_spy_qqq_60_40_monthly_rebalanced`: targets 60% SPY and 40% QQQ with monthly rebalancing.
                - `sf_spy_qqq_tactical_momentum`: chooses SPY or QQQ using a fixed trailing momentum rule, with cash when both are negative.
                - `sf_spy_qqq_gld_tlt_risk_off_rotation`: rotates between SPY/QQQ risk-on exposure and GLD/TLT/cash risk-off exposure.
                - `sf_spy_core_phase6_overlay_satellite_qqq`: links a SPY overlay-style core to a capped QQQ satellite when risk-on.
                - `sf_spy_qqq_btc_capped_offensive`: holds an SPY/QQQ base with a capped BTC sleeve when BTC momentum and SPY risk-on conditions are positive.
                """
            ),
            _markdown(
                """
                ## Performance Overview

                These tables and charts describe research performance only. They are not
                promotion decisions and do not alter the current operational paper baseline.
                """
            ),
            _code(
                """
                overview_cols = [
                    "strategy",
                    "end_value",
                    "total_return_pct",
                    "cagr_pct",
                    "volatility_pct",
                    "max_drawdown_pct",
                    "calmar",
                ]
                metrics[overview_cols].sort_values("end_value", ascending=False)
                """
            ),
            _code(
                """
                plot_frame = metrics.set_index("strategy")[["end_value", "cagr_pct", "max_drawdown_pct", "calmar"]]
                fig, axes = plt.subplots(2, 2, figsize=(13, 8))
                for ax, column in zip(axes.ravel(), plot_frame.columns):
                    plot_frame[column].sort_values().plot(kind="barh", ax=ax)
                    ax.set_title(column)
                    ax.grid(True, axis="x", alpha=0.25)
                fig.tight_layout()
                plt.show()
                """
            ),
            _markdown(
                """
                ## Allocation Timelines

                The Strategy Factory transaction ledger is inferred from target allocation changes.
                These are not broker fills.
                """
            ),
            _code(
                """
                display(Image(filename=str(chart_dir / "allocation_timeline_by_strategy.png")))
                display(Image(filename=str(chart_dir / "latest_allocation_snapshot.png")))
                """
            ),
            _code(
                """
                allocation.loc[
                    allocation["strategy_id"].isin(watchlist_ids),
                    ["date", "strategy_id", "asset", "weight"],
                ].tail(30)
                """
            ),
            _markdown(
                """
                ## Target-weight changes vs actual rebalance trades

                The target-weight ledger shows signal or allocation changes. For example, the BTC
                capped strategy has explicit BTC entries and exits when the target BTC sleeve moves
                between 0% and 10%.

                The drift-rebalance ledger estimates implementation trades. It lets current weights
                drift with asset returns between rebalance dates, then calculates the trades needed to
                restore the strategy target. This makes constant-target strategies like SPY/QQQ 60/40
                visible: even if the target stays 60/40, market returns push the actual portfolio away
                from 60/40 and monthly rebalancing creates buy/sell trades.
                """
            ),
            _code(
                """
                target_change_rows = ledger.groupby("strategy_id").size().rename("target_change_rows")
                drift_rows = drift_ledger.groupby("strategy_id").size().rename("drift_rebalance_rows")
                pd.concat([target_change_rows, drift_rows], axis=1).fillna(0).astype(int)
                """
            ),
            _markdown(
                """
                ## Transaction Ledger

                The ledger shows inferred BUY_ENTRY, BUY_INCREASE, SELL_REDUCE, SELL_EXIT, and
                CASH_ALLOCATION_CHANGE rows. Notional changes use a $10,000 interpretation baseline.
                """
            ),
            _code(
                """
                ledger.head(50)
                """
            ),
            _code(
                """
                ledger.tail(50)
                """
            ),
            _code(
                """
                by_strategy = ledger.groupby("strategy_id").size().rename("transaction_rows")
                by_asset = ledger.groupby("asset").size().rename("transaction_rows")
                buy_sell = ledger.groupby(["strategy_id", "transaction_direction"]).size().unstack(fill_value=0)
                by_strategy, by_asset, buy_sell
                """
            ),
            _code(
                """
                display(Image(filename=str(chart_dir / "transaction_count_by_asset.png")))
                """
            ),
            _markdown(
                """
                ## Drift-based Rebalance Ledger

                These rows estimate the trades needed to restore target weights after asset returns
                cause holdings to drift. They are implementation estimates, not fills.
                """
            ),
            _code(
                """
                drift_ledger.head(50)
                """
            ),
            _code(
                """
                drift_ledger.tail(50)
                """
            ),
            _code(
                """
                drift_summary.sort_values("rebalance_trade_rows", ascending=False)
                """
            ),
            _code(
                """
                display(Image(filename=str(chart_dir / "drift_rebalance_trades_by_strategy.png")))
                display(Image(filename=str(chart_dir / "drift_rebalance_trades_by_asset.png")))
                display(Image(filename=str(chart_dir / "drift_rebalance_notional_by_asset.png")))
                """
            ),
            _markdown(
                """
                ## SPY/QQQ 60/40 Rebalance Inspection

                This section shows the monthly implementation trades for the constant-target 60/40
                candidate. Positive notional buys an asset back to target; negative notional sells an
                overweight asset back to target.
                """
            ),
            _code(
                """
                strategy_6040 = "sf_spy_qqq_60_40_monthly_rebalanced"
                trades_6040 = drift_ledger[
                    (drift_ledger["strategy_id"] == strategy_6040)
                    & (drift_ledger["asset"].isin(["SPY", "QQQ"]))
                ].copy()
                display(Image(filename=str(chart_dir / "spy_qqq_60_40_rebalance_timeline.png")))
                trades_6040.tail(30)
                """
            ),
            _markdown(
                """
                ## BTC Capped Rebalance Inspection

                BTC entries and exits appear in the target-change ledger. Regular rebalance trades while
                BTC is active appear in the drift ledger.
                """
            ),
            _code(
                """
                btc_target_changes = ledger[
                    (ledger["strategy_id"] == "sf_spy_qqq_btc_capped_offensive")
                    & (ledger["asset"] == "BTC-USD")
                ].copy()
                btc_drift_trades = drift_ledger[
                    (drift_ledger["strategy_id"] == "sf_spy_qqq_btc_capped_offensive")
                    & (drift_ledger["asset"] == "BTC-USD")
                ].copy()
                btc_target_changes.tail(20), btc_drift_trades.tail(20)
                """
            ),
            _markdown(
                """
                ## Trade Burden Comparison

                This compares which strategies and assets create the most estimated implementation
                activity.
                """
            ),
            _code(
                """
                trade_matrix.sort_values("total_abs_trade_notional_per_10000", ascending=False).head(25)
                """
            ),
            _markdown(
                """
                ## Turnover Visualisation

                Turnover is the sum of absolute target-weight changes by strategy and rebalance date.
                Large spikes identify periods where the candidate changed exposure materially.
                """
            ),
            _code(
                """
                display(Image(filename=str(chart_dir / "turnover_timeline_by_strategy.png")))
                high_turnover = turnover.sort_values("turnover", ascending=False).head(25)
                high_turnover
                """
            ),
            _markdown(
                """
                ## BTC-Specific Inspection

                BTC strategy returns are evaluated on ETF-common trading dates in the Strategy Factory
                frame. BTC weekend observations and weekend gap risk are diagnostic context and are not
                directly represented in ETF-common-date strategy returns.
                """
            ),
            _code(
                """
                display(Image(filename=str(chart_dir / "btc_weight_timeline.png")))
                btc_gap
                """
            ),
            _markdown(
                """
                ## Watchlist Interpretation

                - Clean growth watchlist: SPY/QQQ 60/40.
                - Baseline-linked growth watchlist: Phase6-style SPY overlay plus QQQ satellite.
                - High-growth/high-caveat watchlist: SPY/QQQ/BTC capped offensive.
                """
            ),
            _code(
                """
                if missing_watchlist_display_cols:
                    print(
                        "Optional watchlist display columns unavailable; showing NA placeholders:",
                        missing_watchlist_display_cols,
                    )
                    print("Available Phase 17C watchlist columns:", list(watchlist.columns))

                print("Canonical rolling 3Y beat-rate field:", ROLLING_3Y_BEAT_RATE_FIELD)
                watchlist_enriched[WATCHLIST_DISPLAY_COLUMNS]
                """
            ),
            _markdown(
                """
                ## Current Paper Relevance

                Phase 16 paper preview currently represents only the Phase6 SPY overlay baseline.
                The 60/40 and BTC Strategy Factory candidates are research watchlist candidates and
                are not represented in active paper order preview files.
                """
            ),
            _markdown(
                """
                ## Conclusion

                Target-weight changes are signal/allocation changes. Drift-based rebalance trades are
                estimated implementation trades. Neither are broker fills.

                No candidate is promoted. There is no live trading, no real money, and no broker/API
                execution. The next operational step is watchlist paper-preview integration or recurring
                signal hardening, not live deployment.
                """
            ),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_notebook(path: Path = NOTEBOOK_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_notebook(), indent=2), encoding="utf-8")
    return path


def main() -> None:
    save_strategy_factory_transaction_reports()
    path = build_notebook()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
