from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


DEFAULT_PHASE9A_CONFIG: dict[str, Any] = {
    "enabled": False,
    "initial_capital": 10000.0,
    "ticker": "SPY",
    "strategy_names": {
        "final_candidate": "Final candidate",
        "spy_buy_hold": "SPY Buy & Hold",
        "spy_12m_momentum": "SPY 12M Momentum",
    },
    "indicators": {
        "sma_short_days": 50,
        "sma_long_days": 200,
        "rsi_days": 14,
        "volatility_days": 63,
        "short_momentum_days": 63,
        "medium_momentum_days": 126,
        "long_momentum_days": 252,
        "drawdown_near_high_threshold": -0.05,
        "drawdown_correction_threshold": -0.10,
        "drawdown_bear_threshold": -0.20,
        "trend_distance_near_threshold": 0.03,
        "trend_distance_extended_threshold": 0.10,
    },
    "gates": {
        "min_indicator_coverage_rate": 0.90,
        "min_regime_rows": 4,
        "require_no_strategy_promotion": True,
        "require_underperformance_clusters_reported": True,
        "max_allowed_final_candidate_role": "Diagnostic only",
    },
}


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase9a_technical_indicator_expansion_diagnostic", {})
    return _deep_merge_dict(DEFAULT_PHASE9A_CONFIG, user_config)


