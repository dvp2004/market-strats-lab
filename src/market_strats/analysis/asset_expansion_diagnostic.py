from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.strategies.fixed_weight_portfolio import (
    rebase_strategy_result_to_dates,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _safe_name(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "_")
        .replace("+", "plus")
        .replace("/", "_")
        .replace("-", "_")
    )


def _get_price_data(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"{ticker} missing from ticker_outputs")

    output = ticker_outputs[ticker]

    price_data = output.get("price_data")

    if price_data is None or price_data.empty:
        price_data = output.get("data")

    if price_data is None or price_data.empty:
        raise ValueError(f"{ticker} has no preserved price_data/data frame")

    required_columns = {"date", "adj_close"}
    missing_columns = required_columns - set(price_data.columns)

    if missing_columns:
        raise ValueError(
            f"{ticker} price data missing required columns: {sorted(missing_columns)}"
        )

    frame = price_data[["date", "adj_close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["adj_close"] = frame["adj_close"].astype(float)

    return frame.sort_values("date").dropna().reset_index(drop=True)


def _get_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
    strategy: str,
) -> pd.DataFrame:
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"{ticker} missing from ticker_outputs")

    strategy_results = ticker_outputs[ticker].get("strategy_results")

    if strategy_results is None or strategy not in strategy_results:
        available = (
            sorted(strategy_results.keys())
            if isinstance(strategy_results, dict)
            else []
        )
        raise ValueError(
            f"Strategy '{strategy}' missing for {ticker}. Available: {available}"
        )

    return strategy_results[strategy]


def _build_close_panel(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    assets: list[str],
) -> pd.DataFrame:
    series_by_ticker: dict[str, pd.Series] = {}

    for ticker in assets:
        price_data = _get_price_data(ticker_outputs, ticker)
        series = price_data.set_index("date")["adj_close"].rename(ticker.upper())
        series_by_ticker[ticker.upper()] = series

    panel = pd.concat(series_by_ticker.values(), axis=1, join="inner")
    panel = panel.sort_index().dropna(how="any")

    if panel.empty:
        raise ValueError(f"No overlapping price history for assets: {assets}")

    return panel


def _normalise_weights(
    raw_weights: pd.Series,
) -> pd.Series:
    total = float(raw_weights.sum())

    if total <= 0:
        return raw_weights * 0.0

    return raw_weights / total


def _apply_constraints(
    selected_assets: list[str],
    max_asset_weight: float,
    group_caps: dict[str, float],
    asset_groups: dict[str, str],
) -> pd.Series:
    if not selected_assets:
        return pd.Series(dtype=float)

    weights = pd.Series(
        1.0 / len(selected_assets),
        index=selected_assets,
        dtype=float,
    )

    weights = weights.clip(upper=max_asset_weight)

    for group_name, cap in group_caps.items():
        group_assets = [
            asset
            for asset in weights.index
            if asset_groups.get(asset, "other") == group_name
        ]

        if not group_assets:
            continue

        group_weight = float(weights.loc[group_assets].sum())

        if group_weight > cap:
            scale = cap / group_weight
            weights.loc[group_assets] = weights.loc[group_assets] * scale

    return weights


def _run_constrained_trend_confirmed_allocator(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    assets: list[str],
    universe_name: str,
    initial_capital: float,
    top_n: int,
    lookback_months: int,
    trend_sma_days: int,
    max_asset_weight: float,
    group_caps: dict[str, float],
    asset_groups: dict[str, str],
    cash_returns: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    close_panel = _build_close_panel(ticker_outputs, assets)
    daily_returns = close_panel.pct_change().fillna(0.0)

    trend_sma = close_panel.rolling(trend_sma_days).mean()
    above_trend = close_panel > trend_sma

    monthly_last_dates = (
        close_panel.resample("ME").last().dropna(how="all").index
    )
    monthly_close = close_panel.loc[close_panel.index.isin(monthly_last_dates)]

    trailing_returns = monthly_close.pct_change(lookback_months)

    target_weights = pd.DataFrame(
        index=close_panel.index,
        columns=close_panel.columns,
        dtype=float,
    )

    for signal_date in trailing_returns.index:
        if signal_date not in close_panel.index:
            continue

        signal_index = close_panel.index.get_loc(signal_date)
        execution_index = signal_index + 1

        if execution_index >= len(close_panel.index):
            continue

        execution_date = close_panel.index[execution_index]
        momentum_row = trailing_returns.loc[signal_date].dropna()
        trend_row = above_trend.loc[signal_date]

        eligible = [
            asset
            for asset, momentum in momentum_row.items()
            if momentum > 0 and bool(trend_row.get(asset, False))
        ]

        ranked_assets = (
            momentum_row.loc[eligible]
            .sort_values(ascending=False)
            .head(top_n)
            .index.tolist()
        )

        weights = _apply_constraints(
            selected_assets=ranked_assets,
            max_asset_weight=max_asset_weight,
            group_caps=group_caps,
            asset_groups=asset_groups,
        )

        target_weights.loc[execution_date, :] = 0.0

        for asset, weight in weights.items():
            target_weights.loc[execution_date, asset] = weight

    target_weights = target_weights.ffill().fillna(0.0)
    risky_weight = target_weights.sum(axis=1).clip(lower=0.0, upper=1.0)
    cash_position = 1.0 - risky_weight

    portfolio_return = (target_weights.shift(1).fillna(0.0) * daily_returns).sum(axis=1)

    if cash_returns is not None:
        aligned_cash = cash_returns.copy()
        aligned_cash.index = pd.to_datetime(aligned_cash.index)
        aligned_cash = aligned_cash.reindex(close_panel.index).ffill().fillna(0.0)
        portfolio_return = portfolio_return + cash_position.shift(1).fillna(1.0) * aligned_cash

    turnover = target_weights.diff().abs().sum(axis=1)
    turnover.iloc[0] = target_weights.iloc[0].abs().sum()

    equity = initial_capital * (1.0 + portfolio_return).cumprod()

    result = pd.DataFrame(
        {
            "date": close_panel.index,
            "adj_close": equity.values,
            "strategy_return": portfolio_return.values,
            "equity": equity.values,
            "position": risky_weight.values,
            "cash_position": cash_position.values,
            "turnover": turnover.values,
        }
    )

    result["strategy_name"] = (
        f"{universe_name} Constrained Trend-Confirmed Relative Momentum Allocator"
    )

    allocation_rows = []

    for asset in close_panel.columns:
        weights = target_weights[asset]
        allocation_rows.append(
            {
                "universe": universe_name,
                "asset": asset,
                "avg_weight_pct": weights.mean() * 100.0,
                "max_weight_pct": weights.max() * 100.0,
                "days_held": int((weights > 0).sum()),
                "pct_days_held": (weights > 0).mean() * 100.0,
                "final_weight_pct": weights.iloc[-1] * 100.0,
            }
        )

    allocation_summary = pd.DataFrame(allocation_rows)

    numeric_columns = allocation_summary.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        allocation_summary[column] = allocation_summary[column].round(3)

    return result.reset_index(drop=True), allocation_summary


def _slice_and_rebase_result(
    result: pd.DataFrame,
    start_date: str | pd.Timestamp | None,
    end_date: str | pd.Timestamp | None,
    initial_capital: float,
) -> pd.DataFrame:
    df = result.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    if start_date is not None:
        df = df[df["date"] >= pd.to_datetime(start_date)]

    if end_date is not None:
        df = df[df["date"] <= pd.to_datetime(end_date)]

    df = df.reset_index(drop=True)

    if len(df) < 2:
        return pd.DataFrame()

    df.loc[df.index[0], "strategy_return"] = 0.0
    df["equity"] = initial_capital * (1.0 + df["strategy_return"]).cumprod()
    df["adj_close"] = df["equity"]

    return df


def _create_holdout_rows(
    results: dict[str, pd.DataFrame],
    initial_capital: float,
    reference_end_date: str,
    holdout_start_date: str,
) -> pd.DataFrame:
    rows: list[dict] = []

    periods = [
        {
            "period": "full",
            "start_date": None,
            "end_date": None,
        },
        {
            "period": "reference",
            "start_date": None,
            "end_date": reference_end_date,
        },
        {
            "period": "holdout",
            "start_date": holdout_start_date,
            "end_date": None,
        },
    ]

    for period in periods:
        for strategy_name, result in results.items():
            sliced = _slice_and_rebase_result(
                result=result,
                start_date=period["start_date"],
                end_date=period["end_date"],
                initial_capital=initial_capital,
            )

            if sliced.empty:
                continue

            metrics = calculate_metrics(sliced, strategy_name)

            rows.append(
                {
                    "period": period["period"],
                    "strategy": strategy_name,
                    "start_date": metrics["start_date"],
                    "end_date": metrics["end_date"],
                    "end_value": metrics["end_value"],
                    "cagr_pct": metrics["cagr_pct"],
                    "calmar": metrics["calmar"],
                    "volatility_pct": metrics["volatility_pct"],
                    "sharpe": metrics["sharpe"],
                    "sortino": metrics["sortino"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "worst_month_pct": metrics["worst_month_pct"],
                    "exposure_time_pct": metrics["exposure_time_pct"],
                    "trade_count": metrics["trade_count"],
                }
            )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output.reset_index(drop=True)


def _get_single_metric_row(
    metrics: pd.DataFrame,
    period: str,
    universe_name: str,
    strategy_keyword: str,
) -> pd.Series | None:
    rows = metrics[
        (metrics["period"] == period)
        & metrics["strategy"].str.contains(universe_name, regex=False)
        & metrics["strategy"].str.contains(strategy_keyword, regex=False)
    ]

    if rows.empty:
        return None

    return rows.iloc[0]


def _metric_delta(
    expanded_row: pd.Series | None,
    baseline_row: pd.Series | None,
    column: str,
) -> float | None:
    if expanded_row is None or baseline_row is None:
        return None

    if column not in expanded_row.index or column not in baseline_row.index:
        return None

    try:
        return round(float(expanded_row[column]) - float(baseline_row[column]), 3)
    except (TypeError, ValueError):
        return None


def _safe_metric(row: pd.Series | None, column: str) -> float | str:
    if row is None or column not in row.index:
        return ""

    value = row[column]

    if pd.isna(value):
        return ""

    if isinstance(value, int | float):
        return round(float(value), 3)

    return value


def _create_decision_rows(
    metrics: pd.DataFrame,
    allocation_summary: pd.DataFrame,
    baseline_universe_name: str,
    expanded_universe_name: str,
) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()

    base_allocator_full = _get_single_metric_row(
        metrics=metrics,
        period="full",
        universe_name=baseline_universe_name,
        strategy_keyword="Allocator",
    )
    expanded_allocator_full = _get_single_metric_row(
        metrics=metrics,
        period="full",
        universe_name=expanded_universe_name,
        strategy_keyword="Allocator",
    )

    base_overlay_full = _get_single_metric_row(
        metrics=metrics,
        period="full",
        universe_name=baseline_universe_name,
        strategy_keyword="3D Overlay",
    )
    expanded_overlay_full = _get_single_metric_row(
        metrics=metrics,
        period="full",
        universe_name=expanded_universe_name,
        strategy_keyword="3D Overlay",
    )

    base_overlay_reference = _get_single_metric_row(
        metrics=metrics,
        period="reference",
        universe_name=baseline_universe_name,
        strategy_keyword="3D Overlay",
    )
    expanded_overlay_reference = _get_single_metric_row(
        metrics=metrics,
        period="reference",
        universe_name=expanded_universe_name,
        strategy_keyword="3D Overlay",
    )

    base_overlay_holdout = _get_single_metric_row(
        metrics=metrics,
        period="holdout",
        universe_name=baseline_universe_name,
        strategy_keyword="3D Overlay",
    )
    expanded_overlay_holdout = _get_single_metric_row(
        metrics=metrics,
        period="holdout",
        universe_name=expanded_universe_name,
        strategy_keyword="3D Overlay",
    )

    expanded_allocations = allocation_summary[
        allocation_summary["universe"] == expanded_universe_name
    ].copy()

    added_asset = "USO"
    added_asset_row = expanded_allocations[expanded_allocations["asset"] == added_asset]

    if added_asset_row.empty:
        added_asset_avg_weight = 0.0
        added_asset_days_held = 0
        added_asset_pct_days_held = 0.0
        added_asset_final_weight = 0.0
    else:
        added_asset_metrics = added_asset_row.iloc[0]
        added_asset_avg_weight = float(added_asset_metrics["avg_weight_pct"])
        added_asset_days_held = int(added_asset_metrics["days_held"])
        added_asset_pct_days_held = float(added_asset_metrics["pct_days_held"])
        added_asset_final_weight = float(added_asset_metrics["final_weight_pct"])

    allocator_cagr_delta = _metric_delta(
        expanded_allocator_full,
        base_allocator_full,
        "cagr_pct",
    )
    allocator_calmar_delta = _metric_delta(
        expanded_allocator_full,
        base_allocator_full,
        "calmar",
    )
    allocator_drawdown_delta = _metric_delta(
        expanded_allocator_full,
        base_allocator_full,
        "max_drawdown_pct",
    )

    overlay_full_cagr_delta = _metric_delta(
        expanded_overlay_full,
        base_overlay_full,
        "cagr_pct",
    )
    overlay_full_calmar_delta = _metric_delta(
        expanded_overlay_full,
        base_overlay_full,
        "calmar",
    )
    overlay_full_drawdown_delta = _metric_delta(
        expanded_overlay_full,
        base_overlay_full,
        "max_drawdown_pct",
    )

    overlay_reference_cagr_delta = _metric_delta(
        expanded_overlay_reference,
        base_overlay_reference,
        "cagr_pct",
    )
    overlay_reference_calmar_delta = _metric_delta(
        expanded_overlay_reference,
        base_overlay_reference,
        "calmar",
    )

    overlay_holdout_cagr_delta = _metric_delta(
        expanded_overlay_holdout,
        base_overlay_holdout,
        "cagr_pct",
    )
    overlay_holdout_calmar_delta = _metric_delta(
        expanded_overlay_holdout,
        base_overlay_holdout,
        "calmar",
    )
    overlay_holdout_volatility_delta = _metric_delta(
        expanded_overlay_holdout,
        base_overlay_holdout,
        "volatility_pct",
    )

    allocator_pass = (
        allocator_cagr_delta is not None
        and allocator_calmar_delta is not None
        and allocator_drawdown_delta is not None
        and allocator_cagr_delta > 0.20
        and allocator_calmar_delta > 0.03
        and allocator_drawdown_delta >= 0
    )

    overlay_full_pass = (
        overlay_full_cagr_delta is not None
        and overlay_full_calmar_delta is not None
        and overlay_full_cagr_delta > 0.20
        and overlay_full_calmar_delta > 0.02
    )

    overlay_holdout_material_pass = (
        overlay_holdout_cagr_delta is not None
        and overlay_holdout_calmar_delta is not None
        and overlay_holdout_cagr_delta > 0.20
        and overlay_holdout_calmar_delta > 0.02
    )

    added_asset_used = added_asset_avg_weight >= 1.0 and added_asset_days_held > 100

    if allocator_pass and overlay_full_pass and overlay_holdout_material_pass:
        final_classification = "Validated expansion candidate"
        final_verdict = (
            "Oil improved allocator and overlay results across full-period and holdout. "
            "Promote to deeper validation."
        )
    elif allocator_pass and overlay_full_pass and not overlay_holdout_material_pass:
        final_classification = "Promising but not validated"
        final_verdict = (
            "Oil improved allocator and full-period overlay results, but holdout overlay "
            "improvement was too small to call it a validated new champion."
        )
    elif added_asset_used and allocator_pass:
        final_classification = "Allocator improvement only"
        final_verdict = (
            "Oil improved the standalone allocator, but did not clearly improve the final "
            "overlay system enough to promote it."
        )
    elif not added_asset_used:
        final_classification = "Added asset ignored"
        final_verdict = (
            "Oil received too little allocation to matter under the current rules."
        )
    else:
        final_classification = "Expansion rejected"
        final_verdict = (
            "Oil did not improve the system enough to justify inclusion."
        )

    return pd.DataFrame(
        [
            {
                "comparison": f"{expanded_universe_name} vs {baseline_universe_name}",
                "added_asset": added_asset,
                "added_asset_avg_weight_pct": round(added_asset_avg_weight, 3),
                "added_asset_days_held": added_asset_days_held,
                "added_asset_pct_days_held": round(added_asset_pct_days_held, 3),
                "added_asset_final_weight_pct": round(added_asset_final_weight, 3),

                "baseline_allocator_cagr_pct": _safe_metric(
                    base_allocator_full,
                    "cagr_pct",
                ),
                "expanded_allocator_cagr_pct": _safe_metric(
                    expanded_allocator_full,
                    "cagr_pct",
                ),
                "allocator_cagr_delta_pct_points": allocator_cagr_delta,

                "baseline_allocator_calmar": _safe_metric(
                    base_allocator_full,
                    "calmar",
                ),
                "expanded_allocator_calmar": _safe_metric(
                    expanded_allocator_full,
                    "calmar",
                ),
                "allocator_calmar_delta": allocator_calmar_delta,

                "baseline_allocator_max_drawdown_pct": _safe_metric(
                    base_allocator_full,
                    "max_drawdown_pct",
                ),
                "expanded_allocator_max_drawdown_pct": _safe_metric(
                    expanded_allocator_full,
                    "max_drawdown_pct",
                ),
                "allocator_drawdown_delta_pct_points": allocator_drawdown_delta,

                "baseline_overlay_full_cagr_pct": _safe_metric(
                    base_overlay_full,
                    "cagr_pct",
                ),
                "expanded_overlay_full_cagr_pct": _safe_metric(
                    expanded_overlay_full,
                    "cagr_pct",
                ),
                "overlay_full_cagr_delta_pct_points": overlay_full_cagr_delta,

                "baseline_overlay_full_calmar": _safe_metric(
                    base_overlay_full,
                    "calmar",
                ),
                "expanded_overlay_full_calmar": _safe_metric(
                    expanded_overlay_full,
                    "calmar",
                ),
                "overlay_full_calmar_delta": overlay_full_calmar_delta,

                "baseline_overlay_full_max_drawdown_pct": _safe_metric(
                    base_overlay_full,
                    "max_drawdown_pct",
                ),
                "expanded_overlay_full_max_drawdown_pct": _safe_metric(
                    expanded_overlay_full,
                    "max_drawdown_pct",
                ),
                "overlay_full_drawdown_delta_pct_points": overlay_full_drawdown_delta,

                "baseline_overlay_reference_cagr_pct": _safe_metric(
                    base_overlay_reference,
                    "cagr_pct",
                ),
                "expanded_overlay_reference_cagr_pct": _safe_metric(
                    expanded_overlay_reference,
                    "cagr_pct",
                ),
                "overlay_reference_cagr_delta_pct_points": (
                    overlay_reference_cagr_delta
                ),

                "baseline_overlay_reference_calmar": _safe_metric(
                    base_overlay_reference,
                    "calmar",
                ),
                "expanded_overlay_reference_calmar": _safe_metric(
                    expanded_overlay_reference,
                    "calmar",
                ),
                "overlay_reference_calmar_delta": overlay_reference_calmar_delta,

                "baseline_overlay_holdout_cagr_pct": _safe_metric(
                    base_overlay_holdout,
                    "cagr_pct",
                ),
                "expanded_overlay_holdout_cagr_pct": _safe_metric(
                    expanded_overlay_holdout,
                    "cagr_pct",
                ),
                "overlay_holdout_cagr_delta_pct_points": overlay_holdout_cagr_delta,

                "baseline_overlay_holdout_calmar": _safe_metric(
                    base_overlay_holdout,
                    "calmar",
                ),
                "expanded_overlay_holdout_calmar": _safe_metric(
                    expanded_overlay_holdout,
                    "calmar",
                ),
                "overlay_holdout_calmar_delta": overlay_holdout_calmar_delta,

                "overlay_holdout_volatility_delta_pct_points": (
                    overlay_holdout_volatility_delta
                ),

                "allocator_pass": allocator_pass,
                "overlay_full_pass": overlay_full_pass,
                "overlay_holdout_material_pass": overlay_holdout_material_pass,
                "added_asset_used": added_asset_used,
                "final_classification": final_classification,
                "final_verdict": final_verdict,
            }
        ]
    )


def create_asset_expansion_diagnostic(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    diagnostic_config = config.get("asset_expansion_diagnostic", {})

    if not diagnostic_config.get("enabled", False):
        return {
            "metrics": pd.DataFrame(),
            "rolling_summary": pd.DataFrame(),
            "allocation_summary": pd.DataFrame(),
            "decision": pd.DataFrame(),
        }

    initial_capital = float(config["initial_capital"])
    baseline_universe_name = str(diagnostic_config.get("baseline_universe_name", "Base"))
    expanded_universe_name = str(
        diagnostic_config.get("expanded_universe_name", "Base + Oil")
    )
    baseline_assets = [
        str(asset).upper() for asset in diagnostic_config["baseline_assets"]
    ]
    expanded_assets = [
        str(asset).upper() for asset in diagnostic_config["expanded_assets"]
    ]

    top_n = int(diagnostic_config.get("top_n", 3))
    lookback_months = int(diagnostic_config.get("lookback_months", 12))
    trend_sma_days = int(diagnostic_config.get("trend_sma_days", 200))
    confirmation_days = int(diagnostic_config.get("confirmation_days", 3))
    max_asset_weight = float(diagnostic_config.get("max_asset_weight", 1.0 / top_n))
    group_caps = {
        str(group): float(cap)
        for group, cap in diagnostic_config.get("group_caps", {}).items()
    }
    asset_groups = {
        str(asset).upper(): str(group)
        for asset, group in diagnostic_config.get("asset_groups", {}).items()
    }

    reference_end_date = str(
        config.get("regime_switch_overlay_holdout_validation", {}).get(
            "reference_end_date",
            "2015-12-31",
        )
    )
    holdout_start_date = str(
        config.get("regime_switch_overlay_holdout_validation", {}).get(
            "holdout_start_date",
            "2016-01-01",
        )
    )

    spy_buy_hold = _get_strategy_result(ticker_outputs, "SPY", "Buy and Hold")

    base_panel = _build_close_panel(ticker_outputs, baseline_assets)
    expanded_panel = _build_close_panel(ticker_outputs, expanded_assets)
    common_dates = sorted(set(base_panel.index).intersection(expanded_panel.index))

    if not common_dates:
        raise ValueError("No common dates between baseline and expanded universes")

    cash_returns = ticker_outputs["SPY"].get("cash_returns")

    baseline_allocator, baseline_allocation = _run_constrained_trend_confirmed_allocator(
        ticker_outputs=ticker_outputs,
        assets=baseline_assets,
        universe_name=baseline_universe_name,
        initial_capital=initial_capital,
        top_n=top_n,
        lookback_months=lookback_months,
        trend_sma_days=trend_sma_days,
        max_asset_weight=max_asset_weight,
        group_caps=group_caps,
        asset_groups=asset_groups,
        cash_returns=cash_returns,
    )
    expanded_allocator, expanded_allocation = _run_constrained_trend_confirmed_allocator(
        ticker_outputs=ticker_outputs,
        assets=expanded_assets,
        universe_name=expanded_universe_name,
        initial_capital=initial_capital,
        top_n=top_n,
        lookback_months=lookback_months,
        trend_sma_days=trend_sma_days,
        max_asset_weight=max_asset_weight,
        group_caps=group_caps,
        asset_groups=asset_groups,
        cash_returns=cash_returns,
    )

    baseline_allocator = baseline_allocator[
        pd.to_datetime(baseline_allocator["date"]).isin(common_dates)
    ].copy()
    expanded_allocator = expanded_allocator[
        pd.to_datetime(expanded_allocator["date"]).isin(common_dates)
    ].copy()

    offensive_spy = rebase_strategy_result_to_dates(
        result=spy_buy_hold,
        dates=common_dates,
        initial_capital=initial_capital,
    )

    baseline_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_spy,
        defensive_result=baseline_allocator,
        initial_capital=initial_capital,
        trend_sma_days=int(
            config.get("regime_switch_overlay", {}).get("trend_sma_days", 200)
        ),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        confirmation_days=confirmation_days,
    )
    expanded_overlay = run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_spy,
        defensive_result=expanded_allocator,
        initial_capital=initial_capital,
        trend_sma_days=int(
            config.get("regime_switch_overlay", {}).get("trend_sma_days", 200)
        ),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
        confirmation_days=confirmation_days,
    )

    results = {
        f"{baseline_universe_name} Allocator": baseline_allocator,
        f"{expanded_universe_name} Allocator": expanded_allocator,
        f"{baseline_universe_name} 3D Overlay": baseline_overlay,
        f"{expanded_universe_name} 3D Overlay": expanded_overlay,
        "SPY Buy and Hold": offensive_spy,
    }

    metrics = _create_holdout_rows(
        results=results,
        initial_capital=initial_capital,
        reference_end_date=reference_end_date,
        holdout_start_date=holdout_start_date,
    )

    rolling = calculate_rolling_window_metrics(results)
    rolling_summary = create_rolling_summary(rolling)

    allocation_summary = pd.concat(
        [baseline_allocation, expanded_allocation],
        ignore_index=True,
    )

    decision = _create_decision_rows(
        metrics=metrics,
        allocation_summary=allocation_summary,
        baseline_universe_name=baseline_universe_name,
        expanded_universe_name=expanded_universe_name,
    )

    return {
        "metrics": metrics,
        "rolling_summary": rolling_summary,
        "allocation_summary": allocation_summary,
        "decision": decision,
    }


def write_asset_expansion_diagnostic_markdown(
    outputs: dict[str, pd.DataFrame],
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metrics = outputs.get("metrics", pd.DataFrame())
    rolling_summary = outputs.get("rolling_summary", pd.DataFrame())
    allocation_summary = outputs.get("allocation_summary", pd.DataFrame())
    decision = outputs.get("decision", pd.DataFrame())

    content = f"""# Asset Expansion Diagnostic

This report tests controlled asset expansion.

Current branch:

> Base universe vs Base + Oil proxy (`USO`)

## Decision

{decision.to_markdown(index=False) if not decision.empty else "No decision available."}

## Metrics

{metrics.to_markdown(index=False) if not metrics.empty else "No metrics available."}

## Rolling Summary

{rolling_summary.to_markdown(index=False) if not rolling_summary.empty else "No rolling summary available."}

## Allocation Summary

{allocation_summary.to_markdown(index=False) if not allocation_summary.empty else "No allocation summary available."}

## Interpretation Notes

- This is not a broad optimiser.
- This only tests whether adding USO improves the existing constrained trend-confirmed allocator and 3D overlay.
- If USO receives little weight, the market itself is telling us oil is not useful under this rule.
- If USO improves only one metric while damaging Calmar or drawdown, reject the expansion.
- ETH is deliberately excluded from this branch because it has a later start date and needs quarantine.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_asset_expansion_diagnostic(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_asset_expansion_diagnostic(
        ticker_outputs=ticker_outputs,
        config=config,
    )

    metrics = outputs["metrics"]
    rolling_summary = outputs["rolling_summary"]
    allocation_summary = outputs["allocation_summary"]
    decision = outputs["decision"]

    if metrics.empty:
        return outputs

    metrics_path = reports_dir / "asset_expansion_diagnostic_metrics.csv"
    rolling_summary_path = reports_dir / "asset_expansion_diagnostic_rolling_summary.csv"
    allocation_summary_path = (
        reports_dir / "asset_expansion_diagnostic_allocation_summary.csv"
    )
    decision_path = reports_dir / "asset_expansion_diagnostic_decision.csv"
    markdown_path = reports_dir / "asset_expansion_diagnostic.md"

    metrics.to_csv(metrics_path, index=False)
    rolling_summary.to_csv(rolling_summary_path, index=False)
    allocation_summary.to_csv(allocation_summary_path, index=False)
    decision.to_csv(decision_path, index=False)

    write_asset_expansion_diagnostic_markdown(
        outputs=outputs,
        output_path=markdown_path,
    )

    print("\nAsset expansion diagnostic metrics:")
    print(metrics.to_string(index=False))

    print("\nAsset expansion diagnostic decision:")
    print(decision.to_string(index=False))

    print(f"\nSaved asset expansion diagnostic metrics to: {metrics_path}")
    print(f"Saved asset expansion diagnostic rolling summary to: {rolling_summary_path}")
    print(f"Saved asset expansion diagnostic allocation summary to: {allocation_summary_path}")
    print(f"Saved asset expansion diagnostic decision to: {decision_path}")
    print(f"Saved asset expansion diagnostic markdown to: {markdown_path}")

    return outputs