from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


INITIAL_CAPITAL = 10_000.0
SPY_BENCHMARK_ID = "SPY Buy & Hold Benchmark"
PHASE6_ID = "phase6b_loose_relief_execution_realistic_overlay"
MULTI_ASSET_ID = "canonical_spy_qqq_gld_tlt_50_30_10_10"
BTC_INV_VOL_ID = "canonical_inverse_vol_63d_btc_usd_qqq_spy"
SPY_QQQ_60_40_ID = "canonical_spy_qqq_60_40"

TRACKED_CANDIDATES = [
    PHASE6_ID,
    MULTI_ASSET_ID,
    BTC_INV_VOL_ID,
    SPY_QQQ_60_40_ID,
]

PERFORMANCE_DIR = Path("reports/paper_trading/regime_informed_tracking/performance")
VISUALS_DIR = Path("reports/paper_trading/regime_informed_tracking/performance_visuals")
NOTEBOOK_PATH = Path("notebooks/regime_informed_portfolio_performance_dashboard.ipynb")

NOTEBOOK_SECTIONS = [
    "What this notebook shows",
    "Current status in plain English",
    "Tracked strategies",
    "Historical performance: native periods",
    "Historical performance: common overlap period",
    "Strategy 1 - Phase6 loose relief overlay",
    "Strategy 2 - SPY/QQQ/GLD/TLT 50/30/10/10",
    "Strategy 3 - Inverse-vol SPY/QQQ/BTC 5% cap",
    "Strategy 4 - SPY/QQQ 60/40 reference",
    "Paper trading sessions",
    "Paper cash ledger",
    "Trade blotter",
    "Current holdings",
    "What changed today",
    "Next action",
]

HISTORICAL_CHARTS = {
    "native_final": "native_period_final_value_bar.png",
    "common_equity": "common_period_equity_curves.png",
    "common_drawdown": "common_period_drawdowns.png",
    "common_final": "common_period_final_value_bar.png",
    "risk_return": "risk_return_scatter.png",
    "phase6_equity": "phase6_equity_curve.png",
    "phase6_drawdown": "phase6_drawdown.png",
    "phase6_exposure": "phase6_exposure_or_weight.png",
    "multi_equity": "multi_asset_equity_curve.png",
    "multi_drawdown": "multi_asset_drawdown.png",
    "multi_weights": "multi_asset_weights_over_time.png",
    "btc_equity": "btc_inverse_vol_equity_curve.png",
    "btc_drawdown": "btc_inverse_vol_drawdown.png",
    "btc_weights": "btc_inverse_vol_weights_over_time.png",
    "spy_qqq_equity": "spy_qqq_60_40_equity_curve.png",
    "spy_qqq_drawdown": "spy_qqq_60_40_drawdown.png",
    "spy_qqq_weights": "spy_qqq_60_40_weights_over_time.png",
    "cash": "paper_cash_by_candidate.png",
    "entered_skipped": "paper_entered_vs_skipped_notional.png",
    "paper_value": "paper_portfolio_value_by_candidate.png",
    "blotter": "trade_blotter_actions.png",
}


@dataclass
class CandidateCurve:
    candidate_id: str
    role: str
    notes: str
    equity: pd.DataFrame
    weights: pd.DataFrame


def _ensure_dirs(performance_dir: Path, visuals_dir: Path, notebook_path: Path) -> None:
    performance_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir.mkdir(parents=True, exist_ok=True)
    notebook_path.parent.mkdir(parents=True, exist_ok=True)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _price_path(root: Path, symbol: str) -> Path:
    fresh = root / "data" / "fresh" / "processed" / f"{symbol}.parquet"
    if fresh.exists():
        return fresh
    return root / "data" / "processed" / f"{symbol}.parquet"


def _load_price_series(root: Path, symbol: str) -> pd.Series:
    path = _price_path(root, symbol)
    if not path.exists():
        raise FileNotFoundError(f"missing price file for {symbol}: {path}")
    frame = pd.read_parquet(path)
    if "date" not in frame.columns:
        raise ValueError(f"missing date column for {symbol}")
    price_col = "adj_close" if "adj_close" in frame.columns else "close"
    if price_col not in frame.columns:
        raise ValueError(f"missing price column for {symbol}")
    series = frame[["date", price_col]].copy()
    series["date"] = pd.to_datetime(series["date"])
    series = series.dropna(subset=["date", price_col]).drop_duplicates("date")
    series = series.sort_values("date").set_index("date")[price_col].astype(float)
    series = series.loc[series > 0]
    if series.empty:
        raise ValueError(f"no positive prices for {symbol}")
    return series.rename(symbol)


def _load_price_frame(root: Path, symbols: list[str]) -> pd.DataFrame:
    series = [_load_price_series(root, symbol) for symbol in symbols]
    return pd.concat(series, axis=1, join="inner").dropna().sort_index()


def _drawdown(values: pd.Series) -> pd.Series:
    return values / values.cummax() - 1.0


def _metrics(values: pd.Series) -> dict[str, float]:
    values = values.dropna().astype(float)
    if len(values) < 2:
        return {
            "initial_value": np.nan,
            "final_value": np.nan,
            "total_return_pct": np.nan,
            "CAGR": np.nan,
            "max_drawdown": np.nan,
        }
    years = max((values.index[-1] - values.index[0]).days / 365.25, 1 / 365.25)
    final_value = float(values.iloc[-1])
    initial_value = float(values.iloc[0])
    total_return = final_value / initial_value - 1.0
    cagr = (final_value / initial_value) ** (1.0 / years) - 1.0
    return {
        "initial_value": initial_value,
        "final_value": final_value,
        "total_return_pct": total_return * 100,
        "CAGR": cagr * 100,
        "max_drawdown": float(_drawdown(values).min()) * 100,
    }


def _period_return_weights(
    target_weights: pd.Series,
    period_returns: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    weights = target_weights.reindex(period_returns.columns).fillna(0.0).astype(float)
    portfolio_returns: list[float] = []
    weight_rows: list[pd.Series] = []
    for date, returns in period_returns.iterrows():
        portfolio_return = float((weights * returns.fillna(0.0)).sum())
        portfolio_returns.append(portfolio_return)
        drifted = weights * (1.0 + returns.fillna(0.0))
        total = float(drifted.sum())
        weights = drifted / total if total else target_weights
        weight_rows.append(weights.rename(date))
    return (
        pd.Series(portfolio_returns, index=period_returns.index),
        pd.DataFrame(weight_rows),
    )


def _monthly_rebalanced_equity(
    prices: pd.DataFrame,
    target_weights_by_date: pd.DataFrame,
    initial_capital: float,
) -> tuple[pd.Series, pd.DataFrame]:
    returns = prices.pct_change().fillna(0.0)
    rebalance_dates = target_weights_by_date.index
    equity_parts: list[pd.Series] = []
    weight_parts: list[pd.DataFrame] = []
    current_value = initial_capital
    for index, start_date in enumerate(rebalance_dates):
        end_date = (
            rebalance_dates[index + 1]
            if index + 1 < len(rebalance_dates)
            else returns.index[-1] + pd.Timedelta(days=1)
        )
        period_returns = returns.loc[(returns.index >= start_date) & (returns.index < end_date)]
        if period_returns.empty:
            continue
        target = target_weights_by_date.loc[start_date]
        period_portfolio_returns, period_weights = _period_return_weights(
            target,
            period_returns,
        )
        period_equity = current_value * (1.0 + period_portfolio_returns).cumprod()
        current_value = float(period_equity.iloc[-1])
        equity_parts.append(period_equity)
        period_weights.index = period_returns.index
        weight_parts.append(period_weights)
    if not equity_parts:
        return pd.Series(dtype=float), pd.DataFrame()
    equity = pd.concat(equity_parts).sort_index()
    weights = pd.concat(weight_parts).sort_index()
    equity.iloc[0] = initial_capital
    return equity, weights


def _monthly_dates(index: pd.DatetimeIndex, min_start: pd.Timestamp | None = None) -> pd.DatetimeIndex:
    usable = index if min_start is None else index[index >= min_start]
    if len(usable) == 0:
        return pd.DatetimeIndex([])
    month_ends = pd.Series(usable, index=usable).groupby(usable.to_period("M")).first()
    return pd.DatetimeIndex(month_ends.values)


def _fixed_candidate(
    root: Path,
    candidate_id: str,
    role: str,
    weights: dict[str, float],
    notes: str,
) -> CandidateCurve:
    symbols = list(weights)
    prices = _load_price_frame(root, symbols)
    monthly_dates = _monthly_dates(prices.index)
    target_weights = pd.DataFrame(index=monthly_dates, columns=symbols, dtype=float)
    for symbol, weight in weights.items():
        target_weights[symbol] = weight
    equity, daily_weights = _monthly_rebalanced_equity(
        prices,
        target_weights,
        INITIAL_CAPITAL,
    )
    equity_frame = pd.DataFrame(
        {
            "date": equity.index,
            "canonical_candidate_id": candidate_id,
            "portfolio_value": equity.values,
            "cash_balance": 0.0,
            "invested_value": equity.values,
            "strategy_role": role,
            "notes": notes,
        }
    )
    weights_frame = daily_weights.reset_index(names="date").melt(
        id_vars="date",
        var_name="asset",
        value_name="weight",
    )
    weights_frame["canonical_candidate_id"] = candidate_id
    return CandidateCurve(candidate_id, role, notes, equity_frame, weights_frame)


def _cap_weights(raw: pd.Series, max_asset_weight: float, btc_cap: float) -> pd.Series:
    weights = raw.astype(float).copy()
    caps = pd.Series(max_asset_weight, index=weights.index, dtype=float)
    if "BTC-USD" in caps.index:
        caps.loc["BTC-USD"] = btc_cap
    weights = weights / weights.sum()
    capped = pd.Series(0.0, index=weights.index)
    remaining_assets = list(weights.index)
    remaining_weight = 1.0
    remaining_raw = weights.copy()
    for _ in range(len(weights) + 2):
        if not remaining_assets:
            break
        tentative = remaining_raw.loc[remaining_assets]
        tentative = tentative / tentative.sum() * remaining_weight
        binding = tentative[tentative > caps.loc[tentative.index]]
        if binding.empty:
            capped.loc[tentative.index] = tentative
            break
        for asset in binding.index:
            capped.loc[asset] = caps.loc[asset]
            remaining_weight -= caps.loc[asset]
            remaining_assets.remove(asset)
        if remaining_weight < -1e-9:
            raise ValueError("caps make inverse-vol allocation impossible")
    total = capped.sum()
    if not math.isclose(float(total), 1.0, abs_tol=1e-6):
        residual_assets = capped[capped < caps].index
        if len(residual_assets) == 0:
            raise ValueError("unable to normalize capped weights")
        capped.loc[residual_assets] += (1.0 - total) / len(residual_assets)
    return capped.clip(lower=0.0)


def _inverse_vol_candidate(root: Path) -> CandidateCurve:
    candidate_id = BTC_INV_VOL_ID
    role = "provisional_high_caveat_candidate"
    notes = "BTC high-caveat; inception-limited; weekend/gap risk; paper-only"
    symbols = ["SPY", "QQQ", "BTC-USD"]
    prices = _load_price_frame(root, symbols)
    returns = prices.pct_change().dropna()
    lookback = 63
    rebalance_dates = _monthly_dates(returns.index, min_start=returns.index[min(lookback, len(returns) - 1)])
    weight_rows: list[pd.Series] = []
    for date in rebalance_dates:
        history = returns.loc[returns.index < date].tail(lookback)
        if len(history) < lookback:
            continue
        vol = history.std().replace(0.0, np.nan)
        raw = (1.0 / vol).dropna()
        raw = raw.reindex(symbols).dropna()
        if raw.empty:
            continue
        capped = _cap_weights(raw, max_asset_weight=0.50, btc_cap=0.05)
        weight_rows.append(capped.rename(date))
    target_weights = pd.DataFrame(weight_rows)
    equity, daily_weights = _monthly_rebalanced_equity(
        prices.loc[prices.index >= target_weights.index.min()],
        target_weights,
        INITIAL_CAPITAL,
    )
    equity_frame = pd.DataFrame(
        {
            "date": equity.index,
            "canonical_candidate_id": candidate_id,
            "portfolio_value": equity.values,
            "cash_balance": 0.0,
            "invested_value": equity.values,
            "strategy_role": role,
            "notes": notes,
        }
    )
    weights_frame = daily_weights.reset_index(names="date").melt(
        id_vars="date",
        var_name="asset",
        value_name="weight",
    )
    weights_frame["canonical_candidate_id"] = candidate_id
    return CandidateCurve(candidate_id, role, notes, equity_frame, weights_frame)


def _phase6_candidate(root: Path) -> CandidateCurve:
    path = root / "reports" / "phase6b_loose_relief_execution_realistic_overlay_daily.csv"
    role = "provisional_core_candidate"
    notes = "original defensive overlay baseline; lower drawdown, lower raw wealth; paper-only"
    if not path.exists():
        equity = pd.DataFrame(
            columns=[
                "date",
                "canonical_candidate_id",
                "portfolio_value",
                "cash_balance",
                "invested_value",
                "strategy_role",
                "notes",
            ]
        )
        weights = pd.DataFrame(columns=["date", "asset", "weight", "canonical_candidate_id"])
        return CandidateCurve(PHASE6_ID, role, "phase6 daily equity missing", equity, weights)
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["decision_date"])
    frame = frame.sort_values("date")
    value = pd.to_numeric(frame["candidate_equity"], errors="coerce")
    exposure = pd.to_numeric(frame.get("exposure", 1.0), errors="coerce").fillna(1.0)
    cash_balance = value * (1.0 - exposure)
    invested_value = value * exposure
    equity = pd.DataFrame(
        {
            "date": frame["date"],
            "canonical_candidate_id": PHASE6_ID,
            "portfolio_value": value,
            "cash_balance": cash_balance,
            "invested_value": invested_value,
            "strategy_role": role,
            "notes": notes,
        }
    ).dropna(subset=["portfolio_value"])
    weights = pd.DataFrame(
        {
            "date": frame["date"],
            "asset": "SPY",
            "weight": exposure,
            "canonical_candidate_id": PHASE6_ID,
        }
    )
    cash_weights = pd.DataFrame(
        {
            "date": frame["date"],
            "asset": "CASH",
            "weight": 1.0 - exposure,
            "canonical_candidate_id": PHASE6_ID,
        }
    )
    return CandidateCurve(PHASE6_ID, role, notes, equity, pd.concat([weights, cash_weights]))