def _normalise_strategy_frame(frame: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    required_columns = {"date", "strategy_return"}
    missing = required_columns.difference(frame.columns)

    if missing:
        raise ValueError(f"{strategy_name} is missing required columns: {sorted(missing)}")

    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    out["strategy_return"] = pd.to_numeric(
        out["strategy_return"],
        errors="coerce",
    ).fillna(0.0)

    return out


def _align_frame_to_period(
    frame: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    strategy_name: str,
) -> pd.DataFrame:
    out = _normalise_strategy_frame(frame, strategy_name)
    aligned = out[(out["date"] >= start_date) & (out["date"] <= end_date)].copy()
    aligned = aligned.sort_values("date").reset_index(drop=True)

    if aligned.empty:
        raise ValueError(
            f"{strategy_name} has no rows after alignment to "
            f"{start_date.date()} through {end_date.date()}."
        )

    aligned.loc[aligned.index[0], "strategy_return"] = 0.0

    return aligned


def _find_final_candidate_frame(
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> pd.DataFrame:
    if relative_momentum_outputs is None:
        raise ValueError("relative_momentum_outputs is required for Phase 9A.")

    if ticker_outputs is None:
        raise ValueError("ticker_outputs is required for Phase 9A.")

    final_candidate = _create_audited_overlay_result(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    ).copy()

    required_columns = {"date", "strategy_return", "equity"}
    missing_columns = required_columns.difference(final_candidate.columns)

    if missing_columns:
        raise ValueError(
            "Reconstructed final candidate is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    final_candidate["date"] = pd.to_datetime(final_candidate["date"])

    return final_candidate.sort_values("date").reset_index(drop=True)


def _get_ticker_outputs(
    ticker_outputs: dict[str, Any] | None,
    ticker: str,
) -> dict[str, Any]:
    if ticker_outputs is None:
        raise ValueError("ticker_outputs is required for Phase 9A.")

    ticker_upper = str(ticker).upper()

    if ticker_upper not in ticker_outputs:
        available = sorted(ticker_outputs.keys())
        raise ValueError(f"ticker_outputs missing {ticker_upper!r}. Available: {available}")

    return ticker_outputs[ticker_upper]


def _get_price_frame(
    ticker_outputs: dict[str, Any] | None,
    ticker: str,
) -> pd.DataFrame:
    outputs = _get_ticker_outputs(ticker_outputs, ticker)

    for key in ["price_data", "data"]:
        value = outputs.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy()

    raise ValueError(f"No price_data/data frame found for {ticker}.")


def _get_strategy_result(
    ticker_outputs: dict[str, Any] | None,
    ticker: str,
    strategy_name: str,
) -> pd.DataFrame:
    outputs = _get_ticker_outputs(ticker_outputs, ticker)
    strategy_results = outputs.get("strategy_results", {})

    if strategy_name not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"{ticker} strategy result {strategy_name!r} not found. Available: {available}"
        )

    return strategy_results[strategy_name]


def _resolve_phase9a_input_frames(
    *,
    config: dict[str, Any],
    phase_config: dict[str, Any],
    final_candidate: pd.DataFrame | None,
    spy_buy_hold: pd.DataFrame | None,
    spy_12m_momentum: pd.DataFrame | None,
    price_data: pd.DataFrame | None,
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ticker = str(phase_config.get("ticker", "SPY")).upper()

    if final_candidate is None:
        final_candidate = _find_final_candidate_frame(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
        )

    if spy_buy_hold is None:
        spy_buy_hold = _get_strategy_result(ticker_outputs, ticker, "Buy and Hold")

    if spy_12m_momentum is None:
        spy_12m_momentum = _get_strategy_result(
            ticker_outputs,
            ticker,
            "12-Month Absolute Momentum",
        )

    if price_data is None:
        price_data = _get_price_frame(ticker_outputs, ticker)

    candidate_dates = pd.to_datetime(final_candidate["date"])
    start_date = candidate_dates.min()
    end_date = candidate_dates.max()

    final_candidate = _align_frame_to_period(
        final_candidate,
        start_date=start_date,
        end_date=end_date,
        strategy_name="Final candidate",
    )
    spy_buy_hold = _align_frame_to_period(
        spy_buy_hold,
        start_date=start_date,
        end_date=end_date,
        strategy_name="SPY Buy & Hold",
    )
    spy_12m_momentum = _align_frame_to_period(
        spy_12m_momentum,
        start_date=start_date,
        end_date=end_date,
        strategy_name="SPY 12M Momentum",
    )

    prices = price_data.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices[(prices["date"] >= start_date) & (prices["date"] <= end_date)].copy()
    prices = prices.sort_values("date").drop_duplicates(subset=["date"]).reset_index(
        drop=True
    )

    if prices.empty:
        raise ValueError(
            f"Price data has no rows after alignment to {start_date.date()} "
            f"through {end_date.date()}."
        )

    return final_candidate, spy_buy_hold, spy_12m_momentum, prices


def _price_column(prices: pd.DataFrame) -> str:
    if "adj_close" in prices.columns:
        return "adj_close"
    if "close" in prices.columns:
        return "close"
    raise ValueError("Price data must contain adj_close or close.")


def _rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)

    avg_gain = gains.rolling(window).mean()
    avg_loss = losses.rolling(window).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    return rsi.fillna(50.0)


def build_phase9a_indicator_frame(
    prices: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    indicator_config = phase_config.get("indicators", {})
    price_col = _price_column(prices)

    out = prices[["date", price_col]].copy()
    out = out.rename(columns={price_col: "price"})
    out["price"] = pd.to_numeric(out["price"], errors="coerce")

    sma_short_days = int(indicator_config.get("sma_short_days", 50))
    sma_long_days = int(indicator_config.get("sma_long_days", 200))
    rsi_days = int(indicator_config.get("rsi_days", 14))
    volatility_days = int(indicator_config.get("volatility_days", 63))
    short_momentum_days = int(indicator_config.get("short_momentum_days", 63))
    medium_momentum_days = int(indicator_config.get("medium_momentum_days", 126))
    long_momentum_days = int(indicator_config.get("long_momentum_days", 252))

    out["daily_return"] = out["price"].pct_change().fillna(0.0)
    out["sma_short"] = out["price"].rolling(sma_short_days).mean()
    out["sma_long"] = out["price"].rolling(sma_long_days).mean()
    out["trend_distance_long"] = out["price"] / out["sma_long"] - 1.0
    out["sma_short_minus_long"] = out["sma_short"] / out["sma_long"] - 1.0
    out["rsi"] = _rsi(out["price"], rsi_days)
    out["realized_volatility"] = out["daily_return"].rolling(volatility_days).std() * np.sqrt(
        252.0
    )
    out["momentum_short"] = out["price"].pct_change(short_momentum_days)
    out["momentum_medium"] = out["price"].pct_change(medium_momentum_days)
    out["momentum_long"] = out["price"].pct_change(long_momentum_days)
    out["drawdown"] = out["price"] / out["price"].cummax() - 1.0

    return out


def _bucket_drawdown(drawdown: float, indicator_config: dict[str, Any]) -> str:
    near_high = float(indicator_config.get("drawdown_near_high_threshold", -0.05))
    correction = float(indicator_config.get("drawdown_correction_threshold", -0.10))
    bear = float(indicator_config.get("drawdown_bear_threshold", -0.20))

    if drawdown <= bear:
        return "deep_bear_below_-20"
    if drawdown <= correction:
        return "correction_-10_to_-20"
    if drawdown <= near_high:
        return "mild_drawdown_-5_to_-10"
    return "near_high_0_to_-5"


def _bucket_trend_distance(value: float, indicator_config: dict[str, Any]) -> str:
    near = float(indicator_config.get("trend_distance_near_threshold", 0.03))
    extended = float(indicator_config.get("trend_distance_extended_threshold", 0.10))

    if pd.isna(value):
        return "unknown"
    if value < 0:
        return "below_long_sma"
    if value <= near:
        return "near_long_sma"
    if value <= extended:
        return "above_long_sma_moderate"
    return "above_long_sma_extended"


def _bucket_rsi(value: float) -> str:
    if pd.isna(value):
        return "unknown"
    if value < 30:
        return "oversold_below_30"
    if value > 70:
        return "overbought_above_70"
    return "neutral_30_to_70"


def _bucket_volatility(series: pd.Series) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    valid = clean.dropna()

    if valid.nunique() < 3:
        return pd.Series("unknown", index=series.index)

    low_cut = valid.quantile(1 / 3)
    high_cut = valid.quantile(2 / 3)

    def _bucket(value: float) -> str:
        if pd.isna(value):
            return "unknown"
        if value <= low_cut:
            return "low_volatility"
        if value <= high_cut:
            return "medium_volatility"
        return "high_volatility"

    return clean.map(_bucket)


def build_phase9a_regime_frame(
    indicator_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    indicator_config = phase_config.get("indicators", {})
    out = indicator_frame.copy()

    out["trend_state"] = np.where(
        out["price"] >= out["sma_long"],
        "above_long_sma",
        "below_long_sma",
    )
    out.loc[out["sma_long"].isna(), "trend_state"] = "unknown"
    out["drawdown_bucket"] = out["drawdown"].map(
        lambda value: _bucket_drawdown(float(value), indicator_config)
    )
    out["trend_distance_bucket"] = out["trend_distance_long"].map(
        lambda value: _bucket_trend_distance(float(value), indicator_config)
        if not pd.isna(value)
        else "unknown"
    )
    out["rsi_bucket"] = out["rsi"].map(_bucket_rsi)
    out["volatility_bucket"] = _bucket_volatility(out["realized_volatility"])
    out["long_momentum_state"] = np.where(
        out["momentum_long"] > 0,
        "positive_12m_momentum",
        "negative_12m_momentum",
    )
    out.loc[out["momentum_long"].isna(), "long_momentum_state"] = "unknown"

    out["technical_risk_state"] = "mixed"
    out.loc[
        (out["trend_state"] == "above_long_sma")
        & (out["long_momentum_state"] == "positive_12m_momentum")
        & (out["drawdown_bucket"].isin(["near_high_0_to_-5", "mild_drawdown_-5_to_-10"])),
        "technical_risk_state",
    ] = "risk_on"
    out.loc[
        (out["trend_state"] == "below_long_sma")
        | (out["long_momentum_state"] == "negative_12m_momentum")
        | (out["drawdown_bucket"] == "deep_bear_below_-20"),
        "technical_risk_state",
    ] = "risk_off"

    return out


def build_phase9a_analysis_frame(
    *,
    final_candidate: pd.DataFrame,
    spy_buy_hold: pd.DataFrame,
    spy_12m_momentum: pd.DataFrame,
    regime_frame: pd.DataFrame,
) -> pd.DataFrame:
    candidate = _normalise_strategy_frame(final_candidate, "Final candidate")
    buy_hold = _normalise_strategy_frame(spy_buy_hold, "SPY Buy & Hold")
    spy_12m = _normalise_strategy_frame(spy_12m_momentum, "SPY 12M Momentum")

    out = regime_frame.merge(
        candidate[["date", "strategy_return"]],
        on="date",
        how="inner",
    ).rename(columns={"strategy_return": "candidate_return"})
    out = out.merge(
        buy_hold[["date", "strategy_return"]],
        on="date",
        how="inner",
    ).rename(columns={"strategy_return": "buy_hold_return"})
    out = out.merge(
        spy_12m[["date", "strategy_return"]],
        on="date",
        how="inner",
    ).rename(columns={"strategy_return": "spy_12m_return"})

    out["candidate_minus_buy_hold"] = out["candidate_return"] - out["buy_hold_return"]
    out["candidate_minus_spy_12m"] = out["candidate_return"] - out["spy_12m_return"]
    out["candidate_underperforms_buy_hold"] = out["candidate_minus_buy_hold"] < 0
    out["candidate_underperforms_spy_12m"] = out["candidate_minus_spy_12m"] < 0

    indicator_columns = [
        "sma_long",
        "trend_distance_long",
        "realized_volatility",
        "momentum_short",
        "momentum_medium",
        "momentum_long",
    ]
    out["indicator_row_complete"] = out[indicator_columns].notna().all(axis=1)

    return out


def _summarise_by_regime(
    analysis_frame: pd.DataFrame,
    regime_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for regime_value, group in analysis_frame.groupby(regime_column, dropna=False):
        rows.append(
            {
                "regime_column": regime_column,
                "regime_value": str(regime_value),
                "rows": int(len(group)),
                "coverage_rate": float(group["indicator_row_complete"].mean()),
                "candidate_avg_daily_return": float(group["candidate_return"].mean()),
                "buy_hold_avg_daily_return": float(group["buy_hold_return"].mean()),
                "spy_12m_avg_daily_return": float(group["spy_12m_return"].mean()),
                "candidate_minus_buy_hold_avg_daily": float(
                    group["candidate_minus_buy_hold"].mean()
                ),
                "candidate_minus_spy_12m_avg_daily": float(
                    group["candidate_minus_spy_12m"].mean()
                ),
                "underperform_buy_hold_rate": float(
                    group["candidate_underperforms_buy_hold"].mean()
                ),
                "underperform_spy_12m_rate": float(
                    group["candidate_underperforms_spy_12m"].mean()
                ),
                "worst_candidate_minus_buy_hold_daily": float(
                    group["candidate_minus_buy_hold"].min()
                ),
                "worst_candidate_minus_spy_12m_daily": float(
                    group["candidate_minus_spy_12m"].min()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase9a_regime_summary(analysis_frame: pd.DataFrame) -> pd.DataFrame:
    regime_columns = [
        "trend_state",
        "drawdown_bucket",
        "trend_distance_bucket",
        "rsi_bucket",
        "volatility_bucket",
        "long_momentum_state",
        "technical_risk_state",
    ]

    summaries = [
        _summarise_by_regime(analysis_frame, column)
        for column in regime_columns
        if column in analysis_frame.columns
    ]

    if not summaries:
        return pd.DataFrame()

    return pd.concat(summaries, ignore_index=True)


def build_phase9a_underperformance_clusters(
    regime_summary: pd.DataFrame,
) -> pd.DataFrame:
    if regime_summary.empty:
        return pd.DataFrame()

    cluster = regime_summary.copy()
    cluster = cluster[cluster["rows"] >= 20].copy()

    if cluster.empty:
        return pd.DataFrame()

    cluster["buy_hold_pain_score"] = (
        cluster["underperform_buy_hold_rate"]
        * -cluster["candidate_minus_buy_hold_avg_daily"]
    )
    cluster["spy12m_pain_score"] = (
        cluster["underperform_spy_12m_rate"]
        * -cluster["candidate_minus_spy_12m_avg_daily"]
    )

    cluster = cluster.sort_values(
        ["buy_hold_pain_score", "spy12m_pain_score"],
        ascending=False,
    ).reset_index(drop=True)

    return cluster.head(15)


def build_phase9a_summary(
    analysis_frame: pd.DataFrame,
    regime_summary: pd.DataFrame,
    underperformance_clusters: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {
            "start_date": pd.to_datetime(analysis_frame["date"].min()).date().isoformat(),
            "end_date": pd.to_datetime(analysis_frame["date"].max()).date().isoformat(),
            "rows": int(len(analysis_frame)),
            "indicator_coverage_rate": float(
                analysis_frame["indicator_row_complete"].mean()
            ),
            "regime_rows": int(len(regime_summary)),
            "underperformance_cluster_rows": int(len(underperformance_clusters)),
            "candidate_underperforms_buy_hold_rate": float(
                analysis_frame["candidate_underperforms_buy_hold"].mean()
            ),
            "candidate_underperforms_spy_12m_rate": float(
                analysis_frame["candidate_underperforms_spy_12m"].mean()
            ),
            "mean_candidate_minus_buy_hold_daily": float(
                analysis_frame["candidate_minus_buy_hold"].mean()
            ),
            "mean_candidate_minus_spy_12m_daily": float(
                analysis_frame["candidate_minus_spy_12m"].mean()
            ),
            "diagnostic_role": "Diagnostic only",
            "strategy_promotion": False,
        }
    ]

    return pd.DataFrame(rows)


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase9a_gate_report(
    summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 9A summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]
    min_coverage = float(gates.get("min_indicator_coverage_rate", 0.90))
    min_regime_rows = int(gates.get("min_regime_rows", 4))
    require_no_promotion = bool(gates.get("require_no_strategy_promotion", True))
    require_clusters = bool(gates.get("require_underperformance_clusters_reported", True))
    max_role = str(gates.get("max_allowed_final_candidate_role", "Diagnostic only"))

    rows = [
        _gate_row(
            "Indicator coverage is sufficient",
            float(row["indicator_coverage_rate"]) >= min_coverage,
            f"{row['indicator_coverage_rate']:.2%}; required >= {min_coverage:.2%}",
        ),
        _gate_row(
            "Technical regime rows were generated",
            int(row["regime_rows"]) >= min_regime_rows,
            f"{int(row['regime_rows'])} rows; required >= {min_regime_rows}",
        ),
        _gate_row(
            "Underperformance clusters were reported",
            (not require_clusters) or int(row["underperformance_cluster_rows"]) > 0,
            f"{int(row['underperformance_cluster_rows'])} cluster rows",
        ),
        _gate_row(
            "Diagnostic does not promote a new strategy",
            (not require_no_promotion) or not bool(row["strategy_promotion"]),
            f"strategy_promotion={bool(row['strategy_promotion'])}",
        ),
        _gate_row(
            "Diagnostic role remains bounded",
            str(row["diagnostic_role"]) == max_role,
            f"diagnostic_role={row['diagnostic_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase9a_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Completed — diagnostic only"
        interpretation = (
            "Phase 9A generated technical-regime diagnostics without promoting a new "
            "strategy. Results can inform future hypotheses, but do not change the "
            "final candidate hierarchy."
        )
    else:
        verdict = "Failed diagnostic discipline"
        interpretation = (
            "Phase 9A did not satisfy every diagnostic gate. Do not use it to justify "
            "new technical rules until the diagnostic issue is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 9A",
                "diagnostic": "Technical indicator expansion diagnostic",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase9a_markdown(
    *,
    summary: pd.DataFrame,
    regime_summary: pd.DataFrame,
    underperformance_clusters: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 9A — Technical Indicator Expansion Diagnostic",
        "",
        "## Purpose",
        "",
        (
            "This diagnostic checks whether additional price-derived technical "
            "indicators explain where the final candidate helps or fails."
        ),
        "",
        "It is not a new strategy and it does not tune the final candidate.",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Regime Summary",
        "",
        regime_summary.to_markdown(index=False),
        "",
        "## Underperformance Clusters",
        "",
        underperformance_clusters.to_markdown(index=False),
        "",
        "## Gate Report",
        "",
        gate_report.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        conclusion.to_markdown(index=False),
        "",
        "## Limitations",
        "",
        "- This is a diagnostic only.",
        "- It does not create or promote a new trading rule.",
        "- Regime buckets are descriptive and can still overfit if converted into rules.",
        "- Future technical rules require separate pre-defined validation gates.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase9a_technical_indicator_expansion_diagnostic(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
    final_candidate: pd.DataFrame | None = None,
    spy_buy_hold: pd.DataFrame | None = None,
    spy_12m_momentum: pd.DataFrame | None = None,
    price_data: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "indicator_frame": empty,
            "regime_frame": empty,
            "analysis_frame": empty,
            "regime_summary": empty,
            "underperformance_clusters": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    final_candidate, spy_buy_hold, spy_12m_momentum, prices = (
        _resolve_phase9a_input_frames(
            config=config,
            phase_config=phase_config,
            final_candidate=final_candidate,
            spy_buy_hold=spy_buy_hold,
            spy_12m_momentum=spy_12m_momentum,
            price_data=price_data,
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
        )
    )

    indicator_frame = build_phase9a_indicator_frame(prices, phase_config)
    regime_frame = build_phase9a_regime_frame(indicator_frame, phase_config)
    analysis_frame = build_phase9a_analysis_frame(
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
        regime_frame=regime_frame,
    )
    regime_summary = build_phase9a_regime_summary(analysis_frame)
    underperformance_clusters = build_phase9a_underperformance_clusters(regime_summary)
    summary = build_phase9a_summary(
        analysis_frame,
        regime_summary,
        underperformance_clusters,
    )
    gate_report = build_phase9a_gate_report(summary, phase_config)
    conclusion = build_phase9a_conclusion(gate_report)

    indicator_frame.to_csv(
        reports_path / "phase9a_technical_indicator_frame.csv",
        index=False,
    )
    regime_frame.to_csv(
        reports_path / "phase9a_technical_regime_frame.csv",
        index=False,
    )
    analysis_frame.to_csv(
        reports_path / "phase9a_technical_indicator_analysis_frame.csv",
        index=False,
    )
    regime_summary.to_csv(
        reports_path / "phase9a_technical_regime_summary.csv",
        index=False,
    )
    underperformance_clusters.to_csv(
        reports_path / "phase9a_technical_underperformance_clusters.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase9a_technical_indicator_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase9a_technical_indicator_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase9a_technical_indicator_conclusion.csv",
        index=False,
    )

    write_phase9a_markdown(
        summary=summary,
        regime_summary=regime_summary,
        underperformance_clusters=underperformance_clusters,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase9a_technical_indicator_expansion_diagnostic.md",
    )

    print("Wrote Phase 9A technical indicator expansion diagnostic reports.")

    return {
        "indicator_frame": indicator_frame,
        "regime_frame": regime_frame,
        "analysis_frame": analysis_frame,
        "regime_summary": regime_summary,
        "underperformance_clusters": underperformance_clusters,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }