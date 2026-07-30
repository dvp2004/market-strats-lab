"""MI-2 technical-feature, forecast, and portfolio baseline pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import floor, sqrt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yaml

RISK_FREE_INSTRUMENT_ID = "mi1_etf_bil"
SPY_INSTRUMENT_ID = "mi1_etf_spy"
RISK_ASSET_EXCLUDE = {RISK_FREE_INSTRUMENT_ID}
FEATURE_COLUMNS = [
    "raw_return_21",
    "raw_return_63",
    "raw_return_126",
    "raw_momentum_252_minus_21",
    "realized_volatility_20",
    "max_drawdown_60",
    "close_to_200dma",
    "avg_dollar_volume_20",
]
RIDGE_ALPHA = 1.0
ONE_WAY_COST = 0.001


@dataclass(frozen=True)
class Mi2RunResult:
    mi1_provenance: dict[str, Any]
    research_start_date: str
    validation_start_date: str
    validation_end_date: str
    holdout_start_date: str
    holdout_end_date: str
    feature_row_count: int
    target_row_count: int
    strategy_count: int
    model_count: int
    output_paths: dict[str, str]
    scoreboard_summary: list[dict[str, Any]]


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return value


def load_registry_rules(path: Path) -> dict[str, Any]:
    return read_yaml(path)


def us_equity_sessions(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    calendar = mcal.get_calendar("XNYS")
    schedule = calendar.schedule(
        start_date=start.date().isoformat(), end_date=end.date().isoformat()
    )
    return [pd.Timestamp(index_value).normalize() for index_value in schedule.index]


def load_mi1_inputs(mi1_data_root: Path) -> dict[str, pd.DataFrame]:
    required = {
        "market_eod_bar": mi1_data_root / "normalized" / "market_eod_bar.parquet",
        "corporate_action_event": mi1_data_root / "normalized" / "corporate_action_event.parquet",
        "coverage_audit": mi1_data_root / "normalized" / "coverage_audit.parquet",
        "decision_panel_availability_audit": mi1_data_root
        / "normalized"
        / "decision_panel_availability_audit.parquet",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required MI-1 outputs: " + ", ".join(missing))
    return {name: pd.read_parquet(path) for name, path in required.items()}


def _normalize_dates(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column]).dt.normalize()
    return frame


def validate_mi1_contract(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = _normalize_dates(inputs["market_eod_bar"], ["session_date"])
    availability = inputs["decision_panel_availability_audit"].copy()
    coverage = inputs["coverage_audit"].copy()

    required_bar_columns = {
        "instrument_id",
        "session_date",
        "close_raw",
        "high_raw",
        "low_raw",
        "volume_raw",
        "vendor_adjusted_close",
        "available_at_utc",
        "availability_evidence_level",
    }
    missing_columns = required_bar_columns - set(bars.columns)
    if missing_columns:
        raise ValueError(f"MI-1 market_eod_bar is outside contract: {sorted(missing_columns)}")

    if "eligible" not in availability.columns or "dataset_row_id" not in availability.columns:
        raise ValueError("MI-1 availability audit is outside contract")
    if availability["eligible"].isna().any():
        raise ValueError("MI-1 availability audit contains null eligibility values")
    if (
        (availability["availability_evidence_level"] == "unverified") & availability["eligible"]
    ).any():
        raise ValueError("Unverified MI-1 row is marked decision-panel eligible")

    eligible_ids = set(availability.loc[availability["eligible"], "dataset_row_id"].astype(str))
    bars["dataset_row_id"] = (
        bars["instrument_id"].astype(str) + "|" + bars["session_date"].dt.date.astype(str)
    )
    eligible_bars = bars[bars["dataset_row_id"].isin(eligible_ids)].copy()
    if eligible_bars.empty:
        raise ValueError("No decision-panel eligible MI-1 bars available")
    if (eligible_bars["availability_evidence_level"] == "unverified").any():
        raise ValueError("Unverified MI-1 bar passed availability filtering")

    if "start_date_eligible" not in coverage.columns or not coverage["start_date_eligible"].all():
        raise ValueError("Coverage audit does not show all instruments as start-date eligible")
    return eligible_bars


def derive_common_research_start(
    eligible_bars: pd.DataFrame,
    instrument_ids: list[str],
    minimum_sessions: int,
) -> pd.Timestamp:
    by_instrument = {
        instrument_id: set(
            eligible_bars.loc[eligible_bars["instrument_id"] == instrument_id, "session_date"]
        )
        for instrument_id in instrument_ids
    }
    start = eligible_bars["session_date"].min()
    end = eligible_bars["session_date"].max()
    sessions = us_equity_sessions(start, end)
    for index, session in enumerate(sessions):
        start_index = index - minimum_sessions + 1
        if start_index < 0:
            continue
        window = sessions[start_index : index + 1]
        if all(
            all(window_session in by_instrument[item] for window_session in window)
            for item in instrument_ids
        ):
            return session
    raise ValueError(f"Unable to derive common {minimum_sessions}-session research start date")


def build_feature_panel(
    eligible_bars: pd.DataFrame,
    corporate_actions: pd.DataFrame,
    research_start: pd.Timestamp,
) -> pd.DataFrame:
    bars = eligible_bars.sort_values(["instrument_id", "session_date"]).copy()
    bars["raw_dollar_volume"] = bars["close_raw"] * bars["volume_raw"]
    groups = bars.groupby("instrument_id", group_keys=False)
    bars["raw_return_21"] = groups["close_raw"].pct_change(21)
    bars["raw_return_63"] = groups["close_raw"].pct_change(63)
    bars["raw_return_126"] = groups["close_raw"].pct_change(126)
    bars["raw_momentum_252_minus_21"] = (
        groups["close_raw"].shift(21) / groups["close_raw"].shift(252) - 1.0
    )
    bars["realized_volatility_20"] = groups["close_raw"].pct_change().groupby(
        bars["instrument_id"]
    ).rolling(20).std().reset_index(level=0, drop=True) * sqrt(252)
    rolling_max = groups["close_raw"].rolling(60).max().reset_index(level=0, drop=True)
    bars["max_drawdown_60"] = (
        (bars["close_raw"] / rolling_max - 1.0)
        .groupby(bars["instrument_id"])
        .rolling(60)
        .min()
        .reset_index(level=0, drop=True)
    )
    bars["close_to_200dma"] = (
        bars["close_raw"] / groups["close_raw"].rolling(200).mean().reset_index(level=0, drop=True)
        - 1.0
    )
    bars["avg_dollar_volume_20"] = (
        groups["raw_dollar_volume"].rolling(20).mean().reset_index(level=0, drop=True)
    )

    actions = _normalize_dates(corporate_actions, ["session_date"])
    split_dates = {
        instrument_id: set(group["session_date"])
        for instrument_id, group in actions[actions.get("action_type", "") == "split"].groupby(
            "instrument_id"
        )
    }
    split_blocked: list[bool] = []
    for row in bars.itertuples(index=False):
        dates = split_dates.get(row.instrument_id, set())
        blocked = any(
            row.session_date - pd.Timedelta(days=370) <= split <= row.session_date
            for split in dates
        )
        split_blocked.append(blocked)
    bars["feature_available"] = (
        bars["session_date"].ge(research_start)
        & bars[FEATURE_COLUMNS].notna().all(axis=1)
        & ~pd.Series(split_blocked, index=bars.index)
    )
    bars["feature_block_reason"] = ""
    bars.loc[bars["session_date"].lt(research_start), "feature_block_reason"] = (
        "before_common_research_start"
    )
    bars.loc[bars[FEATURE_COLUMNS].isna().any(axis=1), "feature_block_reason"] = (
        "insufficient_lookback"
    )
    bars.loc[split_blocked, "feature_block_reason"] = (
        "split_in_lookback_window_raw_prices_not_silently_adjusted"
    )
    bars["decision_timestamp_utc"] = bars["available_at_utc"]
    result_columns = [
        "instrument_id",
        "session_date",
        "decision_timestamp_utc",
        "availability_evidence_level",
        "feature_available",
        "feature_block_reason",
        *FEATURE_COLUMNS,
    ]
    return bars[result_columns].copy()


def build_target_panel(eligible_bars: pd.DataFrame) -> pd.DataFrame:
    bars = eligible_bars.sort_values(["instrument_id", "session_date"]).copy()
    groups = bars.groupby("instrument_id", group_keys=False)
    bars["future_total_return_20"] = (
        groups["vendor_adjusted_close"].shift(-20) / bars["vendor_adjusted_close"] - 1.0
    )
    bil = bars[bars["instrument_id"] == RISK_FREE_INSTRUMENT_ID][
        ["session_date", "future_total_return_20"]
    ].rename(columns={"future_total_return_20": "bil_future_total_return_20"})
    targets = bars.merge(bil, on="session_date", how="left")
    targets["target_value"] = (
        targets["future_total_return_20"] - targets["bil_future_total_return_20"]
    )
    targets["target_name"] = "20_trading_session_forward_total_return_excess_vs_BIL"
    targets["target_is_future_information"] = True
    targets["target_price_policy"] = "vendor_adjusted_close_retrospective_total_return_proxy"
    targets["target_available"] = targets["target_value"].notna()
    targets["target_block_reason"] = ""
    targets.loc[~targets["target_available"], "target_block_reason"] = "incomplete_future_horizon"
    return targets[
        [
            "instrument_id",
            "session_date",
            "target_name",
            "target_value",
            "target_is_future_information",
            "target_price_policy",
            "target_available",
            "target_block_reason",
        ]
    ].copy()


def walk_forward_boundaries(
    sessions: list[pd.Timestamp], registry: dict[str, Any]
) -> dict[str, Any]:
    wf = registry["walk_forward_and_holdout"]
    holdout_count = max(1, floor(len(sessions) * float(wf["untouched_holdout_fraction"])))
    holdout_start_index = len(sessions) - holdout_count
    validation_sessions = sessions[:holdout_start_index]
    initial_train_end = floor(len(validation_sessions) * float(wf["initial_training_fraction"]))
    test_block = int(wf.get("test_block_sessions") or wf["walk_forward_test_block_sessions"])
    purge = int(wf["purge_sessions"])
    embargo = int(wf["embargo_sessions"])
    blocks = []
    train_end = initial_train_end
    while train_end + purge < len(validation_sessions):
        test_start = train_end + purge
        test_end = min(test_start + test_block, len(validation_sessions))
        if test_start >= test_end:
            break
        blocks.append(
            {
                "train_end_index": train_end,
                "test_start_index": test_start,
                "test_end_index": test_end,
                "test_sessions": validation_sessions[test_start:test_end],
            }
        )
        train_end = test_end + embargo
    return {
        "validation_sessions": validation_sessions,
        "holdout_sessions": sessions[holdout_start_index:],
        "holdout_start_index": holdout_start_index,
        "blocks": blocks,
        "initial_train_end_index": initial_train_end,
        "purge_sessions": purge,
        "embargo_sessions": embargo,
        "test_block_sessions": test_block,
    }


def build_walk_forward_predictions(
    feature_panel: pd.DataFrame,
    target_panel: pd.DataFrame,
    registry: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    samples = feature_panel.merge(target_panel, on=["instrument_id", "session_date"], how="inner")
    samples = samples[samples["feature_available"] & samples["target_available"]].copy()
    samples = samples.sort_values(["session_date", "instrument_id"])
    sessions = list(pd.Index(samples["session_date"].unique()).sort_values())
    bounds = walk_forward_boundaries(sessions, registry)
    predictions: list[pd.DataFrame] = []

    def fit_predict(
        train_sessions: list[pd.Timestamp], test_sessions: list[pd.Timestamp], segment: str
    ) -> None:
        train = samples[samples["session_date"].isin(train_sessions)]
        test = samples[samples["session_date"].isin(test_sessions)]
        if train.empty or test.empty:
            return
        prediction = fit_ridge_predict(
            train[FEATURE_COLUMNS],
            train["target_value"],
            test[FEATURE_COLUMNS],
            alpha=RIDGE_ALPHA,
        )
        out = test[["instrument_id", "session_date", "target_value"]].copy()
        out["prediction"] = prediction
        out["model_name"] = "ridge_fixed_alpha_1_0"
        out["evaluation_segment"] = segment
        out["zero_prediction"] = 0.0
        out["persistence_prediction"] = test["raw_return_21"].to_numpy()
        predictions.append(out)

    validation_sessions = bounds["validation_sessions"]
    for block in bounds["blocks"]:
        fit_predict(
            validation_sessions[: block["train_end_index"]],
            block["test_sessions"],
            "walk_forward_validation",
        )
    holdout_train_end = max(0, bounds["holdout_start_index"] - bounds["purge_sessions"])
    fit_predict(sessions[:holdout_train_end], bounds["holdout_sessions"], "untouched_holdout")
    if not predictions:
        return pd.DataFrame(), bounds
    return pd.concat(predictions, ignore_index=True), bounds


def fit_ridge_predict(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    test_x: pd.DataFrame,
    *,
    alpha: float,
) -> np.ndarray:
    """Fit train-only standardization and fixed-alpha Ridge, then predict test rows."""

    x = train_x.to_numpy(dtype=float)
    y = train_y.to_numpy(dtype=float)
    test = test_x.to_numpy(dtype=float)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0.0] = 1.0
    x_scaled = (x - mean) / scale
    test_scaled = (test - mean) / scale
    design = np.column_stack([np.ones(len(x_scaled)), x_scaled])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coefficients = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y
    return np.column_stack([np.ones(len(test_scaled)), test_scaled]) @ coefficients


def final_prior_month_sessions(
    sessions: list[pd.Timestamp],
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    frame = pd.DataFrame({"session_date": sessions})
    frame["month"] = frame["session_date"].dt.to_period("M")
    month_ends = frame.groupby("month")["session_date"].max().tolist()
    pairs = []
    session_index = {session: index for index, session in enumerate(sessions)}
    for signal_session in month_ends[:-1]:
        next_index = session_index[signal_session] + 1
        pairs.append((signal_session, sessions[next_index]))
    return pairs


def top_quartile(items: pd.DataFrame, score_column: str) -> pd.DataFrame:
    ranked = items.sort_values([score_column, "instrument_id"], ascending=[False, True])
    count = max(1, floor(len(ranked) / 4))
    return ranked.head(count)


def capped_inverse_vol_weights(selected: pd.DataFrame, cap: float = 0.35) -> dict[str, float]:
    if selected.empty:
        return {}
    inv = 1.0 / selected["realized_volatility_20"].clip(lower=1e-8)
    weights = dict(zip(selected["instrument_id"], (inv / inv.sum()).to_numpy(), strict=True))
    capped: dict[str, float] = {}
    remaining = 1.0
    uncapped = set(weights)
    while uncapped:
        total = sum(weights[item] for item in uncapped)
        changed = False
        for item in list(uncapped):
            proposed = remaining * weights[item] / total
            if proposed > cap:
                capped[item] = cap
                remaining -= cap
                uncapped.remove(item)
                changed = True
        if not changed:
            for item in uncapped:
                capped[item] = remaining * weights[item] / total
            break
    return capped


def _weights_for_strategy(strategy: str, signal_rows: pd.DataFrame) -> dict[str, float]:
    risk = signal_rows[
        signal_rows["instrument_id"].ne(RISK_FREE_INSTRUMENT_ID) & signal_rows["feature_available"]
    ].copy()
    if strategy == "SPY_buy_and_hold_total_return":
        return {SPY_INSTRUMENT_ID: 1.0}
    if strategy == "BIL_cash_proxy_total_return":
        return {RISK_FREE_INSTRUMENT_ID: 1.0}
    if strategy == "equal_weight_eligible_universe_monthly_rebalance":
        return (
            dict.fromkeys(sorted(risk["instrument_id"]), 1.0 / len(risk))
            if not risk.empty
            else {RISK_FREE_INSTRUMENT_ID: 1.0}
        )
    if strategy == "10_month_absolute_trend_equal_weight":
        selected = risk[risk["close_to_200dma"] > 0]
        return (
            dict.fromkeys(sorted(selected["instrument_id"]), 1.0 / len(selected))
            if not selected.empty
            else {RISK_FREE_INSTRUMENT_ID: 1.0}
        )
    if strategy == "12_1_cross_sectional_momentum_top_quartile":
        selected = top_quartile(risk, "raw_momentum_252_minus_21")
        return (
            dict.fromkeys(selected["instrument_id"], 1.0 / len(selected))
            if not selected.empty
            else {RISK_FREE_INSTRUMENT_ID: 1.0}
        )
    if strategy == "volatility_targeted_trend_baseline_10_percent":
        selected = risk[risk["close_to_200dma"] > 0]
        raw_weights = capped_inverse_vol_weights(selected, cap=1.0)
        portfolio_vol = sum(
            raw_weights[row.instrument_id] * row.realized_volatility_20
            for row in selected.itertuples(index=False)
            if row.instrument_id in raw_weights
        )
        scale = min(1.0, 0.10 / portfolio_vol) if portfolio_vol > 0 else 0.0
        weights = {item: weight * scale for item, weight in raw_weights.items()}
        weights[RISK_FREE_INSTRUMENT_ID] = max(0.0, 1.0 - sum(weights.values()))
        return weights
    if strategy == "technical_composite_top_quartile_inverse_vol":
        selected = top_quartile(risk[risk["close_to_200dma"] > 0], "raw_momentum_252_minus_21")
        weights = capped_inverse_vol_weights(selected, cap=0.35)
        weights[RISK_FREE_INSTRUMENT_ID] = max(0.0, 1.0 - sum(weights.values()))
        return weights
    raise ValueError(f"Unknown strategy: {strategy}")


def simulate_strategies(
    eligible_bars: pd.DataFrame,
    feature_panel: pd.DataFrame,
    segment_sessions: dict[str, list[pd.Timestamp]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategies = [
        "SPY_buy_and_hold_total_return",
        "BIL_cash_proxy_total_return",
        "equal_weight_eligible_universe_monthly_rebalance",
        "10_month_absolute_trend_equal_weight",
        "12_1_cross_sectional_momentum_top_quartile",
        "volatility_targeted_trend_baseline_10_percent",
        "technical_composite_top_quartile_inverse_vol",
    ]
    prices = eligible_bars.pivot(
        index="session_date", columns="instrument_id", values="vendor_adjusted_close"
    )
    returns = prices.pct_change().fillna(0.0)
    all_sessions = list(prices.index.sort_values())
    features_by_date = {date: group for date, group in feature_panel.groupby("session_date")}
    return_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    for segment, sessions in segment_sessions.items():
        session_set = set(sessions)
        rebalance_pairs = [
            pair for pair in final_prior_month_sessions(all_sessions) if pair[1] in session_set
        ]
        for strategy in strategies:
            weights = {RISK_FREE_INSTRUMENT_ID: 1.0}
            rebalance_map: dict[pd.Timestamp, tuple[pd.Timestamp, dict[str, float], float]] = {}
            for signal_session, trade_session in rebalance_pairs:
                new_weights = _weights_for_strategy(
                    strategy,
                    features_by_date.get(
                        signal_session, pd.DataFrame(columns=feature_panel.columns)
                    ),
                )
                universe = set(weights) | set(new_weights)
                turnover = sum(
                    abs(new_weights.get(item, 0.0) - weights.get(item, 0.0)) for item in universe
                )
                cost = turnover * ONE_WAY_COST
                rebalance_map[trade_session] = (signal_session, new_weights, cost)
                weights = new_weights
                for instrument_id, research_weight in sorted(new_weights.items()):
                    trade_rows.append(
                        {
                            "strategy_name": strategy,
                            "evaluation_segment": segment,
                            "signal_session_date": signal_session,
                            "trade_session_date": trade_session,
                            "execution_rule": "next_valid_us_equity_session_open",
                            "instrument_id": instrument_id,
                            "research_weight": research_weight,
                            "turnover": turnover,
                            "transaction_cost": cost,
                        }
                    )
            weights = {RISK_FREE_INSTRUMENT_ID: 1.0}
            for session in sessions:
                cost = 0.0
                if session in rebalance_map:
                    _signal, weights, cost = rebalance_map[session]
                daily_return = sum(
                    weights.get(item, 0.0) * returns.at[session, item]
                    for item in weights
                    if item in returns.columns
                )
                return_rows.append(
                    {
                        "strategy_name": strategy,
                        "evaluation_segment": segment,
                        "session_date": session,
                        "gross_return": daily_return,
                        "transaction_cost": cost,
                        "net_return": daily_return - cost,
                    }
                )
    return pd.DataFrame(return_rows), pd.DataFrame(trade_rows)


def _max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min()) if len(drawdown) else float("nan")


def build_scoreboard(
    predictions: pd.DataFrame,
    strategy_returns: pd.DataFrame,
    strategy_trades: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    forecast_specs = [
        ("ridge_fixed_alpha_1_0", "prediction"),
        ("zero_forward_excess_return", "zero_prediction"),
        ("persistence_last_observed_return", "persistence_prediction"),
    ]
    for segment, group in predictions.groupby("evaluation_segment"):
        for name, column in forecast_specs:
            valid = group[["target_value", column]].dropna()
            rows.append(
                {
                    "evaluation_layer": "forecast evaluation",
                    "strategy_model_name": name,
                    "evaluation_segment": segment,
                    "annualized_return": np.nan,
                    "annualized_volatility": np.nan,
                    "sharpe_ratio": np.nan,
                    "maximum_drawdown": np.nan,
                    "turnover": np.nan,
                    "total_transaction_costs": np.nan,
                    "rebalance_events": np.nan,
                    "forecast_mae": float((valid["target_value"] - valid[column]).abs().mean()),
                    "forecast_rank_correlation": rank_correlation(
                        valid["target_value"],
                        valid[column],
                    ),
                    "availability_eligible_observation_count": int(len(valid)),
                    "promotion_criteria_pass": False,
                    "promotion_criteria_reason": (
                        "MI-2 baseline research artifact; no promotion claimed"
                    ),
                }
            )
    for (segment, name), group in strategy_returns.groupby(["evaluation_segment", "strategy_name"]):
        trades = strategy_trades[
            (strategy_trades["evaluation_segment"] == segment)
            & (strategy_trades["strategy_name"] == name)
        ]
        returns = group["net_return"]
        annual_return = float((1.0 + returns).prod() ** (252 / max(1, len(returns))) - 1.0)
        annual_vol = float(returns.std(ddof=0) * sqrt(252))
        rows.append(
            {
                "evaluation_layer": "portfolio evaluation",
                "strategy_model_name": name,
                "evaluation_segment": segment,
                "annualized_return": annual_return,
                "annualized_volatility": annual_vol,
                "sharpe_ratio": annual_return / annual_vol if annual_vol else np.nan,
                "maximum_drawdown": _max_drawdown(returns),
                "turnover": float(trades["turnover"].sum()) if not trades.empty else 0.0,
                "total_transaction_costs": float(group["transaction_cost"].sum()),
                "rebalance_events": int(trades["trade_session_date"].nunique())
                if not trades.empty
                else 0,
                "forecast_mae": np.nan,
                "forecast_rank_correlation": np.nan,
                "availability_eligible_observation_count": int(len(group)),
                "promotion_criteria_pass": False,
                "promotion_criteria_reason": (
                    "MI-2 baseline research artifact; no promotion claimed"
                ),
            }
        )
    return pd.DataFrame(rows)


def rank_correlation(left: pd.Series, right: pd.Series) -> float:
    if len(left) < 2:
        return float("nan")
    left_rank = left.rank(method="average")
    right_rank = right.rank(method="average")
    if left_rank.std(ddof=0) == 0.0 or right_rank.std(ddof=0) == 0.0:
        return float("nan")
    return float(left_rank.corr(right_rank))


def write_scoreboard_reports(scoreboard: pd.DataFrame, report_root: Path) -> tuple[Path, Path]:
    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "technical_baseline_scoreboard.json"
    md_path = report_root / "technical_baseline_scoreboard.md"
    json_path.write_text(
        json.dumps(
            scoreboard.replace({np.nan: None}).to_dict(orient="records"), indent=2, default=str
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# MI-2 Technical Baseline Scoreboard",
        "",
        (
            "Feature policy: decision-time features use raw OHLCV only. Vendor adjusted close "
            "is used only for retrospective target and portfolio evaluation."
        ),
        "",
        (
            "| layer | name | segment | ann_return | ann_vol | sharpe | max_dd | turnover | "
            "costs | rebalances | mae | rank_corr | obs | pass |"
        ),
        (
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
            "---: | ---: | ---: | --- |"
        ),
    ]
    for row in scoreboard.itertuples(index=False):
        lines.append(
            f"| {row.evaluation_layer} | {row.strategy_model_name} | {row.evaluation_segment} | "
            f"{row.annualized_return:.6f} | {row.annualized_volatility:.6f} | "
            f"{row.sharpe_ratio:.6f} | {row.maximum_drawdown:.6f} | {row.turnover:.6f} | "
            f"{row.total_transaction_costs:.6f} | {row.rebalance_events} | "
            f"{row.forecast_mae:.6f} | {row.forecast_rank_correlation:.6f} | "
            f"{row.availability_eligible_observation_count} | "
            f"{row.promotion_criteria_pass} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path


def run_mi2_technical_baseline(
    *,
    mi1_data_root: Path,
    mi2_data_root: Path,
    report_root: Path,
    registry_path: Path = Path("configs/intelligence/mi2_research_registry.yaml"),
) -> Mi2RunResult:
    registry = load_registry_rules(registry_path)
    inputs = load_mi1_inputs(mi1_data_root)
    eligible_bars = validate_mi1_contract(inputs)
    instrument_ids = sorted(eligible_bars["instrument_id"].unique())
    research_start = derive_common_research_start(
        eligible_bars,
        instrument_ids,
        int(registry["research_start_date"]["minimum_common_history_sessions"]),
    )
    corporate_actions = _normalize_dates(inputs["corporate_action_event"], ["session_date"])
    feature_panel = build_feature_panel(eligible_bars, corporate_actions, research_start)
    target_panel = build_target_panel(eligible_bars)
    predictions, bounds = build_walk_forward_predictions(feature_panel, target_panel, registry)
    segment_sessions = {
        "walk_forward_validation": bounds["validation_sessions"],
        "untouched_holdout": bounds["holdout_sessions"],
    }
    strategy_returns, strategy_trades = simulate_strategies(
        eligible_bars,
        feature_panel,
        segment_sessions,
    )
    scoreboard = build_scoreboard(predictions, strategy_returns, strategy_trades)

    mi2_data_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "feature_panel": mi2_data_root / "feature_panel.parquet",
        "target_panel": mi2_data_root / "target_panel.parquet",
        "walk_forward_predictions": mi2_data_root / "walk_forward_predictions.parquet",
        "strategy_returns": mi2_data_root / "strategy_returns.parquet",
        "strategy_trades": mi2_data_root / "strategy_trades.parquet",
        "scoreboard": mi2_data_root / "scoreboard.parquet",
    }
    feature_panel.to_parquet(paths["feature_panel"], index=False)
    target_panel.to_parquet(paths["target_panel"], index=False)
    predictions.to_parquet(paths["walk_forward_predictions"], index=False)
    strategy_returns.to_parquet(paths["strategy_returns"], index=False)
    strategy_trades.to_parquet(paths["strategy_trades"], index=False)
    scoreboard.to_parquet(paths["scoreboard"], index=False)
    md_path, json_path = write_scoreboard_reports(scoreboard, report_root)

    output_paths = {name: str(path) for name, path in paths.items()}
    output_paths["scoreboard_markdown"] = str(md_path)
    output_paths["scoreboard_json"] = str(json_path)
    validation_sessions = bounds["validation_sessions"]
    holdout_sessions = bounds["holdout_sessions"]
    provenance = {
        "source": "local MI-1 normalized parquet outputs",
        "bar_count": int(len(eligible_bars)),
        "availability_evidence_levels": sorted(
            eligible_bars["availability_evidence_level"].dropna().unique().tolist()
        ),
    }
    return Mi2RunResult(
        mi1_provenance=provenance,
        research_start_date=research_start.date().isoformat(),
        validation_start_date=validation_sessions[0].date().isoformat(),
        validation_end_date=validation_sessions[-1].date().isoformat(),
        holdout_start_date=holdout_sessions[0].date().isoformat(),
        holdout_end_date=holdout_sessions[-1].date().isoformat(),
        feature_row_count=int(len(feature_panel)),
        target_row_count=int(len(target_panel)),
        strategy_count=int(
            scoreboard[scoreboard["evaluation_layer"] == "portfolio evaluation"][
                "strategy_model_name"
            ].nunique()
        ),
        model_count=1,
        output_paths=output_paths,
        scoreboard_summary=scoreboard[
            [
                "evaluation_layer",
                "strategy_model_name",
                "evaluation_segment",
                "promotion_criteria_pass",
            ]
        ].to_dict(orient="records"),
    )
