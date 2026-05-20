from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


DEFAULT_PHASE8C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "initial_capital": 10000.0,
    "strategy_names": {
        "final_candidate": "Final candidate",
        "spy_buy_hold": "SPY Buy & Hold",
        "spy_12m_momentum": "SPY 12M Momentum",
    },
    "window": {
        "initial_train_years": 5,
        "test_years": 3,
        "step_years": 3,
        "include_partial_last_window": True,
        "min_test_years": 2.0,
    },
    "gates": {
        "min_test_windows": 4,
        "min_candidate_beats_spy12m_cagr_rate": 0.50,
        "min_candidate_beats_spy12m_calmar_rate": 0.60,
        "min_candidate_better_spy12m_drawdown_rate": 0.60,
        "min_candidate_positive_cagr_rate": 0.80,
        "max_candidate_beats_buy_hold_cagr_rate_for_hierarchy": 0.50,
        "min_candidate_beats_buy_hold_calmar_rate": 0.50,
        "min_candidate_better_buy_hold_drawdown_rate": 0.60,
        "require_worst_candidate_cagr_positive": True,
    },
}


@dataclass(frozen=True)
class Phase8CInput:
    name: str
    returns: pd.DataFrame


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


def _get_phase_config(config: dict[str, Any]) -> dict[str, Any]:
    user_config = config.get("phase8c_walk_forward_validation_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE8C_CONFIG, user_config)


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
        raise ValueError("relative_momentum_outputs is required for Phase 8C.")

    if ticker_outputs is None:
        raise ValueError("ticker_outputs is required for Phase 8C.")

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


def _get_spy_strategy_result(
    ticker_outputs: dict[str, Any] | None,
    strategy_name: str,
) -> pd.DataFrame:
    if not ticker_outputs or "SPY" not in ticker_outputs:
        raise ValueError("ticker_outputs must contain SPY for Phase 8C.")

    strategy_results = ticker_outputs["SPY"].get("strategy_results", {})

    if strategy_name not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"SPY strategy result {strategy_name!r} not found. Available: {available}"
        )

    return strategy_results[strategy_name]


def _resolve_phase8c_input_frames(
    *,
    config: dict[str, Any],
    final_candidate: pd.DataFrame | None,
    spy_buy_hold: pd.DataFrame | None,
    spy_12m_momentum: pd.DataFrame | None,
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if final_candidate is None:
        final_candidate = _find_final_candidate_frame(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
        )

    if spy_buy_hold is None:
        spy_buy_hold = _get_spy_strategy_result(ticker_outputs, "Buy and Hold")

    if spy_12m_momentum is None:
        spy_12m_momentum = _get_spy_strategy_result(
            ticker_outputs,
            "12-Month Absolute Momentum",
        )

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

    return final_candidate, spy_buy_hold, spy_12m_momentum


def _period_years(start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    return max(0.0, (end_date - start_date).days / 365.25)


def _first_date_on_or_after(dates: pd.Series, target: pd.Timestamp) -> pd.Timestamp | None:
    candidates = dates[dates >= target]
    if candidates.empty:
        return None
    return pd.Timestamp(candidates.iloc[0])


def _last_date_on_or_before(dates: pd.Series, target: pd.Timestamp) -> pd.Timestamp | None:
    candidates = dates[dates <= target]
    if candidates.empty:
        return None
    return pd.Timestamp(candidates.iloc[-1])


def build_phase8c_walk_forward_windows(
    reference_frame: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    window_config = phase_config.get("window", {})

    initial_train_years = int(window_config.get("initial_train_years", 5))
    test_years = int(window_config.get("test_years", 3))
    step_years = int(window_config.get("step_years", test_years))
    include_partial_last_window = bool(
        window_config.get("include_partial_last_window", True)
    )
    min_test_years = float(window_config.get("min_test_years", 2.0))

    dates = pd.to_datetime(reference_frame["date"]).drop_duplicates().sort_values()
    full_start = pd.Timestamp(dates.iloc[0])
    full_end = pd.Timestamp(dates.iloc[-1])

    current_test_start_target = full_start + pd.DateOffset(years=initial_train_years)
    rows: list[dict[str, Any]] = []
    window_id = 1

    while current_test_start_target <= full_end:
        test_start = _first_date_on_or_after(dates, current_test_start_target)

        if test_start is None:
            break

        train_end = _last_date_on_or_before(dates, test_start - pd.Timedelta(days=1))

        if train_end is None:
            break

        test_end_target = test_start + pd.DateOffset(years=test_years) - pd.Timedelta(
            days=1
        )
        capped_test_end_target = min(test_end_target, full_end)
        test_end = _last_date_on_or_before(dates, capped_test_end_target)

        if test_end is None:
            break

        test_period_years = _period_years(test_start, test_end)

        if test_period_years < min_test_years:
            if include_partial_last_window:
                break
            break

        rows.append(
            {
                "window_id": window_id,
                "train_start_date": full_start.date().isoformat(),
                "train_end_date": train_end.date().isoformat(),
                "test_start_date": test_start.date().isoformat(),
                "test_end_date": test_end.date().isoformat(),
                "train_years": _period_years(full_start, train_end),
                "test_years": test_period_years,
            }
        )

        window_id += 1
        current_test_start_target = test_start + pd.DateOffset(years=step_years)

    return pd.DataFrame(rows)


def _infer_periods_per_year(dates: pd.Series) -> float:
    clean_dates = pd.to_datetime(dates).dropna().sort_values()

    if len(clean_dates) < 2:
        return 252.0

    elapsed_days = (clean_dates.iloc[-1] - clean_dates.iloc[0]).days

    if elapsed_days <= 0:
        return 252.0

    observations_per_year = (len(clean_dates) - 1) / (elapsed_days / 365.25)

    if observations_per_year > 300:
        return 365.25

    return 252.0


def _equity_curve(returns: pd.Series, initial_capital: float) -> pd.Series:
    clean_returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return initial_capital * (1.0 + clean_returns).cumprod()


def _drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def _calculate_segment_metrics(
    frame: pd.DataFrame,
    *,
    strategy_name: str,
    segment: str,
    window_id: int,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    initial_capital: float,
) -> dict[str, Any]:
    segment_frame = frame[
        (frame["date"] >= start_date) & (frame["date"] <= end_date)
    ].copy()
    segment_frame = segment_frame.sort_values("date").reset_index(drop=True)

    if segment_frame.empty:
        raise ValueError(
            f"{strategy_name} has no rows for {segment} window {window_id}: "
            f"{start_date.date()} to {end_date.date()}."
        )

    segment_frame.loc[segment_frame.index[0], "strategy_return"] = 0.0

    equity = _equity_curve(segment_frame["strategy_return"], initial_capital)
    max_drawdown = float(_drawdown(equity).min())
    years = _period_years(
        pd.Timestamp(segment_frame["date"].iloc[0]),
        pd.Timestamp(segment_frame["date"].iloc[-1]),
    )
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)

    if years <= 0:
        cagr = 0.0
    else:
        cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)

    volatility = float(
        segment_frame["strategy_return"].std(ddof=0)
        * np.sqrt(_infer_periods_per_year(segment_frame["date"]))
    )
    calmar = np.nan if max_drawdown >= 0 else float(cagr / abs(max_drawdown))

    return {
        "window_id": window_id,
        "segment": segment,
        "strategy": strategy_name,
        "start_date": pd.Timestamp(segment_frame["date"].iloc[0]).date().isoformat(),
        "end_date": pd.Timestamp(segment_frame["date"].iloc[-1]).date().isoformat(),
        "period_years": years,
        "end_value": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "calmar": calmar,
    }


def build_phase8c_window_metrics(
    inputs: list[Phase8CInput],
    windows: pd.DataFrame,
    *,
    initial_capital: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, window in windows.iterrows():
        window_id = int(window["window_id"])
        train_start = pd.Timestamp(window["train_start_date"])
        train_end = pd.Timestamp(window["train_end_date"])
        test_start = pd.Timestamp(window["test_start_date"])
        test_end = pd.Timestamp(window["test_end_date"])

        for item in inputs:
            frame = _normalise_strategy_frame(item.returns, item.name)

            rows.append(
                _calculate_segment_metrics(
                    frame,
                    strategy_name=item.name,
                    segment="train_expanding",
                    window_id=window_id,
                    start_date=train_start,
                    end_date=train_end,
                    initial_capital=initial_capital,
                )
            )
            rows.append(
                _calculate_segment_metrics(
                    frame,
                    strategy_name=item.name,
                    segment="test_forward",
                    window_id=window_id,
                    start_date=test_start,
                    end_date=test_end,
                    initial_capital=initial_capital,
                )
            )

    return pd.DataFrame(rows)


def build_phase8c_comparison(
    window_metrics: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    names = phase_config.get("strategy_names", {})
    candidate_name = names.get("final_candidate", "Final candidate")
    buy_hold_name = names.get("spy_buy_hold", "SPY Buy & Hold")
    spy_12m_name = names.get("spy_12m_momentum", "SPY 12M Momentum")

    test_metrics = window_metrics[window_metrics["segment"] == "test_forward"]
    rows: list[dict[str, Any]] = []

    for window_id in sorted(test_metrics["window_id"].unique()):
        group = test_metrics[test_metrics["window_id"] == window_id].set_index("strategy")

        if not {candidate_name, buy_hold_name, spy_12m_name}.issubset(group.index):
            continue

        candidate = group.loc[candidate_name]
        buy_hold = group.loc[buy_hold_name]
        spy_12m = group.loc[spy_12m_name]

        rows.append(
            {
                "window_id": int(window_id),
                "test_start_date": candidate["start_date"],
                "test_end_date": candidate["end_date"],
                "candidate_cagr": candidate["cagr"],
                "spy_12m_cagr": spy_12m["cagr"],
                "buy_hold_cagr": buy_hold["cagr"],
                "candidate_minus_spy_12m_cagr": candidate["cagr"] - spy_12m["cagr"],
                "candidate_minus_buy_hold_cagr": candidate["cagr"] - buy_hold["cagr"],
                "candidate_calmar": candidate["calmar"],
                "spy_12m_calmar": spy_12m["calmar"],
                "buy_hold_calmar": buy_hold["calmar"],
                "candidate_minus_spy_12m_calmar": (
                    candidate["calmar"] - spy_12m["calmar"]
                ),
                "candidate_minus_buy_hold_calmar": (
                    candidate["calmar"] - buy_hold["calmar"]
                ),
                "candidate_max_drawdown": candidate["max_drawdown"],
                "spy_12m_max_drawdown": spy_12m["max_drawdown"],
                "buy_hold_max_drawdown": buy_hold["max_drawdown"],
                "candidate_drawdown_advantage_vs_spy_12m": (
                    candidate["max_drawdown"] - spy_12m["max_drawdown"]
                ),
                "candidate_drawdown_advantage_vs_buy_hold": (
                    candidate["max_drawdown"] - buy_hold["max_drawdown"]
                ),
                "candidate_positive_cagr": candidate["cagr"] > 0,
                "candidate_beats_spy_12m_cagr": candidate["cagr"] > spy_12m["cagr"],
                "candidate_beats_spy_12m_calmar": (
                    candidate["calmar"] > spy_12m["calmar"]
                ),
                "candidate_better_spy_12m_drawdown": (
                    candidate["max_drawdown"] > spy_12m["max_drawdown"]
                ),
                "candidate_beats_buy_hold_cagr": candidate["cagr"] > buy_hold["cagr"],
                "candidate_beats_buy_hold_calmar": (
                    candidate["calmar"] > buy_hold["calmar"]
                ),
                "candidate_better_buy_hold_drawdown": (
                    candidate["max_drawdown"] > buy_hold["max_drawdown"]
                ),
            }
        )

    return pd.DataFrame(rows)


def build_phase8c_summary(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()

    bool_columns = [
        "candidate_positive_cagr",
        "candidate_beats_spy_12m_cagr",
        "candidate_beats_spy_12m_calmar",
        "candidate_better_spy_12m_drawdown",
        "candidate_beats_buy_hold_cagr",
        "candidate_beats_buy_hold_calmar",
        "candidate_better_buy_hold_drawdown",
    ]

    summary = {
        "test_windows": int(len(comparison)),
        "candidate_positive_cagr_rate": comparison["candidate_positive_cagr"].mean(),
        "candidate_beats_spy12m_cagr_rate": comparison[
            "candidate_beats_spy_12m_cagr"
        ].mean(),
        "candidate_beats_spy12m_calmar_rate": comparison[
            "candidate_beats_spy_12m_calmar"
        ].mean(),
        "candidate_better_spy12m_drawdown_rate": comparison[
            "candidate_better_spy_12m_drawdown"
        ].mean(),
        "candidate_beats_buy_hold_cagr_rate": comparison[
            "candidate_beats_buy_hold_cagr"
        ].mean(),
        "candidate_beats_buy_hold_calmar_rate": comparison[
            "candidate_beats_buy_hold_calmar"
        ].mean(),
        "candidate_better_buy_hold_drawdown_rate": comparison[
            "candidate_better_buy_hold_drawdown"
        ].mean(),
        "mean_candidate_minus_spy12m_cagr": comparison[
            "candidate_minus_spy_12m_cagr"
        ].mean(),
        "median_candidate_minus_spy12m_cagr": comparison[
            "candidate_minus_spy_12m_cagr"
        ].median(),
        "worst_candidate_cagr": comparison["candidate_cagr"].min(),
        "worst_candidate_minus_spy12m_cagr": comparison[
            "candidate_minus_spy_12m_cagr"
        ].min(),
        "worst_candidate_max_drawdown": comparison["candidate_max_drawdown"].min(),
    }

    for column in bool_columns:
        summary[f"{column}_count"] = int(comparison[column].sum())

    return pd.DataFrame([summary])


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase8c_gate_report(
    summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 8C produced at least one walk-forward window",
                    False,
                    "No windows were generated.",
                )
            ]
        )

    gates = phase_config.get("gates", {})
    row = summary.iloc[0]

    min_windows = int(gates.get("min_test_windows", 4))
    min_cagr_rate = float(gates.get("min_candidate_beats_spy12m_cagr_rate", 0.50))
    min_calmar_rate = float(gates.get("min_candidate_beats_spy12m_calmar_rate", 0.60))
    min_dd_rate = float(gates.get("min_candidate_better_spy12m_drawdown_rate", 0.60))
    min_positive_rate = float(gates.get("min_candidate_positive_cagr_rate", 0.80))
    max_bh_cagr_rate = float(
        gates.get("max_candidate_beats_buy_hold_cagr_rate_for_hierarchy", 0.50)
    )
    min_bh_calmar_rate = float(gates.get("min_candidate_beats_buy_hold_calmar_rate", 0.50))
    min_bh_dd_rate = float(gates.get("min_candidate_better_buy_hold_drawdown_rate", 0.60))
    require_positive_worst = bool(gates.get("require_worst_candidate_cagr_positive", True))

    rows = [
        _gate_row(
            "Enough forward windows were generated",
            int(row["test_windows"]) >= min_windows,
            f"{int(row['test_windows'])} windows; required {min_windows}",
        ),
        _gate_row(
            "Candidate beats SPY 12M on CAGR often enough",
            float(row["candidate_beats_spy12m_cagr_rate"]) >= min_cagr_rate,
            f"{row['candidate_beats_spy12m_cagr_rate']:.2%}; required {min_cagr_rate:.2%}",
        ),
        _gate_row(
            "Candidate beats SPY 12M on Calmar often enough",
            float(row["candidate_beats_spy12m_calmar_rate"]) >= min_calmar_rate,
            (
                f"{row['candidate_beats_spy12m_calmar_rate']:.2%}; "
                f"required {min_calmar_rate:.2%}"
            ),
        ),
        _gate_row(
            "Candidate has better drawdown than SPY 12M often enough",
            float(row["candidate_better_spy12m_drawdown_rate"]) >= min_dd_rate,
            (
                f"{row['candidate_better_spy12m_drawdown_rate']:.2%}; "
                f"required {min_dd_rate:.2%}"
            ),
        ),
        _gate_row(
            "Candidate keeps positive CAGR often enough",
            float(row["candidate_positive_cagr_rate"]) >= min_positive_rate,
            f"{row['candidate_positive_cagr_rate']:.2%}; required {min_positive_rate:.2%}",
        ),
        _gate_row(
            "Candidate does not warrant raw-CAGR promotion over Buy & Hold",
            float(row["candidate_beats_buy_hold_cagr_rate"]) <= max_bh_cagr_rate,
            (
                f"{row['candidate_beats_buy_hold_cagr_rate']:.2%}; "
                f"maximum {max_bh_cagr_rate:.2%}"
            ),
        ),
        _gate_row(
            "Candidate beats Buy & Hold on Calmar often enough",
            float(row["candidate_beats_buy_hold_calmar_rate"]) >= min_bh_calmar_rate,
            (
                f"{row['candidate_beats_buy_hold_calmar_rate']:.2%}; "
                f"required {min_bh_calmar_rate:.2%}"
            ),
        ),
        _gate_row(
            "Candidate has better drawdown than Buy & Hold often enough",
            float(row["candidate_better_buy_hold_drawdown_rate"]) >= min_bh_dd_rate,
            (
                f"{row['candidate_better_buy_hold_drawdown_rate']:.2%}; "
                f"required {min_bh_dd_rate:.2%}"
            ),
        ),
        _gate_row(
            "Worst candidate forward-window CAGR remains positive",
            (not require_positive_worst) or float(row["worst_candidate_cagr"]) > 0,
            f"worst candidate CAGR {row['worst_candidate_cagr']:.2%}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase8c_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Survived with caveat"
        interpretation = (
            "The final candidate survived the configured walk-forward / "
            "expanding-window audit. This strengthens the sequential validation "
            "story, but it is still not a full prospective model-selection test."
        )
    else:
        verdict = "Failed / mixed walk-forward evidence"
        interpretation = (
            "The final candidate did not pass every configured walk-forward gate. "
            "This narrows the validation claim and should be documented rather "
            "than tuned away."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 8C",
                "diagnostic": "Walk-forward / expanding-window validation audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase8c_markdown(
    windows: pd.DataFrame,
    window_metrics: pd.DataFrame,
    comparison: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 8C — Walk-Forward / Expanding-Window Validation Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit tests the final fixed candidate across sequential forward "
            "windows after an expanding training-history period."
        ),
        "",
        (
            "It does not re-optimise the strategy and it is not a full prospective "
            "walk-forward model-selection framework."
        ),
        "",
        "## Windows",
        "",
        windows.to_markdown(index=False),
        "",
        "## Window Metrics",
        "",
        window_metrics.to_markdown(index=False),
        "",
        "## Forward-Window Comparison",
        "",
        comparison.to_markdown(index=False),
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
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
        "- This is not a full prospective model-selection test.",
        "- The final candidate was already selected before this audit.",
        "- The audit tests sequential robustness, not statistical proof.",
        "- Failed gates should narrow the claim rather than trigger tuning.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase8c_walk_forward_validation_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
    final_candidate: pd.DataFrame | None = None,
    spy_buy_hold: pd.DataFrame | None = None,
    spy_12m_momentum: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "windows": empty,
            "window_metrics": empty,
            "comparison": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    final_candidate, spy_buy_hold, spy_12m_momentum = _resolve_phase8c_input_frames(
        config=config,
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    names = phase_config.get("strategy_names", {})
    initial_capital = float(phase_config.get("initial_capital", 10000.0))

    inputs = [
        Phase8CInput(names.get("final_candidate", "Final candidate"), final_candidate),
        Phase8CInput(names.get("spy_buy_hold", "SPY Buy & Hold"), spy_buy_hold),
        Phase8CInput(names.get("spy_12m_momentum", "SPY 12M Momentum"), spy_12m_momentum),
    ]

    windows = build_phase8c_walk_forward_windows(final_candidate, phase_config)
    window_metrics = build_phase8c_window_metrics(
        inputs,
        windows,
        initial_capital=initial_capital,
    )
    comparison = build_phase8c_comparison(window_metrics, phase_config)
    summary = build_phase8c_summary(comparison)
    gate_report = build_phase8c_gate_report(summary, phase_config)
    conclusion = build_phase8c_conclusion(gate_report)

    windows.to_csv(reports_path / "phase8c_walk_forward_windows.csv", index=False)
    window_metrics.to_csv(
        reports_path / "phase8c_walk_forward_window_metrics.csv",
        index=False,
    )
    comparison.to_csv(
        reports_path / "phase8c_walk_forward_comparison.csv",
        index=False,
    )
    summary.to_csv(reports_path / "phase8c_walk_forward_summary.csv", index=False)
    gate_report.to_csv(
        reports_path / "phase8c_walk_forward_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase8c_walk_forward_conclusion.csv",
        index=False,
    )

    write_phase8c_markdown(
        windows=windows,
        window_metrics=window_metrics,
        comparison=comparison,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase8c_walk_forward_validation_audit.md",
    )

    print("Wrote Phase 8C walk-forward validation audit reports.")

    return {
        "windows": windows,
        "window_metrics": window_metrics,
        "comparison": comparison,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }