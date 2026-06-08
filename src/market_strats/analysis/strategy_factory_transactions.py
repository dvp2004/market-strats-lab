from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_NOTIONAL = 10000.0
DEFAULT_OUTPUT_DIR = Path("reports/strategy_factory/transactions")
DEFAULT_CHART_DIR = DEFAULT_OUTPUT_DIR / "charts"
DEFAULT_ALLOCATION_FILE = Path("reports/strategy_factory/allocation_timeline.csv")
DEFAULT_WATCHLIST_FILE = Path("reports/strategy_factory/watchlist/phase17c_watchlist_candidates.csv")
DEFAULT_PRICE_DATA_DIR = Path("data/fresh/processed")
FACTORY_ASSETS = ["SPY", "QQQ", "GLD", "TLT", "BTC-USD", "CASH"]


def _normalise_asset(asset: Any) -> str:
    text = str(asset).strip().upper()
    if text in {"BTC_USD", "BTCUSD"}:
        return "BTC-USD"
    return text


def _direction(
    *,
    asset: str,
    previous_weight: float,
    target_weight: float,
) -> str:
    if asset == "CASH":
        return "CASH_ALLOCATION_CHANGE"
    if previous_weight <= 0.0 and target_weight > 0.0:
        return "BUY_ENTRY"
    if target_weight > previous_weight:
        return "BUY_INCREASE"
    if target_weight <= 0.0 and previous_weight > 0.0:
        return "SELL_EXIT"
    return "SELL_REDUCE"


def _transaction_type(asset: str) -> str:
    return "cash_allocation_change" if asset == "CASH" else "target_weight_change"


def _strategy_col(frame: pd.DataFrame) -> str:
    if "strategy" in frame.columns:
        return "strategy"
    if "strategy_id" in frame.columns:
        return "strategy_id"
    raise ValueError("Allocation timeline missing strategy/strategy_id column")


def _normalise_allocation(allocation: pd.DataFrame) -> pd.DataFrame:
    strategy_col = _strategy_col(allocation)
    required = {"date", strategy_col, "asset", "weight"}
    missing = required - set(allocation.columns)
    if missing:
        raise ValueError(f"Allocation timeline missing columns: {sorted(missing)}")

    work = allocation[["date", strategy_col, "asset", "weight"]].copy()
    work = work.rename(columns={strategy_col: "strategy"})
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["strategy"] = work["strategy"].astype(str)
    work["asset"] = work["asset"].map(_normalise_asset)
    work["weight"] = pd.to_numeric(work["weight"], errors="coerce").fillna(0.0)
    return work.dropna(subset=["date"]).sort_values(["strategy", "date", "asset"])


def create_transaction_ledger(
    allocation: pd.DataFrame,
    *,
    notional: float = DEFAULT_NOTIONAL,
    strategies: list[str] | None = None,
    min_abs_change: float = 1e-10,
) -> pd.DataFrame:
    work = _normalise_allocation(allocation)

    selected = strategies or sorted(work["strategy"].unique().tolist())
    rows: list[dict[str, Any]] = []

    for strategy in selected:
        part = work.loc[work["strategy"] == strategy]
        if part.empty:
            rows.append(_placeholder_row(strategy, "allocation_data_missing_for_strategy"))
            continue

        wide = (
            part.pivot_table(
                index="date",
                columns="asset",
                values="weight",
                aggfunc="last",
                fill_value=0.0,
            )
            .sort_index()
            .astype(float)
        )
        previous = pd.Series(0.0, index=wide.columns)
        for date, weights in wide.iterrows():
            changes = weights - previous
            for asset, change in changes.items():
                change = float(change)
                if abs(change) <= min_abs_change:
                    continue
                previous_weight = float(previous[asset])
                target_weight = float(weights[asset])
                direction = _direction(
                    asset=asset,
                    previous_weight=previous_weight,
                    target_weight=target_weight,
                )
                rows.append(
                    {
                        "strategy_id": strategy,
                        "rebalance_date": pd.Timestamp(date).date().isoformat(),
                        "asset": asset,
                        "previous_weight": round(previous_weight, 8),
                        "target_weight": round(target_weight, 8),
                        "weight_change": round(change, 8),
                        "transaction_direction": direction,
                        "transaction_type": _transaction_type(asset),
                        "estimated_notional_change_per_10000": round(change * float(notional), 2),
                        "turnover_contribution": round(abs(change), 8),
                        "is_buy": bool(asset != "CASH" and change > 0.0),
                        "is_sell": bool(asset != "CASH" and change < 0.0),
                        "is_rebalance": True,
                        "is_entry": bool(asset != "CASH" and previous_weight <= 0.0 and target_weight > 0.0),
                        "is_exit": bool(asset != "CASH" and target_weight <= 0.0 and previous_weight > 0.0),
                        "transaction_data_available": True,
                        "notes": (
                            "Inferred from target allocation weight change; not a broker fill."
                        ),
                    }
                )
            previous = weights.copy()

    return pd.DataFrame(rows)


def _placeholder_row(strategy: str, reason: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy,
        "rebalance_date": "",
        "asset": "",
        "previous_weight": pd.NA,
        "target_weight": pd.NA,
        "weight_change": pd.NA,
        "transaction_direction": "TRANSACTION_DATA_UNAVAILABLE",
        "transaction_type": "placeholder",
        "estimated_notional_change_per_10000": pd.NA,
        "turnover_contribution": pd.NA,
        "is_buy": False,
        "is_sell": False,
        "is_rebalance": False,
        "is_entry": False,
        "is_exit": False,
        "transaction_data_available": False,
        "notes": reason,
    }


def _drift_placeholder_row(strategy: str, reason: str) -> dict[str, Any]:
    return {
        "strategy_id": strategy,
        "rebalance_date": "",
        "asset": "",
        "pre_rebalance_weight": pd.NA,
        "target_weight": pd.NA,
        "weight_change_required": pd.NA,
        "transaction_direction": "DRIFT_REBALANCE_UNAVAILABLE",
        "estimated_trade_notional_per_10000": pd.NA,
        "is_buy": False,
        "is_sell": False,
        "is_drift_rebalance": False,
        "drift_rebalance_available": False,
        "blocking_reason": reason,
        "notes": reason,
    }


def load_asset_returns_from_processed(
    *,
    price_data_dir: str | Path = DEFAULT_PRICE_DATA_DIR,
    assets: list[str] | None = None,
) -> pd.DataFrame:
    selected = [_normalise_asset(asset) for asset in (assets or FACTORY_ASSETS)]
    data_dir = Path(price_data_dir)
    returns: pd.DataFrame | None = None

    for asset in selected:
        if asset == "CASH":
            continue
        path = data_dir / f"{asset}.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        required = {"date", "adj_close"}
        missing = required - set(frame.columns)
        if missing:
            continue
        part = frame[["date", "adj_close"]].copy()
        part["date"] = pd.to_datetime(part["date"], errors="coerce")
        part = part.dropna(subset=["date"]).sort_values("date")
        part = part.drop_duplicates("date", keep="last")
        part[asset] = pd.to_numeric(part["adj_close"], errors="coerce").pct_change().fillna(0.0)
        part = part[["date", asset]]
        returns = part if returns is None else returns.merge(part, on="date", how="outer")

    if returns is None:
        return pd.DataFrame(columns=["date", *selected])

    returns = returns.sort_values("date").reset_index(drop=True)
    if "CASH" in selected:
        returns["CASH"] = 0.0
    return returns


def _normalise_asset_returns(asset_returns: pd.DataFrame) -> pd.DataFrame:
    if asset_returns.empty or "date" not in asset_returns.columns:
        return pd.DataFrame()
    returns = asset_returns.copy()
    returns["date"] = pd.to_datetime(returns["date"], errors="coerce")
    returns = returns.dropna(subset=["date"]).sort_values("date")
    rename = {
        column: _normalise_asset(column)
        for column in returns.columns
        if column != "date"
    }
    returns = returns.rename(columns=rename)
    for column in returns.columns:
        if column != "date":
            returns[column] = pd.to_numeric(returns[column], errors="coerce")
    return returns.set_index("date").sort_index()


def _target_weight_wide(part: pd.DataFrame) -> pd.DataFrame:
    wide = (
        part.pivot_table(
            index="date",
            columns="asset",
            values="weight",
            aggfunc="last",
            fill_value=0.0,
        )
        .sort_index()
        .astype(float)
    )
    for asset in FACTORY_ASSETS:
        if asset not in wide.columns:
            wide[asset] = 0.0
    return wide[FACTORY_ASSETS]


def _monthly_rebalance_dates(dates: pd.Index) -> set[pd.Timestamp]:
    if len(dates) <= 1:
        return set()
    date_series = pd.Series(pd.to_datetime(dates))
    periods = date_series.dt.to_period("M")
    month_start_mask = periods.ne(periods.shift(1)).fillna(True)
    month_starts = date_series.loc[month_start_mask].iloc[1:]
    return {pd.Timestamp(date) for date in month_starts}


def _drift_direction(asset: str, weight_change_required: float) -> str:
    if asset == "CASH":
        return "CASH_REBALANCE_CHANGE"
    if weight_change_required > 0.0:
        return "BUY_TO_TARGET"
    return "SELL_TO_TARGET"


def _returns_available_for_targets(
    *,
    target_weights: pd.DataFrame,
    returns: pd.DataFrame,
) -> tuple[bool, str]:
    missing_assets = [
        asset
        for asset in FACTORY_ASSETS
        if asset not in returns.columns and target_weights[asset].abs().max() > 1e-10
    ]
    if missing_assets:
        return False, f"missing_asset_returns:{','.join(missing_assets)}"

    positive_assets = [
        asset for asset in FACTORY_ASSETS if asset != "CASH" and target_weights[asset].abs().max() > 1e-10
    ]
    if not positive_assets:
        return True, ""
    aligned = returns.reindex(target_weights.index)
    missing_dates = aligned[positive_assets].isna().any(axis=1)
    if bool(missing_dates.any()):
        first_missing = target_weights.index[missing_dates][0].date().isoformat()
        return False, f"missing_return_date:{first_missing}"
    return True, ""


def create_drift_rebalance_ledger(
    allocation: pd.DataFrame,
    asset_returns: pd.DataFrame,
    *,
    notional: float = DEFAULT_NOTIONAL,
    strategies: list[str] | None = None,
    tolerance: float = 1e-6,
) -> pd.DataFrame:
    work = _normalise_allocation(allocation)
    returns = _normalise_asset_returns(asset_returns)
    selected = strategies or sorted(work["strategy"].unique().tolist())
    rows: list[dict[str, Any]] = []

    for strategy in selected:
        part = work.loc[work["strategy"] == strategy]
        if part.empty:
            rows.append(_drift_placeholder_row(strategy, "allocation_data_missing_for_strategy"))
            continue
        targets = _target_weight_wide(part)
        if len(targets) <= 1:
            continue

        available, reason = _returns_available_for_targets(
            target_weights=targets,
            returns=returns,
        )
        if not available:
            rows.append(_drift_placeholder_row(strategy, reason))
            continue

        aligned_returns = returns.reindex(targets.index).fillna(0.0)
        for asset in FACTORY_ASSETS:
            if asset not in aligned_returns.columns:
                aligned_returns[asset] = 0.0
        aligned_returns = aligned_returns[FACTORY_ASSETS]

        actual_weights = targets.iloc[0].astype(float)
        rebalance_dates = _monthly_rebalance_dates(targets.index)

        for idx, date in enumerate(targets.index):
            if idx == 0:
                continue
            daily_returns = aligned_returns.loc[date].astype(float)
            drifted = actual_weights * (1.0 + daily_returns)
            total_weight = float(drifted.sum())
            pre_rebalance = drifted / total_weight if total_weight > 0.0 else drifted
            target = targets.loc[date].astype(float)

            if pd.Timestamp(date) in rebalance_dates:
                changes = target - pre_rebalance
                for asset, change in changes.items():
                    change = float(change)
                    if abs(change) <= tolerance:
                        continue
                    direction = _drift_direction(asset, change)
                    rows.append(
                        {
                            "strategy_id": strategy,
                            "rebalance_date": pd.Timestamp(date).date().isoformat(),
                            "asset": asset,
                            "pre_rebalance_weight": round(float(pre_rebalance[asset]), 8),
                            "target_weight": round(float(target[asset]), 8),
                            "weight_change_required": round(change, 8),
                            "transaction_direction": direction,
                            "estimated_trade_notional_per_10000": round(
                                change * float(notional),
                                2,
                            ),
                            "is_buy": bool(asset != "CASH" and change > 0.0),
                            "is_sell": bool(asset != "CASH" and change < 0.0),
                            "is_drift_rebalance": True,
                            "drift_rebalance_available": True,
                            "blocking_reason": "",
                            "notes": (
                                "Estimated drift rebalance from asset returns and target weights; "
                                "not a broker fill."
                            ),
                        }
                    )
                actual_weights = target
            else:
                actual_weights = pre_rebalance

    return pd.DataFrame(rows)


def create_rebalance_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    rows = []
    valid = ledger[ledger["transaction_data_available"].astype(bool)].copy()
    for strategy, group in valid.groupby("strategy_id"):
        rows.append(
            {
                "strategy_id": strategy,
                "transaction_rows": int(len(group)),
                "rebalance_dates": int(group["rebalance_date"].nunique()),
                "first_rebalance_date": group["rebalance_date"].min(),
                "latest_rebalance_date": group["rebalance_date"].max(),
                "buy_rows": int(group["is_buy"].astype(bool).sum()),
                "sell_rows": int(group["is_sell"].astype(bool).sum()),
                "entry_rows": int(group["is_entry"].astype(bool).sum()),
                "exit_rows": int(group["is_exit"].astype(bool).sum()),
                "cash_change_rows": int((group["asset"] == "CASH").sum()),
                "total_turnover_contribution": round(
                    float(group["turnover_contribution"].astype(float).sum()),
                    4,
                ),
            }
        )
    return pd.DataFrame(rows)


def create_turnover_timeline(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty or "transaction_data_available" not in ledger.columns:
        return pd.DataFrame()
    valid = ledger[ledger["transaction_data_available"].astype(bool)].copy()
    if valid.empty:
        return pd.DataFrame()
    return (
        valid.groupby(["strategy_id", "rebalance_date"], as_index=False)
        .agg(
            turnover=("turnover_contribution", "sum"),
            transaction_rows=("asset", "count"),
            buy_rows=("is_buy", "sum"),
            sell_rows=("is_sell", "sum"),
        )
        .sort_values(["strategy_id", "rebalance_date"])
    )


def create_drift_rebalance_summary(
    drift_ledger: pd.DataFrame,
    *,
    strategies: list[str] | None = None,
) -> pd.DataFrame:
    selected = strategies or sorted(drift_ledger.get("strategy_id", pd.Series(dtype=str)).unique())
    rows: list[dict[str, Any]] = []
    valid = pd.DataFrame()
    if not drift_ledger.empty and "drift_rebalance_available" in drift_ledger.columns:
        valid = drift_ledger[drift_ledger["drift_rebalance_available"].astype(bool)].copy()

    for strategy in selected:
        group = valid.loc[valid["strategy_id"] == strategy] if not valid.empty else pd.DataFrame()
        if group.empty:
            rows.append(
                {
                    "strategy_id": strategy,
                    "rebalance_trade_rows": 0,
                    "rebalance_dates": 0,
                    "first_rebalance_date": "",
                    "latest_rebalance_date": "",
                    "buy_rows": 0,
                    "sell_rows": 0,
                    "cash_change_rows": 0,
                    "total_abs_trade_notional_per_10000": 0.0,
                    "total_turnover_required": 0.0,
                    "drift_rebalance_available": True,
                    "blocking_reason": "",
                }
            )
            continue

        notional_abs = group["estimated_trade_notional_per_10000"].astype(float).abs()
        required_abs = group["weight_change_required"].astype(float).abs()
        rows.append(
            {
                "strategy_id": strategy,
                "rebalance_trade_rows": int(len(group)),
                "rebalance_dates": int(group["rebalance_date"].nunique()),
                "first_rebalance_date": group["rebalance_date"].min(),
                "latest_rebalance_date": group["rebalance_date"].max(),
                "buy_rows": int(group["is_buy"].astype(bool).sum()),
                "sell_rows": int(group["is_sell"].astype(bool).sum()),
                "cash_change_rows": int((group["asset"] == "CASH").sum()),
                "total_abs_trade_notional_per_10000": round(float(notional_abs.sum()), 2),
                "total_turnover_required": round(float(required_abs.sum()), 6),
                "drift_rebalance_available": True,
                "blocking_reason": "",
            }
        )

    placeholders = pd.DataFrame()
    if not drift_ledger.empty and "drift_rebalance_available" in drift_ledger.columns:
        placeholders = drift_ledger[~drift_ledger["drift_rebalance_available"].astype(bool)]
    if not placeholders.empty:
        for strategy, group in placeholders.groupby("strategy_id"):
            mask = [row["strategy_id"] == strategy for row in rows]
            if any(mask):
                idx = mask.index(True)
                rows[idx]["drift_rebalance_available"] = False
                rows[idx]["blocking_reason"] = ";".join(
                    sorted(set(group["blocking_reason"].astype(str)))
                )

    return pd.DataFrame(rows)


def create_rebalance_trade_matrix(drift_ledger: pd.DataFrame) -> pd.DataFrame:
    if drift_ledger.empty or "drift_rebalance_available" not in drift_ledger.columns:
        return pd.DataFrame()
    valid = drift_ledger[drift_ledger["drift_rebalance_available"].astype(bool)].copy()
    if valid.empty:
        return pd.DataFrame()
    valid["abs_trade_notional_per_10000"] = (
        valid["estimated_trade_notional_per_10000"].astype(float).abs()
    )
    return (
        valid.groupby(["strategy_id", "asset"], as_index=False)
        .agg(
            rebalance_trade_rows=("asset", "count"),
            buy_rows=("is_buy", "sum"),
            sell_rows=("is_sell", "sum"),
            total_signed_trade_notional_per_10000=(
                "estimated_trade_notional_per_10000",
                "sum",
            ),
            total_abs_trade_notional_per_10000=("abs_trade_notional_per_10000", "sum"),
        )
        .assign(
            total_signed_trade_notional_per_10000=lambda frame: frame[
                "total_signed_trade_notional_per_10000"
            ].round(2),
            total_abs_trade_notional_per_10000=lambda frame: frame[
                "total_abs_trade_notional_per_10000"
            ].round(2),
        )
        .sort_values(["strategy_id", "asset"])
    )


def create_latest_allocations(allocation: pd.DataFrame) -> pd.DataFrame:
    work = allocation.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["asset"] = work["asset"].map(_normalise_asset)
    latest_dates = work.groupby("strategy")["date"].transform("max")
    latest = work.loc[work["date"] == latest_dates].copy()
    latest["date"] = latest["date"].dt.date.astype(str)
    return latest.rename(
        columns={"strategy": "strategy_id", "date": "allocation_date"}
    )[["strategy_id", "allocation_date", "asset", "weight"]]


def _asset_allocation_long(allocation: pd.DataFrame) -> pd.DataFrame:
    out = allocation.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str)
    out["asset"] = out["asset"].map(_normalise_asset)
    return out.rename(columns={"strategy": "strategy_id"})[
        ["date", "strategy_id", "asset", "weight"]
    ]


def _watchlist_strategies(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or "candidate_id" not in frame.columns:
        return None
    return frame["candidate_id"].astype(str).tolist()


def _plot_allocation_timeline(allocation: pd.DataFrame, strategies: list[str], path: Path) -> None:
    fig, axes = plt.subplots(len(strategies), 1, figsize=(11, max(4, 3 * len(strategies))), sharex=True)
    if len(strategies) == 1:
        axes = [axes]
    for ax, strategy in zip(axes, strategies, strict=False):
        part = allocation[allocation["strategy_id"] == strategy]
        for asset, group in part.groupby("asset"):
            if asset == "CASH" and group["weight"].max() <= 0:
                continue
            ax.plot(pd.to_datetime(group["date"]), group["weight"], label=asset)
        ax.set_title(strategy)
        ax.set_ylabel("Weight")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3)
    fig.suptitle("Strategy Factory Allocation Timeline")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_turnover_timeline(turnover: pd.DataFrame, strategies: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    for strategy in strategies:
        group = turnover[turnover["strategy_id"] == strategy]
        if group.empty:
            continue
        ax.plot(pd.to_datetime(group["rebalance_date"]), group["turnover"], label=strategy)
    ax.set_title("Strategy Factory Turnover Timeline")
    ax.set_ylabel("Turnover from target weight changes")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_transaction_count_by_asset(ledger: pd.DataFrame, path: Path) -> None:
    valid = ledger[ledger["transaction_data_available"].astype(bool)]
    counts = valid.groupby("asset").size().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    counts.plot(kind="bar", ax=ax)
    ax.set_title("Transaction Count by Asset")
    ax.set_ylabel("Inferred transaction rows")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_latest_allocations(latest: pd.DataFrame, strategies: list[str], path: Path) -> None:
    pivot = latest.pivot_table(index="strategy_id", columns="asset", values="weight", fill_value=0.0)
    pivot = pivot.reindex(strategies).dropna(how="all")
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_title("Latest Strategy Factory Allocation Snapshot")
    ax.set_ylabel("Target weight")
    ax.set_ylim(0, 1.05)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_btc_weight_timeline(allocation: pd.DataFrame, path: Path) -> None:
    btc = allocation[allocation["asset"] == "BTC-USD"].copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    if btc.empty:
        ax.text(0.5, 0.5, "No BTC allocation rows available", ha="center", va="center")
        ax.set_axis_off()
    else:
        for strategy, group in btc.groupby("strategy_id"):
            ax.plot(pd.to_datetime(group["date"]), group["weight"], label=strategy)
        ax.set_title("BTC Target Weight Timeline")
        ax.set_ylabel("BTC target weight")
        ax.set_ylim(-0.01, max(0.12, float(btc["weight"].max()) + 0.02))
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _valid_drift(drift_ledger: pd.DataFrame) -> pd.DataFrame:
    if drift_ledger.empty or "drift_rebalance_available" not in drift_ledger.columns:
        return pd.DataFrame()
    return drift_ledger[drift_ledger["drift_rebalance_available"].astype(bool)].copy()


def _plot_drift_rebalance_trades_by_strategy(
    drift_ledger: pd.DataFrame,
    path: Path,
) -> None:
    valid = _valid_drift(drift_ledger)
    fig, ax = plt.subplots(figsize=(10, 5))
    if valid.empty:
        ax.text(0.5, 0.5, "No drift rebalance rows available", ha="center", va="center")
        ax.set_axis_off()
    else:
        counts = valid.groupby("strategy_id").size().sort_values(ascending=True)
        counts.plot(kind="barh", ax=ax)
        ax.set_title("Drift Rebalance Trade Rows by Strategy")
        ax.set_xlabel("Estimated rebalance trade rows")
        ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_drift_rebalance_trades_by_asset(drift_ledger: pd.DataFrame, path: Path) -> None:
    valid = _valid_drift(drift_ledger)
    fig, ax = plt.subplots(figsize=(9, 5))
    if valid.empty:
        ax.text(0.5, 0.5, "No drift rebalance rows available", ha="center", va="center")
        ax.set_axis_off()
    else:
        counts = valid.groupby("asset").size().sort_values(ascending=False)
        counts.plot(kind="bar", ax=ax)
        ax.set_title("Drift Rebalance Trade Rows by Asset")
        ax.set_ylabel("Estimated rebalance trade rows")
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_drift_rebalance_notional_by_asset(
    drift_ledger: pd.DataFrame,
    path: Path,
) -> None:
    valid = _valid_drift(drift_ledger)
    fig, ax = plt.subplots(figsize=(9, 5))
    if valid.empty:
        ax.text(0.5, 0.5, "No drift rebalance rows available", ha="center", va="center")
        ax.set_axis_off()
    else:
        valid["abs_notional"] = valid["estimated_trade_notional_per_10000"].astype(float).abs()
        notionals = valid.groupby("asset")["abs_notional"].sum().sort_values(ascending=False)
        notionals.plot(kind="bar", ax=ax)
        ax.set_title("Drift Rebalance Absolute Notional by Asset")
        ax.set_ylabel("Absolute notional per $10,000 baseline")
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_spy_qqq_60_40_rebalance_timeline(
    drift_ledger: pd.DataFrame,
    path: Path,
) -> None:
    strategy = "sf_spy_qqq_60_40_monthly_rebalanced"
    valid = _valid_drift(drift_ledger)
    if valid.empty:
        part = pd.DataFrame()
    else:
        part = valid[
            (valid["strategy_id"] == strategy)
            & (valid["asset"].isin(["SPY", "QQQ"]))
        ].copy()
    fig, ax = plt.subplots(figsize=(11, 5))
    if part.empty:
        ax.text(0.5, 0.5, "No 60/40 drift rebalance rows available", ha="center", va="center")
        ax.set_axis_off()
    else:
        pivot = part.pivot_table(
            index="rebalance_date",
            columns="asset",
            values="estimated_trade_notional_per_10000",
            aggfunc="sum",
            fill_value=0.0,
        )
        pivot.index = pd.to_datetime(pivot.index)
        for asset in ["SPY", "QQQ"]:
            if asset in pivot.columns:
                ax.plot(pivot.index, pivot[asset], label=asset)
        ax.axhline(0.0, color="black", linewidth=0.8)
        ax.set_title("SPY/QQQ 60/40 Estimated Monthly Rebalance Trades")
        ax.set_ylabel("Signed trade notional per $10,000")
        ax.grid(True, alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_index(
    *,
    output_dir: Path,
    strategies: list[str],
    ledger: pd.DataFrame,
    summary: pd.DataFrame,
    drift_ledger: pd.DataFrame,
    drift_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Strategy Factory Transaction Visuals",
        "",
        "Research and paper-watchlist analysis only. Target-change rows are signal/allocation "
        "changes; drift-rebalance rows are estimated implementation trades. Neither are broker fills.",
        "",
        "- Live trading allowed: False",
        "- Real money allowed: False",
        "- Broker/API integration allowed: False",
        "- Candidate promotion allowed: False",
        "- Phase 16 paper preview currently represents the baseline SPY overlay, not Strategy Factory candidates.",
        "",
        "## Covered Strategies",
        "",
    ]
    for strategy in strategies:
        lines.append(f"- {strategy}")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- `strategy_transaction_ledger.csv`",
            "- `strategy_rebalance_summary.csv`",
            "- `strategy_weight_change_events.csv`",
            "- `strategy_turnover_timeline.csv`",
            "- `strategy_asset_allocation_long.csv`",
            "- `strategy_latest_allocations.csv`",
            "- `strategy_drift_rebalance_ledger.csv`",
            "- `strategy_drift_rebalance_summary.csv`",
            "- `strategy_rebalance_trade_matrix.csv`",
            "- `charts/allocation_timeline_by_strategy.png`",
            "- `charts/turnover_timeline_by_strategy.png`",
            "- `charts/transaction_count_by_asset.png`",
            "- `charts/latest_allocation_snapshot.png`",
            "- `charts/btc_weight_timeline.png`",
            "- `charts/drift_rebalance_trades_by_strategy.png`",
            "- `charts/drift_rebalance_trades_by_asset.png`",
            "- `charts/drift_rebalance_notional_by_asset.png`",
            "- `charts/spy_qqq_60_40_rebalance_timeline.png`",
            "",
            f"Total target-change transaction rows: {len(ledger)}",
            f"Strategies with transaction data: {len(summary)}",
            f"Total drift rebalance rows: {len(drift_ledger)}",
            f"Strategies covered by drift summary: {len(drift_summary)}",
        ]
    )
    (output_dir / "strategy_transaction_dashboard_index.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def save_strategy_factory_transaction_reports(
    *,
    allocation_file: str | Path = DEFAULT_ALLOCATION_FILE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    watchlist_file: str | Path = DEFAULT_WATCHLIST_FILE,
    price_data_dir: str | Path = DEFAULT_PRICE_DATA_DIR,
    asset_returns: pd.DataFrame | None = None,
    notional: float = DEFAULT_NOTIONAL,
) -> dict[str, pd.DataFrame]:
    output_path = Path(output_dir)
    chart_dir = output_path / "charts"
    output_path.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    allocation_path = Path(allocation_file)
    if not allocation_path.exists():
        raise FileNotFoundError(f"Strategy Factory allocation file missing: {allocation_path}")

    allocation = pd.read_csv(allocation_path)
    normalised_allocation = _normalise_allocation(allocation)
    all_strategies = sorted(normalised_allocation["strategy"].astype(str).unique().tolist())
    watchlist = _watchlist_strategies(Path(watchlist_file)) or []
    selected = all_strategies
    minimum = [strategy for strategy in watchlist if strategy not in selected]
    selected = [*selected, *minimum]
    assets = sorted(normalised_allocation["asset"].astype(str).unique().tolist())
    returns = asset_returns
    if returns is None:
        returns = load_asset_returns_from_processed(
            price_data_dir=price_data_dir,
            assets=assets,
        )

    ledger = create_transaction_ledger(
        normalised_allocation,
        notional=notional,
        strategies=selected,
    )
    rebalance_summary = create_rebalance_summary(ledger)
    turnover = create_turnover_timeline(ledger)
    allocation_long = _asset_allocation_long(normalised_allocation)
    latest = create_latest_allocations(normalised_allocation)
    drift_ledger = create_drift_rebalance_ledger(
        normalised_allocation,
        returns,
        notional=notional,
        strategies=selected,
    )
    drift_summary = create_drift_rebalance_summary(drift_ledger, strategies=selected)
    drift_trade_matrix = create_rebalance_trade_matrix(drift_ledger)
    events = ledger[
        [
            "strategy_id",
            "rebalance_date",
            "asset",
            "previous_weight",
            "target_weight",
            "weight_change",
            "transaction_direction",
            "turnover_contribution",
            "transaction_data_available",
            "notes",
        ]
    ].copy()

    ledger.to_csv(output_path / "strategy_transaction_ledger.csv", index=False)
    rebalance_summary.to_csv(output_path / "strategy_rebalance_summary.csv", index=False)
    events.to_csv(output_path / "strategy_weight_change_events.csv", index=False)
    turnover.to_csv(output_path / "strategy_turnover_timeline.csv", index=False)
    allocation_long.to_csv(output_path / "strategy_asset_allocation_long.csv", index=False)
    latest.to_csv(output_path / "strategy_latest_allocations.csv", index=False)
    drift_ledger.to_csv(output_path / "strategy_drift_rebalance_ledger.csv", index=False)
    drift_summary.to_csv(output_path / "strategy_drift_rebalance_summary.csv", index=False)
    drift_trade_matrix.to_csv(output_path / "strategy_rebalance_trade_matrix.csv", index=False)

    chart_strategies = watchlist or selected
    _plot_allocation_timeline(
        allocation_long,
        chart_strategies,
        chart_dir / "allocation_timeline_by_strategy.png",
    )
    _plot_turnover_timeline(
        turnover,
        chart_strategies,
        chart_dir / "turnover_timeline_by_strategy.png",
    )
    _plot_transaction_count_by_asset(ledger, chart_dir / "transaction_count_by_asset.png")
    _plot_latest_allocations(latest, chart_strategies, chart_dir / "latest_allocation_snapshot.png")
    _plot_btc_weight_timeline(allocation_long, chart_dir / "btc_weight_timeline.png")
    _plot_drift_rebalance_trades_by_strategy(
        drift_ledger,
        chart_dir / "drift_rebalance_trades_by_strategy.png",
    )
    _plot_drift_rebalance_trades_by_asset(
        drift_ledger,
        chart_dir / "drift_rebalance_trades_by_asset.png",
    )
    _plot_drift_rebalance_notional_by_asset(
        drift_ledger,
        chart_dir / "drift_rebalance_notional_by_asset.png",
    )
    _plot_spy_qqq_60_40_rebalance_timeline(
        drift_ledger,
        chart_dir / "spy_qqq_60_40_rebalance_timeline.png",
    )
    _write_index(
        output_dir=output_path,
        strategies=selected,
        ledger=ledger,
        summary=rebalance_summary,
        drift_ledger=drift_ledger,
        drift_summary=drift_summary,
    )

    outputs = {
        "ledger": ledger,
        "rebalance_summary": rebalance_summary,
        "weight_change_events": events,
        "turnover_timeline": turnover,
        "asset_allocation_long": allocation_long,
        "latest_allocations": latest,
        "drift_rebalance_ledger": drift_ledger,
        "drift_rebalance_summary": drift_summary,
        "rebalance_trade_matrix": drift_trade_matrix,
    }
    print("Wrote Strategy Factory transaction visual reports.")
    return outputs