def build_historical_curves(root: Path) -> list[CandidateCurve]:
    def empty_candidate(candidate_id: str, role: str, notes: str) -> CandidateCurve:
        return CandidateCurve(
            candidate_id,
            role,
            notes,
            pd.DataFrame(
                columns=[
                    "date",
                    "canonical_candidate_id",
                    "portfolio_value",
                    "cash_balance",
                    "invested_value",
                    "strategy_role",
                    "notes",
                ]
            ),
            pd.DataFrame(columns=["date", "asset", "weight", "canonical_candidate_id"]),
        )

    curves: list[CandidateCurve] = []
    try:
        curves.append(
            _fixed_candidate(
                root,
                SPY_BENCHMARK_ID,
                "benchmark_only",
                {"SPY": 1.0},
                "SPY Buy & Hold Benchmark; benchmark-only, not paper-tracked; local SPY adjusted-close source",
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        curves.append(
            empty_candidate(
                SPY_BENCHMARK_ID,
                "benchmark_only",
                f"benchmark historical data missing: {exc}",
            )
        )
    curves.append(_phase6_candidate(root))
    builders = [
        (
            MULTI_ASSET_ID,
            "provisional_core_inception_limited",
            lambda: _fixed_candidate(
                root,
                MULTI_ASSET_ID,
                "provisional_core_inception_limited",
                {"SPY": 0.50, "QQQ": 0.30, "GLD": 0.10, "TLT": 0.10},
                "monthly rebalanced static 50/30/10/10 allocation; asset inception limited",
            ),
        ),
        (
            BTC_INV_VOL_ID,
            "provisional_high_caveat_candidate",
            lambda: _inverse_vol_candidate(root),
        ),
        (
            SPY_QQQ_60_40_ID,
            "reference_only",
            lambda: _fixed_candidate(
                root,
                SPY_QQQ_60_40_ID,
                "reference_only",
                {"SPY": 0.60, "QQQ": 0.40},
                "monthly rebalanced SPY/QQQ reference only; severe drawdown risk",
            ),
        ),
    ]
    for candidate_id, role, builder in builders:
        try:
            curves.append(builder())
        except (FileNotFoundError, ValueError) as exc:
            curves.append(empty_candidate(candidate_id, role, f"historical data missing: {exc}"))
    return curves


def _native_summary(curves: list[CandidateCurve]) -> pd.DataFrame:
    rows = []
    for curve in curves:
        frame = curve.equity.copy()
        if frame.empty:
            rows.append(
                {
                    "candidate_id": curve.candidate_id,
                    "candidate_role": curve.role,
                    "start_date": "",
                    "end_date": "",
                    "initial_value": np.nan,
                    "final_value": np.nan,
                    "total_return_pct": np.nan,
                    "CAGR": np.nan,
                    "max_drawdown": np.nan,
                    "notes": curve.notes,
                }
            )
            continue
        values = frame.set_index("date")["portfolio_value"]
        metrics = _metrics(values)
        rows.append(
            {
                "candidate_id": curve.candidate_id,
                "candidate_role": curve.role,
                "start_date": values.index.min().date().isoformat(),
                "end_date": values.index.max().date().isoformat(),
                **metrics,
                "notes": curve.notes,
            }
        )
    return pd.DataFrame(rows)


def _daily_equity(curves: list[CandidateCurve]) -> pd.DataFrame:
    frames = [curve.equity for curve in curves if not curve.equity.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(
        ["canonical_candidate_id", "date"]
    )


def _daily_drawdowns(daily_equity: pd.DataFrame) -> pd.DataFrame:
    if daily_equity.empty:
        return pd.DataFrame(
            columns=["date", "canonical_candidate_id", "drawdown", "drawdown_pct"]
        )
    rows = []
    for candidate_id, group in daily_equity.groupby("canonical_candidate_id"):
        values = group.sort_values("date").set_index("date")["portfolio_value"]
        drawdowns = _drawdown(values)
        rows.append(
            pd.DataFrame(
                {
                    "date": drawdowns.index,
                    "canonical_candidate_id": candidate_id,
                    "drawdown": drawdowns.values,
                    "drawdown_pct": drawdowns.values * 100,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def _common_summary(daily_equity: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    if daily_equity.empty:
        return pd.DataFrame(), "", ""
    date_sets = []
    for _candidate_id, group in daily_equity.groupby("canonical_candidate_id"):
        date_sets.append(set(pd.to_datetime(group["date"])))
    common_dates = sorted(set.intersection(*date_sets)) if date_sets else []
    if len(common_dates) < 2:
        return pd.DataFrame(), "", ""
    common_start = common_dates[0]
    common_end = common_dates[-1]
    rows = []
    for candidate_id, group in daily_equity.groupby("canonical_candidate_id"):
        role = (
            group["strategy_role"].iloc[0]
            if "strategy_role" in group.columns and not group.empty
            else ""
        )
        series = (
            group.assign(date=pd.to_datetime(group["date"]))
            .set_index("date")
            .sort_index()["portfolio_value"]
            .reindex(common_dates)
            .dropna()
        )
        normalized = series / float(series.iloc[0]) * INITIAL_CAPITAL
        metrics = _metrics(normalized)
        rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_role": role,
                "common_start_date": common_start.date().isoformat(),
                "common_end_date": common_end.date().isoformat(),
                **metrics,
                "notes": "common overlap; BTC restricts comparison period when included",
            }
        )
    return pd.DataFrame(rows), common_start.date().isoformat(), common_end.date().isoformat()


def _build_trade_blotter(ledger: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "session_date",
        "selected_signal_date",
        "canonical_candidate_id",
        "candidate_role",
        "asset",
        "action",
        "target_weight",
        "target_notional_usd",
        "fill_price",
        "fill_quantity",
        "actual_notional_usd",
        "cash_effect_usd",
        "manual_execution_status",
        "paper_fill_timestamp_utc",
        "fill_timestamp_status",
        "notes",
    ]
    if ledger.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for row in ledger.to_dict("records"):
        status = str(row.get("manual_execution_status", "")).lower()
        decision = str(row.get("manual_decision", ""))
        fill_price = pd.to_numeric(row.get("paper_fill_price"), errors="coerce")
        fill_quantity = pd.to_numeric(row.get("paper_fill_quantity"), errors="coerce")
        actual_notional = pd.to_numeric(row.get("actual_notional_usd"), errors="coerce")
        if status == "skipped":
            action = "SKIPPED"
            cash_effect = 0.0
        elif status == "blocked":
            action = "BLOCKED"
            cash_effect = 0.0
        elif status == "entered":
            actual_notional = (
                float(fill_price) * float(fill_quantity)
                if pd.notna(fill_price) and pd.notna(fill_quantity)
                else actual_notional
            )
            action = "BUY" if pd.notna(actual_notional) and actual_notional > 0 else "HOLD/REBALANCE"
            cash_effect = -float(actual_notional) if pd.notna(actual_notional) else np.nan
        else:
            action = decision.upper() if decision else "UNKNOWN"
            cash_effect = np.nan
        timestamp = row.get("paper_fill_timestamp_utc", "")
        rows.append(
            {
                "session_date": row.get("session_date", ""),
                "selected_signal_date": row.get("selected_signal_date", ""),
                "canonical_candidate_id": row.get("canonical_candidate_id", ""),
                "candidate_role": row.get("candidate_role", ""),
                "asset": row.get("asset", ""),
                "action": action,
                "target_weight": row.get("target_weight", ""),
                "target_notional_usd": row.get("target_notional_usd", ""),
                "fill_price": "" if pd.isna(fill_price) else float(fill_price),
                "fill_quantity": "" if pd.isna(fill_quantity) else float(fill_quantity),
                "actual_notional_usd": ""
                if pd.isna(actual_notional)
                else float(actual_notional),
                "cash_effect_usd": cash_effect,
                "manual_execution_status": row.get("manual_execution_status", ""),
                "paper_fill_timestamp_utc": timestamp,
                "fill_timestamp_status": "recorded"
                if str(timestamp).strip()
                else "not_recorded_date_only",
                "notes": row.get("notes", ""),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _paper_cash_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "session_date",
        "canonical_candidate_id",
        "starting_cash",
        "cash_used",
        "cash_remaining",
        "entered_notional",
        "skipped_notional",
        "total_portfolio_value",
        "notes",
    ]
    if ledger.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for (session_date, candidate_id), group in ledger.groupby(
        ["session_date", "canonical_candidate_id"],
        dropna=False,
    ):
        status = group["manual_execution_status"].astype(str).str.lower()
        target = pd.to_numeric(group.get("target_notional_usd"), errors="coerce").fillna(0.0)
        actual = pd.to_numeric(group.get("actual_notional_usd"), errors="coerce").fillna(0.0)
        entered_notional = float(actual.loc[status == "entered"].sum())
        skipped_notional = float(target.loc[status == "skipped"].sum())
        cash_used = entered_notional
        rows.append(
            {
                "session_date": session_date,
                "canonical_candidate_id": candidate_id,
                "starting_cash": INITIAL_CAPITAL,
                "cash_used": cash_used,
                "cash_remaining": INITIAL_CAPITAL - cash_used,
                "entered_notional": entered_notional,
                "skipped_notional": skipped_notional,
                "total_portfolio_value": INITIAL_CAPITAL,
                "notes": "skipped session, no entered positions"
                if entered_notional == 0
                else "entered paper rows present; date-level accounting only",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _paper_holdings(ledger: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "session_date",
        "canonical_candidate_id",
        "asset",
        "quantity",
        "fill_price",
        "market_price",
        "market_value",
        "cash_balance",
        "total_portfolio_value",
        "unrealized_pnl",
        "notes",
    ]
    if ledger.empty:
        return pd.DataFrame(columns=columns)
    entered = ledger.loc[
        ledger["manual_execution_status"].astype(str).str.lower() == "entered"
    ].copy()
    if entered.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for row in entered.to_dict("records"):
        fill_price = pd.to_numeric(row.get("paper_fill_price"), errors="coerce")
        quantity = pd.to_numeric(row.get("paper_fill_quantity"), errors="coerce")
        market_value = float(fill_price * quantity) if pd.notna(fill_price) and pd.notna(quantity) else np.nan
        rows.append(
            {
                "session_date": row.get("session_date", ""),
                "canonical_candidate_id": row.get("canonical_candidate_id", ""),
                "asset": row.get("asset", ""),
                "quantity": quantity,
                "fill_price": fill_price,
                "market_price": fill_price,
                "market_value": market_value,
                "cash_balance": np.nan,
                "total_portfolio_value": np.nan,
                "unrealized_pnl": 0.0,
                "notes": "date-level paper holding from manual fill ledger",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _write_csvs(
    *,
    performance_dir: Path,
    curves: list[CandidateCurve],
    ledger: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    native = _native_summary(curves)
    equity = _daily_equity(curves)
    drawdowns = _daily_drawdowns(equity)
    weights = pd.concat(
        [curve.weights for curve in curves if not curve.weights.empty],
        ignore_index=True,
    )
    common, common_start, common_end = _common_summary(equity)
    blotter = _build_trade_blotter(ledger)
    cash = _paper_cash_ledger(ledger)
    holdings = _paper_holdings(ledger)
    sessions = int(ledger["session_date"].nunique()) if not ledger.empty else 0
    entered_sessions = int(
        ledger.loc[
            ledger["manual_execution_status"].astype(str).str.lower() == "entered",
            "session_date",
        ].nunique()
    ) if not ledger.empty else 0
    skipped_sessions = int(
        ledger.loc[
            ledger["manual_execution_status"].astype(str).str.lower() == "skipped",
            "session_date",
        ].nunique()
    ) if not ledger.empty else 0
    paper_positions_exist = not holdings.empty
    status = pd.DataFrame(
        [
            {
                "run_date": datetime.now(timezone.utc).date().isoformat(),
                "notebook_path": str(NOTEBOOK_PATH),
                "visuals_dir": str(VISUALS_DIR),
                "performance_dir": str(performance_dir),
                "candidates_count": len(TRACKED_CANDIDATES),
                "historical_candidates_loaded": native["final_value"].notna().sum(),
                "common_start_date": common_start,
                "common_end_date": common_end,
                "paper_sessions": sessions,
                "entered_sessions": entered_sessions,
                "skipped_sessions": skipped_sessions,
                "paper_positions_exist": paper_positions_exist,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "status": "performance_dashboard_written_manual_paper_only",
                "notes": (
                    "No entered paper trades yet. The first valid regime-informed "
                    "paper cycle was a skip/review cycle, not a filled-position cycle."
                    if not paper_positions_exist
                    else "entered paper rows present; date-level accounting only"
                ),
            }
        ]
    )
    outputs = {
        "native_summary": native,
        "common_summary": common,
        "daily_equity": equity,
        "daily_drawdowns": drawdowns,
        "daily_weights": weights,
        "trade_blotter": blotter,
        "cash_ledger": cash,
        "holdings": holdings,
        "status": status,
    }
    file_map = {
        "native_summary": "regime_informed_historical_native_summary.csv",
        "common_summary": "regime_informed_historical_common_summary.csv",
        "daily_equity": "regime_informed_historical_daily_equity.csv",
        "daily_drawdowns": "regime_informed_historical_daily_drawdowns.csv",
        "daily_weights": "regime_informed_historical_daily_weights.csv",
        "trade_blotter": "regime_informed_trade_blotter.csv",
        "cash_ledger": "regime_informed_paper_cash_ledger.csv",
        "holdings": "regime_informed_paper_holdings.csv",
        "status": "regime_informed_performance_dashboard_status.csv",
    }
    for key, filename in file_map.items():
        outputs[key].to_csv(performance_dir / filename, index=False)
    return outputs


def _placeholder(path: Path, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axis("off")
    ax.set_title(title)
    ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_bar(frame: pd.DataFrame, x: str, y: str, path: Path, title: str, ylabel: str) -> None:
    if frame.empty or x not in frame.columns or y not in frame.columns:
        _placeholder(path, title, f"Missing {x}/{y} data")
        return
    plot_frame = frame[[x, y]].copy()
    plot_frame[y] = pd.to_numeric(plot_frame[y], errors="coerce")
    plot_frame = plot_frame.dropna(subset=[y])
    if plot_frame.empty:
        _placeholder(path, title, "No numeric values available")
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(plot_frame[x], plot_frame[y])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_lines(
    frame: pd.DataFrame,
    *,
    value_col: str,
    path: Path,
    title: str,
    ylabel: str,
    candidates: list[str] | None = None,
) -> None:
    if frame.empty or not {"date", "canonical_candidate_id", value_col}.issubset(frame.columns):
        _placeholder(path, title, f"Missing {value_col} data")
        return
    fig, ax = plt.subplots(figsize=(11, 5.5))
    plot_frame = frame.copy()
    plot_frame["date"] = pd.to_datetime(plot_frame["date"])
    plotted = 0
    for candidate_id, group in plot_frame.groupby("canonical_candidate_id"):
        if candidates is not None and candidate_id not in candidates:
            continue
        series = group.sort_values("date")
        ax.plot(series["date"], series[value_col], label=candidate_id)
        plotted += 1
    if plotted == 0:
        plt.close(fig)
        _placeholder(path, title, "No candidate series available")
        return
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_weights(
    weights: pd.DataFrame,
    candidate_id: str,
    path: Path,
    title: str,
) -> None:
    if weights.empty:
        _placeholder(path, title, "No weights available")
        return
    frame = weights.loc[weights["canonical_candidate_id"] == candidate_id].copy()
    if frame.empty:
        _placeholder(path, title, "No candidate weights available")
        return
    frame["date"] = pd.to_datetime(frame["date"])
    pivot = frame.pivot_table(index="date", columns="asset", values="weight", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for asset in pivot.columns:
        ax.plot(pivot.index, pivot[asset], label=asset)
    ax.set_title(title)
    ax.set_ylabel("Weight")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_risk_return(native: pd.DataFrame, path: Path) -> None:
    if native.empty:
        _placeholder(path, "Risk/Return Scatter", "Missing native summary")
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = pd.to_numeric(native["max_drawdown"], errors="coerce")
    y = pd.to_numeric(native["CAGR"], errors="coerce")
    ax.scatter(x, y)
    for row, x_value, y_value in zip(native.itertuples(index=False), x, y):
        if pd.notna(x_value) and pd.notna(y_value):
            ax.annotate(row.candidate_id[:28], (x_value, y_value), fontsize=8)
    ax.set_title("Risk/Return Scatter")
    ax.set_xlabel("Max drawdown (%)")
    ax.set_ylabel("CAGR (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_entered_skipped(cash: pd.DataFrame, path: Path) -> None:
    if cash.empty:
        _placeholder(path, "Entered vs Skipped Notional", "No cash ledger rows")
        return
    totals = {
        "entered_notional": pd.to_numeric(cash["entered_notional"], errors="coerce").sum(),
        "skipped_notional": pd.to_numeric(cash["skipped_notional"], errors="coerce").sum(),
    }
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(list(totals), list(totals.values()))
    ax.set_title("Paper Entered vs Skipped Notional")
    ax.set_ylabel("USD")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _plot_blotter(blotter: pd.DataFrame, path: Path) -> None:
    if blotter.empty or "action" not in blotter.columns:
        _placeholder(path, "Trade Blotter Actions", "No trade blotter rows")
        return
    counts = blotter["action"].astype(str).value_counts()
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(counts.index, counts.values)
    ax.set_title("Trade Blotter Actions")
    ax.set_ylabel("Rows")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _write_visuals(outputs: dict[str, pd.DataFrame], visuals_dir: Path) -> dict[str, Path]:
    paths = {key: visuals_dir / filename for key, filename in HISTORICAL_CHARTS.items()}
    native = outputs["native_summary"]
    common = outputs["common_summary"]
    equity = outputs["daily_equity"]
    drawdowns = outputs["daily_drawdowns"]
    weights = outputs["daily_weights"]
    cash = outputs["cash_ledger"]
    blotter = outputs["trade_blotter"]
    _plot_bar(native, "candidate_id", "final_value", paths["native_final"], "Native Period Final Value", "USD")
    _plot_bar(common, "candidate_id", "final_value", paths["common_final"], "Common Period Final Value", "USD")
    _plot_risk_return(native, paths["risk_return"])
    if not common.empty:
        common_dates = (common["common_start_date"].iloc[0], common["common_end_date"].iloc[0])
        common_equity = equity.loc[
            (pd.to_datetime(equity["date"]) >= pd.Timestamp(common_dates[0]))
            & (pd.to_datetime(equity["date"]) <= pd.Timestamp(common_dates[1]))
        ].copy()
        normalized_rows = []
        for candidate_id, group in common_equity.groupby("canonical_candidate_id"):
            group = group.sort_values("date").copy()
            group["portfolio_value"] = (
                group["portfolio_value"] / group["portfolio_value"].iloc[0] * INITIAL_CAPITAL
            )
            normalized_rows.append(group)
        common_equity = pd.concat(normalized_rows, ignore_index=True) if normalized_rows else pd.DataFrame()
        common_drawdowns = _daily_drawdowns(common_equity)
    else:
        common_equity = pd.DataFrame()
        common_drawdowns = pd.DataFrame()
    _plot_lines(common_equity, value_col="portfolio_value", path=paths["common_equity"], title="Common Period Equity Curves", ylabel="USD")
    _plot_lines(common_drawdowns, value_col="drawdown_pct", path=paths["common_drawdown"], title="Common Period Drawdowns", ylabel="Drawdown (%)")
    for candidate_id, equity_key, drawdown_key, weight_key, title in [
        (PHASE6_ID, "phase6_equity", "phase6_drawdown", "phase6_exposure", "Phase6 Loose Relief"),
        (MULTI_ASSET_ID, "multi_equity", "multi_drawdown", "multi_weights", "SPY/QQQ/GLD/TLT 50/30/10/10"),
        (BTC_INV_VOL_ID, "btc_equity", "btc_drawdown", "btc_weights", "Inverse-Vol SPY/QQQ/BTC 5% Cap"),
        (SPY_QQQ_60_40_ID, "spy_qqq_equity", "spy_qqq_drawdown", "spy_qqq_weights", "SPY/QQQ 60/40"),
    ]:
        _plot_lines(equity, value_col="portfolio_value", path=paths[equity_key], title=f"{title} Equity Curve", ylabel="USD", candidates=[candidate_id])
        _plot_lines(drawdowns, value_col="drawdown_pct", path=paths[drawdown_key], title=f"{title} Drawdown", ylabel="Drawdown (%)", candidates=[candidate_id])
        _plot_weights(weights, candidate_id, paths[weight_key], f"{title} Weights")
    _plot_bar(cash, "canonical_candidate_id", "cash_remaining", paths["cash"], "Paper Cash Remaining by Candidate", "USD")
    _plot_entered_skipped(cash, paths["entered_skipped"])
    _plot_bar(cash, "canonical_candidate_id", "total_portfolio_value", paths["paper_value"], "Paper Portfolio Value by Candidate", "USD")
    _plot_blotter(blotter, paths["blotter"])
    return paths


def _md_image(root: Path, path: Path) -> str:
    notebook_dir = root / "notebooks"
    try:
        rel = path.relative_to(notebook_dir)
    except ValueError:
        try:
            rel = Path("..") / path.relative_to(root)
        except ValueError:
            rel = path
    if not path.exists():
        return f"**Missing image:** `{rel.as_posix()}`"
    return f"![{path.stem}]({rel.as_posix()})"


def _markdown_cell(source: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)}


def _code_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(True),
    }


def _write_notebook(root: Path, notebook_path: Path, visuals: dict[str, Path]) -> None:
    cells = [
        _markdown_cell(
            "# Regime-Informed Portfolio Performance Dashboard\n\n"
            "This notebook is for performance and paper-trading visibility. "
            "The older regime_informed_results_dashboard.ipynb is mainly a "
            "research-selection dashboard.\n\n"
            "If a PNG is missing, the affected section displays `Missing image: ...` "
            "instead of silently rendering a broken image.\n\n"
            "NO LIVE TRADING\n\nNO REAL MONEY\n\nNO BROKER/API\n\n"
            "NO STRATEGY PROMOTION"
        ),
        _code_cell(
            "from pathlib import Path\n"
            "import pandas as pd\n\n"
            "ROOT = Path('..').resolve()\n"
            "PERFORMANCE = ROOT / 'reports/paper_trading/regime_informed_tracking/performance'\n"
            "def read_csv(name):\n"
            "    path = PERFORMANCE / name\n"
            "    return pd.read_csv(path) if path.exists() else pd.DataFrame({'missing_file': [str(path)]})\n"
            "native = read_csv('regime_informed_historical_native_summary.csv')\n"
            "common = read_csv('regime_informed_historical_common_summary.csv')\n"
            "cash = read_csv('regime_informed_paper_cash_ledger.csv')\n"
            "blotter = read_csv('regime_informed_trade_blotter.csv')\n"
            "holdings = read_csv('regime_informed_paper_holdings.csv')\n"
            "status = read_csv('regime_informed_performance_dashboard_status.csv')\n"
            "status"
        ),
        _markdown_cell(
            "## What this notebook shows\n\n"
            "It separates historical strategy visibility from manual paper-session "
            "accounting. It shows native-period results, common-overlap results, "
            "current targets, trade blotter rows, cash accounting, and whether "
            "paper trades were entered or skipped."
        ),
        _markdown_cell(
            "## Current status in plain English\n\n"
            "No entered paper trades yet. The first valid regime-informed paper "
            "cycle was a skip/review cycle, not a filled-position cycle."
        ),
        _markdown_cell(
            "## Tracked strategies\n\n"
            "Tracked paper candidates: 4\n\n"
            "Benchmark: SPY Buy & Hold. The benchmark is historical comparison only "
            "and is not paper-tracked."
        ),
        _code_cell("native[['candidate_id','start_date','end_date','notes']] if 'candidate_id' in native.columns else native"),
        _markdown_cell("## Historical performance: native periods\n\n" + _md_image(root, visuals["native_final"])),
        _code_cell("native"),
        _markdown_cell("## Historical performance: common overlap period\n\n" + _md_image(root, visuals["common_equity"]) + "\n\n" + _md_image(root, visuals["common_drawdown"]) + "\n\n" + _md_image(root, visuals["common_final"]) + "\n\nCommon overlap is restricted by the latest-inception candidate, including BTC where present."),
        _code_cell("common"),
        _markdown_cell("## Strategy 1 - Phase6 loose relief overlay\n\n" + _md_image(root, visuals["phase6_equity"]) + "\n\n" + _md_image(root, visuals["phase6_drawdown"]) + "\n\n" + _md_image(root, visuals["phase6_exposure"])),
        _markdown_cell("## Strategy 2 - SPY/QQQ/GLD/TLT 50/30/10/10\n\n" + _md_image(root, visuals["multi_equity"]) + "\n\n" + _md_image(root, visuals["multi_drawdown"]) + "\n\n" + _md_image(root, visuals["multi_weights"])),
        _markdown_cell("## Strategy 3 - Inverse-vol SPY/QQQ/BTC 5% cap\n\nBTC is post-inception/high-caveat only.\n\n" + _md_image(root, visuals["btc_equity"]) + "\n\n" + _md_image(root, visuals["btc_drawdown"]) + "\n\n" + _md_image(root, visuals["btc_weights"])),
        _markdown_cell("## Strategy 4 - SPY/QQQ 60/40 reference\n\nReference-only growth benchmark, not a promoted strategy.\n\n" + _md_image(root, visuals["spy_qqq_equity"]) + "\n\n" + _md_image(root, visuals["spy_qqq_drawdown"]) + "\n\n" + _md_image(root, visuals["spy_qqq_weights"])),
        _markdown_cell("## Paper trading sessions"),
        _code_cell("status"),
        _markdown_cell("## Paper cash ledger\n\n" + _md_image(root, visuals["cash"]) + "\n\n" + _md_image(root, visuals["entered_skipped"]) + "\n\n" + _md_image(root, visuals["paper_value"])),
        _code_cell("cash"),
        _markdown_cell("## Trade blotter\n\n" + _md_image(root, visuals["blotter"])),
        _code_cell("blotter"),
        _markdown_cell("## Current holdings"),
        _code_cell("holdings if not holdings.empty else 'No entered paper positions exist yet.'"),
        _markdown_cell("## What changed today\n\nThe dashboard now distinguishes research-selection output from portfolio/performance visibility and makes skipped paper cycles explicit."),
        _markdown_cell("## Next action\n\nReview warnings, BTC caveats, and manual paper-session status before any future paper entry. Do not use live trading, real money, broker/API, or strategy promotion."),
    ]
    notebook = {
        "cells": cells,
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
    notebook_path.write_text(json.dumps(notebook, indent=2) + "\n", encoding="utf-8")


def build_regime_informed_portfolio_dashboard(
    *,
    root: Path | None = None,
    performance_dir: Path | None = None,
    visuals_dir: Path | None = None,
    notebook_path: Path | None = None,
) -> dict[str, Path]:
    root = Path.cwd() if root is None else Path(root)
    performance_dir = root / PERFORMANCE_DIR if performance_dir is None else Path(performance_dir)
    visuals_dir = root / VISUALS_DIR if visuals_dir is None else Path(visuals_dir)
    notebook_path = root / NOTEBOOK_PATH if notebook_path is None else Path(notebook_path)
    _ensure_dirs(performance_dir, visuals_dir, notebook_path)
    curves = build_historical_curves(root)
    ledger = _read_csv(
        root
        / "reports"
        / "paper_trading"
        / "regime_informed_tracking"
        / "regime_informed_manual_session_ledger.csv"
    )
    outputs = _write_csvs(performance_dir=performance_dir, curves=curves, ledger=ledger)
    visuals = _write_visuals(outputs, visuals_dir)
    _write_notebook(root, notebook_path, visuals)
    return {
        "notebook": notebook_path,
        "performance_dir": performance_dir,
        "visuals_dir": visuals_dir,
        **{f"csv_{key}": performance_dir / filename for key, filename in {
            "native_summary": "regime_informed_historical_native_summary.csv",
            "common_summary": "regime_informed_historical_common_summary.csv",
            "daily_equity": "regime_informed_historical_daily_equity.csv",
            "daily_drawdowns": "regime_informed_historical_daily_drawdowns.csv",
            "daily_weights": "regime_informed_historical_daily_weights.csv",
            "trade_blotter": "regime_informed_trade_blotter.csv",
            "cash_ledger": "regime_informed_paper_cash_ledger.csv",
            "holdings": "regime_informed_paper_holdings.csv",
            "status": "regime_informed_performance_dashboard_status.csv",
        }.items()},
        **{f"chart_{key}": path for key, path in visuals.items()},
    }
