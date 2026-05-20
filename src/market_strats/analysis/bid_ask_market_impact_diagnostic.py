from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


DEFAULT_PHASE8B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "initial_capital": 10000.0,
    "gate_scenario": "stress",
    "strategy_names": {
        "final_candidate": "Final candidate",
        "spy_buy_hold": "SPY Buy & Hold",
        "spy_12m_momentum": "SPY 12M Momentum",
    },
    "gates": {
        "candidate_must_beat_spy12m_cagr": True,
        "candidate_must_beat_spy12m_calmar": True,
        "candidate_must_have_better_spy12m_drawdown": True,
        "candidate_must_not_beat_buy_hold_raw_cagr": True,
        "candidate_must_beat_buy_hold_calmar": True,
        "candidate_must_have_better_buy_hold_drawdown": True,
        "max_candidate_cagr_degradation_pts_vs_no_extra_cost": 0.50,
    },
    "scenarios": {
        "no_extra_cost": {
            "spread_bps": 0.0,
            "impact_bps_per_100pct_turnover": 0.0,
            "stress_drawdown_threshold": -0.10,
            "deep_stress_drawdown_threshold": -0.20,
            "stress_multiplier": 1.0,
            "deep_stress_multiplier": 1.0,
        },
        "moderate": {
            "spread_bps": 2.5,
            "impact_bps_per_100pct_turnover": 5.0,
            "stress_drawdown_threshold": -0.10,
            "deep_stress_drawdown_threshold": -0.20,
            "stress_multiplier": 2.0,
            "deep_stress_multiplier": 3.0,
        },
        "stress": {
            "spread_bps": 5.0,
            "impact_bps_per_100pct_turnover": 10.0,
            "stress_drawdown_threshold": -0.10,
            "deep_stress_drawdown_threshold": -0.20,
            "stress_multiplier": 3.0,
            "deep_stress_multiplier": 5.0,
        },
        "severe": {
            "spread_bps": 10.0,
            "impact_bps_per_100pct_turnover": 20.0,
            "stress_drawdown_threshold": -0.10,
            "deep_stress_drawdown_threshold": -0.20,
            "stress_multiplier": 4.0,
            "deep_stress_multiplier": 8.0,
        },
    },
}


@dataclass(frozen=True)
class Phase8BInput:
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
    user_config = config.get("phase8b_bid_ask_market_impact_diagnostic", {})
    return _deep_merge_dict(DEFAULT_PHASE8B_CONFIG, user_config)


def _normalise_strategy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"date", "strategy_return"}
    missing = required_columns.difference(frame.columns)

    if missing:
        raise ValueError(f"Missing required strategy columns: {sorted(missing)}")

    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    out["strategy_return"] = pd.to_numeric(
        out["strategy_return"],
        errors="coerce",
    ).fillna(0.0)

    if "turnover" in out.columns:
        turnover = out["turnover"]
    elif "overlay_turnover" in out.columns:
        turnover = out["overlay_turnover"]
    else:
        turnover = pd.Series(0.0, index=out.index)

    out["turnover_for_phase8b"] = pd.to_numeric(
        turnover,
        errors="coerce",
    ).fillna(0.0)
    out["turnover_for_phase8b"] = out["turnover_for_phase8b"].clip(lower=0.0)

    return out


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
    running_max = equity.cummax()
    return equity / running_max - 1.0


def _max_drawdown(equity: pd.Series) -> float:
    return float(_drawdown(equity).min())


def _cagr(equity: pd.Series, dates: pd.Series) -> float:
    clean_dates = pd.to_datetime(dates).dropna().sort_values()

    if len(clean_dates) < 2 or equity.empty:
        return 0.0

    years = (clean_dates.iloc[-1] - clean_dates.iloc[0]).days / 365.25

    if years <= 0 or equity.iloc[0] <= 0:
        return 0.0

    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def _volatility(returns: pd.Series, dates: pd.Series) -> float:
    periods_per_year = _infer_periods_per_year(dates)
    clean_returns = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return float(clean_returns.std(ddof=0) * np.sqrt(periods_per_year))


def _calmar(cagr: float, max_drawdown: float) -> float:
    if max_drawdown >= 0:
        return np.nan

    return float(cagr / abs(max_drawdown))


def _trade_count(turnover: pd.Series) -> int:
    return int((pd.to_numeric(turnover, errors="coerce").fillna(0.0) > 0).sum())


def _stress_multiplier(drawdowns: pd.Series, scenario: dict[str, Any]) -> pd.Series:
    stress_threshold = float(scenario.get("stress_drawdown_threshold", -0.10))
    deep_threshold = float(scenario.get("deep_stress_drawdown_threshold", -0.20))
    stress_multiplier = float(scenario.get("stress_multiplier", 1.0))
    deep_multiplier = float(scenario.get("deep_stress_multiplier", stress_multiplier))

    multiplier = pd.Series(1.0, index=drawdowns.index)
    multiplier = multiplier.mask(drawdowns <= stress_threshold, stress_multiplier)
    multiplier = multiplier.mask(drawdowns <= deep_threshold, deep_multiplier)

    return multiplier


def _find_final_candidate_frame(
    relative_momentum_outputs: dict[str, Any] | None,
    ticker_outputs: dict[str, Any] | None,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Reconstruct the Phase 6B loose_relief final candidate.

    The final candidate is not stored directly inside relative_momentum_outputs
    or ticker_outputs. Those containers only hold allocator outputs and
    single-ticker strategy results. Phase 8B must rebuild the audited final
    candidate the same way Phase 7B and Phase 8A do.
    """
    if relative_momentum_outputs is None:
        raise ValueError("relative_momentum_outputs is required to reconstruct final candidate.")

    if ticker_outputs is None:
        raise ValueError("ticker_outputs is required to reconstruct final candidate.")

    final_candidate = _create_audited_overlay_result(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    ).copy()

    required_columns = {"date", "strategy_return", "equity"}
    missing_columns = required_columns - set(final_candidate.columns)

    if missing_columns:
        raise ValueError(
            "Reconstructed Phase 6B final candidate is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    final_candidate["date"] = pd.to_datetime(final_candidate["date"])

    return final_candidate.sort_values("date").reset_index(drop=True)


def _get_spy_strategy_result(
    ticker_outputs: dict[str, Any] | None,
    strategy_name: str,
) -> pd.DataFrame:
    if not ticker_outputs or "SPY" not in ticker_outputs:
        raise ValueError("ticker_outputs must contain SPY for Phase 8B benchmark extraction.")

    spy_outputs = ticker_outputs["SPY"]
    strategy_results = spy_outputs.get("strategy_results", {})

    if strategy_name not in strategy_results:
        available = sorted(strategy_results.keys())
        raise ValueError(
            f"SPY strategy result {strategy_name!r} not found. Available: {available}"
        )

    return strategy_results[strategy_name]

def _align_frame_to_period(
    frame: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    strategy_name: str,
) -> pd.DataFrame:
    if "date" not in frame.columns:
        raise ValueError(f"{strategy_name} is missing date column.")

    aligned = frame.copy()
    aligned["date"] = pd.to_datetime(aligned["date"])
    aligned = aligned[
        (aligned["date"] >= start_date) & (aligned["date"] <= end_date)
    ].copy()
    aligned = aligned.sort_values("date").reset_index(drop=True)

    if aligned.empty:
        raise ValueError(
            f"{strategy_name} has no rows after aligning to "
            f"{start_date.date()} through {end_date.date()}."
        )

    if "strategy_return" not in aligned.columns:
        raise ValueError(f"{strategy_name} is missing strategy_return column.")

    aligned["strategy_return"] = pd.to_numeric(
        aligned["strategy_return"],
        errors="coerce",
    ).fillna(0.0)

    aligned.loc[aligned.index[0], "strategy_return"] = 0.0

    return aligned

def _resolve_phase8b_input_frames(
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


def apply_bid_ask_market_impact_scenario(
    frame: pd.DataFrame,
    *,
    strategy_name: str,
    scenario_name: str,
    scenario: dict[str, Any],
    initial_capital: float,
) -> pd.DataFrame:
    out = _normalise_strategy_frame(frame)

    base_equity = _equity_curve(out["strategy_return"], initial_capital)
    base_drawdown = _drawdown(base_equity)
    turnover = out["turnover_for_phase8b"]

    spread_bps = float(scenario.get("spread_bps", 0.0))
    impact_bps_per_100pct_turnover = float(
        scenario.get("impact_bps_per_100pct_turnover", 0.0)
    )

    multiplier = _stress_multiplier(base_drawdown, scenario)
    effective_spread_bps = spread_bps * multiplier
    effective_impact_bps = impact_bps_per_100pct_turnover * turnover * multiplier
    effective_total_bps = effective_spread_bps + effective_impact_bps

    extra_cost = turnover * effective_total_bps / 10000.0
    adjusted_return = out["strategy_return"] - extra_cost
    adjusted_equity = _equity_curve(adjusted_return, initial_capital)

    result = pd.DataFrame(
        {
            "date": out["date"],
            "strategy": strategy_name,
            "scenario": scenario_name,
            "base_strategy_return": out["strategy_return"],
            "adjusted_strategy_return": adjusted_return,
            "turnover": turnover,
            "base_equity": base_equity,
            "base_drawdown": base_drawdown,
            "stress_multiplier": multiplier,
            "effective_spread_bps": effective_spread_bps,
            "effective_impact_bps": effective_impact_bps,
            "effective_total_cost_bps": effective_total_bps,
            "extra_cost_return": extra_cost,
            "adjusted_equity": adjusted_equity,
        }
    )

    result["adjusted_drawdown"] = _drawdown(result["adjusted_equity"])

    return result


def _metric_row(daily: pd.DataFrame, *, initial_capital: float) -> dict[str, Any]:
    adjusted_equity = daily["adjusted_equity"]
    adjusted_return = daily["adjusted_strategy_return"]
    base_equity = daily["base_equity"]

    cagr = _cagr(adjusted_equity, daily["date"])
    max_dd = _max_drawdown(adjusted_equity)
    base_cagr = _cagr(base_equity, daily["date"])
    total_extra_cost = float(daily["extra_cost_return"].sum())
    elapsed_years = (
        pd.to_datetime(daily["date"]).iloc[-1] - pd.to_datetime(daily["date"]).iloc[0]
    ).days / 365.25
    avg_annual_extra_drag = total_extra_cost / max(1e-12, elapsed_years)

    return {
        "strategy": daily["strategy"].iloc[0],
        "scenario": daily["scenario"].iloc[0],
        "start_date": pd.to_datetime(daily["date"].iloc[0]).date().isoformat(),
        "end_date": pd.to_datetime(daily["date"].iloc[-1]).date().isoformat(),
        "end_value": float(adjusted_equity.iloc[-1]),
        "cagr": cagr,
        "base_cagr": base_cagr,
        "cagr_delta_vs_no_extra_cost": cagr - base_cagr,
        "volatility": _volatility(adjusted_return, daily["date"]),
        "max_drawdown": max_dd,
        "calmar": _calmar(cagr, max_dd),
        "total_turnover": float(daily["turnover"].sum()),
        "trade_count": _trade_count(daily["turnover"]),
        "total_extra_cost_return": total_extra_cost,
        "avg_annual_extra_drag": avg_annual_extra_drag,
        "initial_capital": initial_capital,
    }


def build_phase8b_daily_returns(
    inputs: list[Phase8BInput],
    *,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    initial_capital = float(phase_config.get("initial_capital", 10000.0))
    scenarios = phase_config.get("scenarios", {})

    if not scenarios:
        raise ValueError("Phase 8B requires at least one scenario.")

    daily_frames = []

    for item in inputs:
        for scenario_name, scenario in scenarios.items():
            daily_frames.append(
                apply_bid_ask_market_impact_scenario(
                    item.returns,
                    strategy_name=item.name,
                    scenario_name=scenario_name,
                    scenario=scenario,
                    initial_capital=initial_capital,
                )
            )

    return pd.concat(daily_frames, ignore_index=True)


def build_phase8b_metrics(
    daily_returns: pd.DataFrame,
    *,
    initial_capital: float,
) -> pd.DataFrame:
    rows = []

    for _, group in daily_returns.groupby(["strategy", "scenario"], sort=False):
        rows.append(_metric_row(group.reset_index(drop=True), initial_capital=initial_capital))

    return pd.DataFrame(rows)


def build_phase8b_summary(metrics: pd.DataFrame, phase_config: dict[str, Any]) -> pd.DataFrame:
    names = phase_config.get("strategy_names", {})
    candidate_name = names.get("final_candidate", "Final candidate")
    spy_bh_name = names.get("spy_buy_hold", "SPY Buy & Hold")
    spy_12m_name = names.get("spy_12m_momentum", "SPY 12M Momentum")

    rows = []

    for scenario in metrics["scenario"].drop_duplicates():
        scenario_metrics = metrics[metrics["scenario"] == scenario].set_index("strategy")

        if not {candidate_name, spy_bh_name, spy_12m_name}.issubset(
            scenario_metrics.index
        ):
            continue

        candidate = scenario_metrics.loc[candidate_name]
        spy_bh = scenario_metrics.loc[spy_bh_name]
        spy_12m = scenario_metrics.loc[spy_12m_name]

        rows.append(
            {
                "scenario": scenario,
                "candidate_cagr": candidate["cagr"],
                "spy_12m_cagr": spy_12m["cagr"],
                "buy_hold_cagr": spy_bh["cagr"],
                "candidate_minus_spy_12m_cagr": candidate["cagr"] - spy_12m["cagr"],
                "candidate_minus_buy_hold_cagr": candidate["cagr"] - spy_bh["cagr"],
                "candidate_calmar": candidate["calmar"],
                "spy_12m_calmar": spy_12m["calmar"],
                "buy_hold_calmar": spy_bh["calmar"],
                "candidate_minus_spy_12m_calmar": (
                    candidate["calmar"] - spy_12m["calmar"]
                ),
                "candidate_minus_buy_hold_calmar": (
                    candidate["calmar"] - spy_bh["calmar"]
                ),
                "candidate_max_drawdown": candidate["max_drawdown"],
                "spy_12m_max_drawdown": spy_12m["max_drawdown"],
                "buy_hold_max_drawdown": spy_bh["max_drawdown"],
                "candidate_drawdown_advantage_vs_spy_12m": (
                    candidate["max_drawdown"] - spy_12m["max_drawdown"]
                ),
                "candidate_drawdown_advantage_vs_buy_hold": (
                    candidate["max_drawdown"] - spy_bh["max_drawdown"]
                ),
                "candidate_cagr_degradation_pts": -candidate[
                    "cagr_delta_vs_no_extra_cost"
                ],
                "candidate_avg_annual_extra_drag": candidate["avg_annual_extra_drag"],
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


def build_phase8b_gate_report(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    del summary

    names = phase_config.get("strategy_names", {})
    gates = phase_config.get("gates", {})
    gate_scenario = phase_config.get("gate_scenario", "stress")

    candidate_name = names.get("final_candidate", "Final candidate")
    spy_bh_name = names.get("spy_buy_hold", "SPY Buy & Hold")
    spy_12m_name = names.get("spy_12m_momentum", "SPY 12M Momentum")

    scenario_metrics = metrics[metrics["scenario"] == gate_scenario].set_index("strategy")

    if not {candidate_name, spy_bh_name, spy_12m_name}.issubset(
        scenario_metrics.index
    ):
        raise ValueError(f"Gate scenario {gate_scenario!r} is missing required strategies.")

    candidate = scenario_metrics.loc[candidate_name]
    spy_bh = scenario_metrics.loc[spy_bh_name]
    spy_12m = scenario_metrics.loc[spy_12m_name]

    no_extra = metrics[
        (metrics["strategy"] == candidate_name) & (metrics["scenario"] == "no_extra_cost")
    ]

    if no_extra.empty:
        candidate_cagr_degradation = -float(candidate["cagr_delta_vs_no_extra_cost"])
    else:
        candidate_cagr_degradation = float(no_extra.iloc[0]["cagr"] - candidate["cagr"])

    max_degradation = float(
        gates.get("max_candidate_cagr_degradation_pts_vs_no_extra_cost", 0.50)
    )
    max_degradation_decimal = max_degradation / 100.0

    rows = [
        _gate_row(
            "Candidate beats SPY 12M on CAGR under gate scenario",
            float(candidate["cagr"]) > float(spy_12m["cagr"]),
            f"{candidate['cagr']:.4%} vs {spy_12m['cagr']:.4%} under {gate_scenario}",
        ),
        _gate_row(
            "Candidate beats SPY 12M on Calmar under gate scenario",
            float(candidate["calmar"]) > float(spy_12m["calmar"]),
            f"{candidate['calmar']:.3f} vs {spy_12m['calmar']:.3f}",
        ),
        _gate_row(
            "Candidate has better max drawdown than SPY 12M under gate scenario",
            float(candidate["max_drawdown"]) > float(spy_12m["max_drawdown"]),
            f"{candidate['max_drawdown']:.2%} vs {spy_12m['max_drawdown']:.2%}",
        ),
        _gate_row(
            "Candidate does not become raw-CAGR winner over Buy & Hold",
            float(candidate["cagr"]) < float(spy_bh["cagr"]),
            f"{candidate['cagr']:.4%} vs {spy_bh['cagr']:.4%}",
        ),
        _gate_row(
            "Candidate beats Buy & Hold on Calmar under gate scenario",
            float(candidate["calmar"]) > float(spy_bh["calmar"]),
            f"{candidate['calmar']:.3f} vs {spy_bh['calmar']:.3f}",
        ),
        _gate_row(
            "Candidate has better max drawdown than Buy & Hold under gate scenario",
            float(candidate["max_drawdown"]) > float(spy_bh["max_drawdown"]),
            f"{candidate['max_drawdown']:.2%} vs {spy_bh['max_drawdown']:.2%}",
        ),
        _gate_row(
            "Candidate CAGR degradation versus no-extra-cost case is not excessive",
            candidate_cagr_degradation <= max_degradation_decimal,
            f"degradation {candidate_cagr_degradation:.4%}; "
            f"limit {max_degradation_decimal:.4%}",
        ),
    ]

    gate_report = pd.DataFrame(rows)

    gate_report.loc[:, "gate_scenario"] = gate_scenario
    gate_report.loc[:, "all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase8b_conclusion(gate_report: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if all_passed:
        verdict = "Survived with caveat"
        interpretation = (
            "The final candidate survived the configured bid-ask / market-impact "
            "stress diagnostic, but this is still a scenario test rather than "
            "production execution modelling."
        )
    else:
        verdict = "Weakened / failed configured stress gate"
        interpretation = (
            "The final candidate did not survive every configured bid-ask / "
            "market-impact stress gate. This should narrow the execution-realistic "
            "claim rather than trigger immediate threshold tuning."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 8B",
                "diagnostic": "Bid-ask / market-impact stress diagnostic",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase8b_markdown(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 8B — Bid-Ask / Market-Impact Stress Diagnostic",
        "",
        "## Purpose",
        "",
        (
            "This diagnostic tests whether the final candidate survives additional "
            "scenario-based spread and market-impact costs on turnover days."
        ),
        "",
        "It is not a new strategy and it does not tune the final candidate.",
        "",
        "## Scenario Metrics",
        "",
        metrics.to_markdown(index=False),
        "",
        "## Scenario Summary",
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
        "- This is not a production execution simulator.",
        "- It does not model order books, intraday liquidity, broker routing, or fills.",
        "- It applies scenario costs mechanically to turnover days.",
        "- It should narrow claims if the candidate weakens.",
        "- It should not be used as an excuse to tune thresholds.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase8b_bid_ask_market_impact_diagnostic(
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
            "daily_returns": empty,
            "metrics": empty,
            "summary": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    final_candidate, spy_buy_hold, spy_12m_momentum = _resolve_phase8b_input_frames(
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
        Phase8BInput(names.get("final_candidate", "Final candidate"), final_candidate),
        Phase8BInput(names.get("spy_buy_hold", "SPY Buy & Hold"), spy_buy_hold),
        Phase8BInput(names.get("spy_12m_momentum", "SPY 12M Momentum"), spy_12m_momentum),
    ]

    daily_returns = build_phase8b_daily_returns(inputs, phase_config=phase_config)
    metrics = build_phase8b_metrics(daily_returns, initial_capital=initial_capital)
    summary = build_phase8b_summary(metrics, phase_config)
    gate_report = build_phase8b_gate_report(metrics, summary, phase_config)
    conclusion = build_phase8b_conclusion(gate_report)

    daily_returns.to_csv(
        reports_path / "phase8b_bid_ask_market_impact_daily_returns.csv",
        index=False,
    )
    metrics.to_csv(reports_path / "phase8b_bid_ask_market_impact_metrics.csv", index=False)
    summary.to_csv(reports_path / "phase8b_bid_ask_market_impact_summary.csv", index=False)
    gate_report.to_csv(
        reports_path / "phase8b_bid_ask_market_impact_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase8b_bid_ask_market_impact_conclusion.csv",
        index=False,
    )

    write_phase8b_markdown(
        metrics=metrics,
        summary=summary,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase8b_bid_ask_market_impact_diagnostic.md",
    )

    print("Wrote Phase 8B bid-ask / market-impact diagnostic reports.")

    return {
        "daily_returns": daily_returns,
        "metrics": metrics,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }