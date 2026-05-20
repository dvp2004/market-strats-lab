from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


DEFAULT_PHASE8D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "initial_capital": 10000.0,
    "strategy_names": {
        "final_candidate": "Final candidate",
        "spy_buy_hold": "SPY Buy & Hold",
        "spy_12m_momentum": "SPY 12M Momentum",
    },
    "rolling_windows_years": [1, 3, 5],
    "gates": {
        "min_terminal_relative_wealth_vs_buy_hold": 0.80,
        "max_time_lagging_buy_hold_rate": 0.75,
        "max_relative_drawdown_vs_buy_hold": 0.35,
        "max_longest_lagging_streak_years_vs_buy_hold": 7.0,
        "min_terminal_relative_wealth_vs_spy12m": 1.00,
        "max_time_lagging_spy12m_rate": 0.60,
        "max_rolling_3y_underperformance_rate_vs_buy_hold": 0.80,
        "min_worst_3y_active_cagr_vs_buy_hold": -0.10,
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
    user_config = config.get("phase8d_behavioural_regret_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE8D_CONFIG, user_config)


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
        raise ValueError("relative_momentum_outputs is required for Phase 8D.")

    if ticker_outputs is None:
        raise ValueError("ticker_outputs is required for Phase 8D.")

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
        raise ValueError("ticker_outputs must contain SPY for Phase 8D.")

    strategy_results = ticker_outputs["SPY"].get("strategy_results", {})

    if strategy_name not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"SPY strategy result {strategy_name!r} not found. Available: {available}"
        )

    return strategy_results[strategy_name]


def _resolve_phase8d_input_frames(
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


def _equity_curve(returns: pd.Series, initial_capital: float) -> pd.Series:
    clean_returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return initial_capital * (1.0 + clean_returns).cumprod()


def _period_years(start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    return max(0.0, (end_date - start_date).days / 365.25)


def _cagr(start_value: float, end_value: float, years: float) -> float:
    if years <= 0 or start_value <= 0:
        return 0.0

    return float((end_value / start_value) ** (1.0 / years) - 1.0)


def _max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def _longest_true_streak(mask: pd.Series) -> int:
    longest = 0
    current = 0

    for value in mask.astype(bool):
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return int(longest)


def _time_since_last_high_days(dates: pd.Series, relative_wealth: pd.Series) -> int:
    running_max = relative_wealth.cummax()
    high_mask = relative_wealth >= running_max

    if not high_mask.any():
        return int(len(relative_wealth))

    last_high_date = pd.to_datetime(dates[high_mask].iloc[-1])
    final_date = pd.to_datetime(dates.iloc[-1])

    return int((final_date - last_high_date).days)


def build_phase8d_daily_regret(
    *,
    final_candidate: pd.DataFrame,
    benchmarks: dict[str, pd.DataFrame],
    initial_capital: float,
) -> pd.DataFrame:
    candidate = _normalise_strategy_frame(final_candidate, "Final candidate")
    candidate_equity = _equity_curve(candidate["strategy_return"], initial_capital)

    rows: list[pd.DataFrame] = []

    for benchmark_name, benchmark_frame in benchmarks.items():
        benchmark = _normalise_strategy_frame(benchmark_frame, benchmark_name)

        merged = candidate[["date", "strategy_return"]].merge(
            benchmark[["date", "strategy_return"]],
            on="date",
            how="inner",
            suffixes=("_candidate", "_benchmark"),
        )

        if merged.empty:
            raise ValueError(f"No overlapping dates for benchmark {benchmark_name!r}.")

        merged["candidate_equity"] = _equity_curve(
            merged["strategy_return_candidate"],
            initial_capital,
        )
        merged["benchmark_equity"] = _equity_curve(
            merged["strategy_return_benchmark"],
            initial_capital,
        )
        merged["benchmark"] = benchmark_name
        merged["relative_wealth"] = (
            merged["candidate_equity"] / merged["benchmark_equity"]
        )
        merged["relative_wealth_minus_one"] = merged["relative_wealth"] - 1.0
        merged["relative_drawdown"] = (
            merged["relative_wealth"] / merged["relative_wealth"].cummax() - 1.0
        )
        merged["candidate_lagging_benchmark"] = (
            merged["candidate_equity"] < merged["benchmark_equity"]
        )
        merged["active_return"] = (
            merged["strategy_return_candidate"] - merged["strategy_return_benchmark"]
        )
        merged["candidate_full_equity_reference"] = candidate_equity.reindex(
            merged.index,
            method=None,
        )

        rows.append(
            merged[
                [
                    "date",
                    "benchmark",
                    "strategy_return_candidate",
                    "strategy_return_benchmark",
                    "active_return",
                    "candidate_equity",
                    "benchmark_equity",
                    "relative_wealth",
                    "relative_wealth_minus_one",
                    "relative_drawdown",
                    "candidate_lagging_benchmark",
                ]
            ]
        )

    return pd.concat(rows, ignore_index=True)


def build_phase8d_summary(daily_regret: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for benchmark_name, group in daily_regret.groupby("benchmark", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        start_date = pd.Timestamp(group["date"].iloc[0])
        end_date = pd.Timestamp(group["date"].iloc[-1])
        years = _period_years(start_date, end_date)

        lag_mask = group["candidate_lagging_benchmark"].astype(bool)
        longest_lagging_streak_days = _longest_true_streak(lag_mask)

        candidate_cagr = _cagr(
            float(group["candidate_equity"].iloc[0]),
            float(group["candidate_equity"].iloc[-1]),
            years,
        )
        benchmark_cagr = _cagr(
            float(group["benchmark_equity"].iloc[0]),
            float(group["benchmark_equity"].iloc[-1]),
            years,
        )

        rows.append(
            {
                "benchmark": benchmark_name,
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "period_years": years,
                "candidate_end_value": float(group["candidate_equity"].iloc[-1]),
                "benchmark_end_value": float(group["benchmark_equity"].iloc[-1]),
                "terminal_relative_wealth": float(group["relative_wealth"].iloc[-1]),
                "candidate_cagr": candidate_cagr,
                "benchmark_cagr": benchmark_cagr,
                "candidate_minus_benchmark_cagr": candidate_cagr - benchmark_cagr,
                "time_lagging_rate": float(lag_mask.mean()),
                "lagging_days": int(lag_mask.sum()),
                "longest_lagging_streak_days": longest_lagging_streak_days,
                "longest_lagging_streak_years": longest_lagging_streak_days / 252.0,
                "min_relative_wealth": float(group["relative_wealth"].min()),
                "max_relative_wealth": float(group["relative_wealth"].max()),
                "max_relative_drawdown": float(group["relative_drawdown"].min()),
                "time_since_last_relative_high_days": _time_since_last_high_days(
                    group["date"],
                    group["relative_wealth"],
                ),
            }
        )

    return pd.DataFrame(rows)


def _first_date_on_or_after(dates: pd.Series, target: pd.Timestamp) -> pd.Timestamp | None:
    candidates = dates[dates >= target]
    if candidates.empty:
        return None

    return pd.Timestamp(candidates.iloc[0])


def build_phase8d_rolling_regret(
    daily_regret: pd.DataFrame,
    *,
    rolling_windows_years: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for benchmark_name, group in daily_regret.groupby("benchmark", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        dates = pd.to_datetime(group["date"])

        for window_years in rolling_windows_years:
            for end_idx in range(len(group)):
                end_date = pd.Timestamp(dates.iloc[end_idx])
                start_target = end_date - pd.DateOffset(years=int(window_years))
                start_date = _first_date_on_or_after(dates, start_target)

                if start_date is None:
                    continue

                start_idx_candidates = group.index[dates == start_date]

                if len(start_idx_candidates) == 0:
                    continue

                start_idx = int(start_idx_candidates[0])

                if start_idx >= end_idx:
                    continue

                actual_years = _period_years(start_date, end_date)

                if actual_years < float(window_years) * 0.80:
                    continue

                candidate_start = float(group.loc[start_idx, "candidate_equity"])
                candidate_end = float(group.loc[end_idx, "candidate_equity"])
                benchmark_start = float(group.loc[start_idx, "benchmark_equity"])
                benchmark_end = float(group.loc[end_idx, "benchmark_equity"])

                candidate_cagr = _cagr(candidate_start, candidate_end, actual_years)
                benchmark_cagr = _cagr(benchmark_start, benchmark_end, actual_years)
                active_cagr = candidate_cagr - benchmark_cagr
                relative_wealth_change = (
                    (candidate_end / candidate_start)
                    / (benchmark_end / benchmark_start)
                    - 1.0
                )

                rows.append(
                    {
                        "benchmark": benchmark_name,
                        "window_years": int(window_years),
                        "start_date": start_date.date().isoformat(),
                        "end_date": end_date.date().isoformat(),
                        "period_years": actual_years,
                        "candidate_cagr": candidate_cagr,
                        "benchmark_cagr": benchmark_cagr,
                        "active_cagr": active_cagr,
                        "relative_wealth_change": relative_wealth_change,
                        "candidate_underperformed": active_cagr < 0,
                    }
                )

    return pd.DataFrame(rows)


def build_phase8d_rolling_summary(rolling_regret: pd.DataFrame) -> pd.DataFrame:
    if rolling_regret.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []

    for (benchmark_name, window_years), group in rolling_regret.groupby(
        ["benchmark", "window_years"],
        sort=False,
    ):
        rows.append(
            {
                "benchmark": benchmark_name,
                "window_years": int(window_years),
                "rolling_windows": int(len(group)),
                "underperformance_rate": float(group["candidate_underperformed"].mean()),
                "outperformance_rate": float((~group["candidate_underperformed"]).mean()),
                "mean_active_cagr": float(group["active_cagr"].mean()),
                "median_active_cagr": float(group["active_cagr"].median()),
                "worst_active_cagr": float(group["active_cagr"].min()),
                "best_active_cagr": float(group["active_cagr"].max()),
                "mean_relative_wealth_change": float(
                    group["relative_wealth_change"].mean()
                ),
                "worst_relative_wealth_change": float(
                    group["relative_wealth_change"].min()
                ),
            }
        )

    return pd.DataFrame(rows)


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _summary_value(summary: pd.DataFrame, benchmark: str, column: str) -> float:
    row = summary[summary["benchmark"] == benchmark]

    if row.empty:
        raise ValueError(f"Missing summary row for benchmark {benchmark!r}.")

    return float(row.iloc[0][column])


def _rolling_summary_value(
    rolling_summary: pd.DataFrame,
    benchmark: str,
    window_years: int,
    column: str,
) -> float:
    row = rolling_summary[
        (rolling_summary["benchmark"] == benchmark)
        & (rolling_summary["window_years"] == window_years)
    ]

    if row.empty:
        raise ValueError(
            f"Missing rolling summary for benchmark={benchmark!r}, "
            f"window_years={window_years}."
        )

    return float(row.iloc[0][column])


def build_phase8d_gate_report(
    summary: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    names = phase_config.get("strategy_names", {})
    gates = phase_config.get("gates", {})

    buy_hold_name = names.get("spy_buy_hold", "SPY Buy & Hold")
    spy_12m_name = names.get("spy_12m_momentum", "SPY 12M Momentum")

    min_terminal_bh = float(gates.get("min_terminal_relative_wealth_vs_buy_hold", 0.80))
    max_lag_bh = float(gates.get("max_time_lagging_buy_hold_rate", 0.75))
    max_rel_dd_bh = float(gates.get("max_relative_drawdown_vs_buy_hold", 0.35))
    max_streak_bh = float(
        gates.get("max_longest_lagging_streak_years_vs_buy_hold", 7.0)
    )
    min_terminal_12m = float(gates.get("min_terminal_relative_wealth_vs_spy12m", 1.00))
    max_lag_12m = float(gates.get("max_time_lagging_spy12m_rate", 0.60))
    max_rolling_3y_under_bh = float(
        gates.get("max_rolling_3y_underperformance_rate_vs_buy_hold", 0.80)
    )
    min_worst_3y_active_bh = float(
        gates.get("min_worst_3y_active_cagr_vs_buy_hold", -0.10)
    )

    terminal_bh = _summary_value(summary, buy_hold_name, "terminal_relative_wealth")
    lag_bh = _summary_value(summary, buy_hold_name, "time_lagging_rate")
    rel_dd_bh = _summary_value(summary, buy_hold_name, "max_relative_drawdown")
    streak_bh = _summary_value(summary, buy_hold_name, "longest_lagging_streak_years")

    terminal_12m = _summary_value(summary, spy_12m_name, "terminal_relative_wealth")
    lag_12m = _summary_value(summary, spy_12m_name, "time_lagging_rate")

    rolling_3y_under_bh = _rolling_summary_value(
        rolling_summary,
        buy_hold_name,
        3,
        "underperformance_rate",
    )
    worst_3y_active_bh = _rolling_summary_value(
        rolling_summary,
        buy_hold_name,
        3,
        "worst_active_cagr",
    )

    rows = [
        _gate_row(
            "Terminal relative wealth versus Buy & Hold remains tolerable",
            terminal_bh >= min_terminal_bh,
            f"{terminal_bh:.3f}; required >= {min_terminal_bh:.3f}",
        ),
        _gate_row(
            "Time lagging Buy & Hold is not excessive",
            lag_bh <= max_lag_bh,
            f"{lag_bh:.2%}; limit {max_lag_bh:.2%}",
        ),
        _gate_row(
            "Relative drawdown versus Buy & Hold is not excessive",
            abs(rel_dd_bh) <= max_rel_dd_bh,
            f"{rel_dd_bh:.2%}; limit -{max_rel_dd_bh:.2%}",
        ),
        _gate_row(
            "Longest lagging streak versus Buy & Hold is tolerable",
            streak_bh <= max_streak_bh,
            f"{streak_bh:.2f} years; limit {max_streak_bh:.2f}",
        ),
        _gate_row(
            "Terminal relative wealth versus SPY 12M remains favourable",
            terminal_12m >= min_terminal_12m,
            f"{terminal_12m:.3f}; required >= {min_terminal_12m:.3f}",
        ),
        _gate_row(
            "Time lagging SPY 12M is not excessive",
            lag_12m <= max_lag_12m,
            f"{lag_12m:.2%}; limit {max_lag_12m:.2%}",
        ),
        _gate_row(
            "3Y rolling underperformance versus Buy & Hold is not excessive",
            rolling_3y_under_bh <= max_rolling_3y_under_bh,
            f"{rolling_3y_under_bh:.2%}; limit {max_rolling_3y_under_bh:.2%}",
        ),
        _gate_row(
            "Worst 3Y active CAGR versus Buy & Hold is tolerable",
            worst_3y_active_bh >= min_worst_3y_active_bh,
            f"{worst_3y_active_bh:.2%}; required >= {min_worst_3y_active_bh:.2%}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase8d_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Survived with caveat"
        interpretation = (
            "The final candidate survived the configured behavioural regret audit. "
            "This supports liveability under the chosen regret thresholds, but it "
            "does not make the system production-ready."
        )
    else:
        verdict = "Failed / material behavioural regret"
        interpretation = (
            "The final candidate did not pass every behavioural regret gate. "
            "This means the investor experience versus benchmarks may be painful "
            "despite the defensive drawdown profile."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 8D",
                "diagnostic": "Behavioural / tracking-error regret audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase8d_markdown(
    summary: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 8D — Behavioural / Tracking-Error Regret Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit measures how painful the final candidate would feel versus "
            "SPY Buy & Hold and SPY 12M Momentum."
        ),
        "",
        "It is not a new strategy and it does not tune the final candidate.",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Rolling Regret Summary",
        "",
        rolling_summary.to_markdown(index=False),
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
        "- Behavioural regret thresholds are judgement-based.",
        "- This does not model a real investor's personal tolerance.",
        "- This is not a production-readiness test.",
        "- Failed gates should narrow the claim rather than trigger tuning.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase8d_behavioural_regret_audit(
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
            "daily_regret": empty,
            "summary": empty,
            "rolling_regret": empty,
            "rolling_summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    final_candidate, spy_buy_hold, spy_12m_momentum = _resolve_phase8d_input_frames(
        config=config,
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        spy_12m_momentum=spy_12m_momentum,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    names = phase_config.get("strategy_names", {})
    initial_capital = float(phase_config.get("initial_capital", 10000.0))

    benchmarks = {
        names.get("spy_buy_hold", "SPY Buy & Hold"): spy_buy_hold,
        names.get("spy_12m_momentum", "SPY 12M Momentum"): spy_12m_momentum,
    }

    daily_regret = build_phase8d_daily_regret(
        final_candidate=final_candidate,
        benchmarks=benchmarks,
        initial_capital=initial_capital,
    )
    summary = build_phase8d_summary(daily_regret)
    rolling_regret = build_phase8d_rolling_regret(
        daily_regret,
        rolling_windows_years=[
            int(value) for value in phase_config.get("rolling_windows_years", [1, 3, 5])
        ],
    )
    rolling_summary = build_phase8d_rolling_summary(rolling_regret)
    gate_report = build_phase8d_gate_report(summary, rolling_summary, phase_config)
    conclusion = build_phase8d_conclusion(gate_report)

    daily_regret.to_csv(reports_path / "phase8d_behavioural_regret_daily.csv", index=False)
    summary.to_csv(reports_path / "phase8d_behavioural_regret_summary.csv", index=False)
    rolling_regret.to_csv(
        reports_path / "phase8d_behavioural_regret_rolling_windows.csv",
        index=False,
    )
    rolling_summary.to_csv(
        reports_path / "phase8d_behavioural_regret_rolling_summary.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase8d_behavioural_regret_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase8d_behavioural_regret_conclusion.csv",
        index=False,
    )

    write_phase8d_markdown(
        summary=summary,
        rolling_summary=rolling_summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase8d_behavioural_regret_audit.md",
    )

    print("Wrote Phase 8D behavioural regret audit reports.")

    return {
        "daily_regret": daily_regret,
        "summary": summary,
        "rolling_regret": rolling_regret,
        "rolling_summary": rolling_summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }