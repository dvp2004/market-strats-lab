from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.regime_switch_overlay_offensive_relief_validation import (
    _create_overlay_for_variant as _create_offensive_relief_overlay_for_variant,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    _build_overlay_inputs,
    _slice_and_rebase_result,
)
from market_strats.strategies.regime_switch_overlay import (
    run_spy_trend_regime_switch_overlay,
)


def _phase6c_config(config: dict) -> dict:
    return config.get("phase6_final_candidate_decision", {})


def _segment_definitions(config: dict) -> list[dict]:
    phase_config = _phase6c_config(config)

    phase2_start_date = str(phase_config["pinned_phase2_start_date"])
    pinned_end_date = str(phase_config["pinned_end_date"])
    holdout_start_date = str(
        config.get("phase6_offensive_relief_validation", {}).get(
            "holdout_start_date",
            "2016-01-04",
        )
    )
    reference_end_date = str(
        config.get("phase6_offensive_relief_validation", {}).get(
            "reference_end_date",
            "2015-12-31",
        )
    )

    segments: list[dict] = [
        {
            "period": "full",
            "segment_type": "core",
            "start_date": phase2_start_date,
            "end_date": pinned_end_date,
        },
        {
            "period": "reference",
            "segment_type": "core",
            "start_date": phase2_start_date,
            "end_date": reference_end_date,
        },
        {
            "period": "holdout",
            "segment_type": "core",
            "start_date": holdout_start_date,
            "end_date": pinned_end_date,
        },
    ]

    source_segments = config.get("phase6_offensive_relief_validation", {}).get(
        "segments",
        [],
    )

    if not source_segments:
        source_segments = config.get("phase4_guard_promotion_validation", {}).get(
            "segments",
            [],
        )

    for segment in source_segments:
        segments.append(
            {
                "period": str(segment["name"]),
                "segment_type": "episode",
                "start_date": segment.get("start_date"),
                "end_date": segment.get("end_date"),
            }
        )

    return segments


def _normalise_result_frame(result: pd.DataFrame) -> pd.DataFrame:
    output = result.copy()

    if "date" not in output.columns:
        raise ValueError("Candidate result is missing date column")

    if "equity" not in output.columns:
        raise ValueError("Candidate result is missing equity column")

    output["date"] = pd.to_datetime(output["date"])
    output = output.sort_values("date").reset_index(drop=True)

    return output


def _result_has_required_columns(result: pd.DataFrame) -> bool:
    return {"date", "equity", "strategy_return"}.issubset(set(result.columns))


def _strategy_name_matches(value: str, required_terms: list[str], banned_terms: list[str]) -> bool:
    value_lower = value.lower()

    return all(term.lower() in value_lower for term in required_terms) and not any(
        term.lower() in value_lower for term in banned_terms
    )


def _find_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker: str,
    required_terms: list[str],
    banned_terms: list[str] | None = None,
) -> pd.DataFrame:
    banned_terms = banned_terms or []
    ticker = ticker.upper()

    if ticker not in ticker_outputs:
        raise ValueError(f"{ticker} not found in ticker_outputs")

    ticker_output = ticker_outputs[ticker]

    strategy_results = ticker_output.get("strategy_results")

    if isinstance(strategy_results, dict):
        exact_candidates: list[pd.DataFrame] = []
        loose_candidates: list[pd.DataFrame] = []

        for key, value in strategy_results.items():
            if not isinstance(value, pd.DataFrame):
                continue

            if not _result_has_required_columns(value):
                continue

            key_text = str(key)

            if _strategy_name_matches(key_text, required_terms, banned_terms):
                exact_candidates.append(value)
                continue

            if "strategy" in value.columns:
                strategy_values = value["strategy"].dropna().astype(str).unique()

                if any(
                    _strategy_name_matches(strategy_name, required_terms, banned_terms)
                    for strategy_name in strategy_values
                ):
                    loose_candidates.append(value)

            if "strategy_name" in value.columns:
                strategy_values = value["strategy_name"].dropna().astype(str).unique()

                if any(
                    _strategy_name_matches(strategy_name, required_terms, banned_terms)
                    for strategy_name in strategy_values
                ):
                    loose_candidates.append(value)

        if exact_candidates:
            return _normalise_result_frame(exact_candidates[0])

        if loose_candidates:
            return _normalise_result_frame(loose_candidates[0])

    for key in ["results", "data", "price_data"]:
        value = ticker_output.get(key)

        if isinstance(value, dict):
            for result_name, result in value.items():
                if not isinstance(result, pd.DataFrame):
                    continue

                if not _result_has_required_columns(result):
                    continue

                if _strategy_name_matches(str(result_name), required_terms, banned_terms):
                    return _normalise_result_frame(result)

    raise ValueError(
        f"Could not find strategy result for {ticker} with required terms "
        f"{required_terms} and banned terms {banned_terms}. Check ticker_outputs keys."
    )


def _find_relief_profile(config: dict, profile_name: str) -> dict:
    profiles = config.get("phase6_offensive_relief_validation", {}).get(
        "relief_profiles",
        [],
    )

    for profile in profiles:
        if str(profile["name"]) == profile_name:
            return profile

    raise ValueError(f"Could not find relief profile: {profile_name}")


def _create_phase3_flat_5bps_overlay(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    overlay_config = config.get("regime_switch_overlay", {})

    return run_spy_trend_regime_switch_overlay(
        offensive_result=offensive_result,
        defensive_result=defensive_result,
        initial_capital=float(config["initial_capital"]),
        trend_sma_days=int(overlay_config.get("trend_sma_days", 200)),
        slippage_bps=float(config.get("slippage_bps", 5.0)),
        confirmation_days=int(overlay_config.get("confirmation_days", 3)),
    )


def _create_candidate_results(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, dict]:
    phase_config = _phase6c_config(config)

    offensive_result, defensive_result = _build_overlay_inputs(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    final_variant = str(phase_config.get("final_candidate_variant", "loose_relief"))
    execution_benchmark_variant = str(
        phase_config.get("execution_benchmark_variant", "phase4_execution_candidate")
    )

    final_profile = _find_relief_profile(config=config, profile_name=final_variant)

    return {
        "SPY Buy & Hold": {
            "role": "Raw wealth benchmark",
            "result": _find_strategy_result(
                ticker_outputs=ticker_outputs,
                ticker="SPY",
                required_terms=["buy", "hold"],
                banned_terms=["momentum", "satellite", "core"],
            ),
        },
        "SPY 12M Momentum": {
            "role": "Simple defensive timing benchmark",
            "result": _find_strategy_result(
                ticker_outputs=ticker_outputs,
                ticker="SPY",
                required_terms=["12", "momentum"],
                banned_terms=["core", "satellite"],
            ),
        },
        "Phase 3 flat 5bps 3D overlay": {
            "role": "Original flat-slippage canonical overlay",
            "result": _create_phase3_flat_5bps_overlay(
                relative_momentum_outputs=relative_momentum_outputs,
                ticker_outputs=ticker_outputs,
                config=config,
            ),
        },
        "Phase 4 execution candidate": {
            "role": "Validated execution-realistic baseline",
            "result": _create_offensive_relief_overlay_for_variant(
                offensive_result=offensive_result,
                defensive_result=defensive_result,
                config=config,
                variant_name=execution_benchmark_variant,
                relief_profile=None,
            ),
        },
        "Phase 6B loose relief candidate": {
            "role": "Enhanced execution-realistic candidate",
            "result": _create_offensive_relief_overlay_for_variant(
                offensive_result=offensive_result,
                defensive_result=defensive_result,
                config=config,
                variant_name=final_variant,
                relief_profile=final_profile,
            ),
        },
    }


def _calculate_candidate_comparison(
    candidate_results: dict[str, dict],
    config: dict,
) -> pd.DataFrame:
    rows: list[dict] = []
    initial_capital = float(config["initial_capital"])
    segments = _segment_definitions(config)

    for candidate_name, candidate_info in candidate_results.items():
        result = _normalise_result_frame(candidate_info["result"])
        role = candidate_info["role"]

        for segment in segments:
            sliced = _slice_and_rebase_result(
                result=result,
                start_date=segment["start_date"],
                end_date=segment["end_date"],
                initial_capital=initial_capital,
            )

            if sliced.empty:
                continue

            metrics = calculate_metrics(sliced, candidate_name)

            rows.append(
                {
                    "period": segment["period"],
                    "segment_type": segment["segment_type"],
                    "candidate_name": candidate_name,
                    "candidate_role": role,
                    "start_date": metrics["start_date"],
                    "end_date": metrics["end_date"],
                    "end_value": metrics["end_value"],
                    "cagr_pct": metrics["cagr_pct"],
                    "calmar": metrics["calmar"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "volatility_pct": metrics["volatility_pct"],
                    "sharpe": metrics["sharpe"],
                    "sortino": metrics["sortino"],
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


def _get_metric_row(
    comparison: pd.DataFrame,
    period: str,
    candidate_name: str,
) -> pd.Series:
    rows = comparison[
        (comparison["period"] == period)
        & (comparison["candidate_name"] == candidate_name)
    ]

    if rows.empty:
        raise ValueError(f"Missing row for period={period}, candidate={candidate_name}")

    return rows.iloc[0]


def _create_delta_report(
    comparison: pd.DataFrame,
    final_candidate_name: str,
    benchmark_names: list[str],
) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    periods = comparison["period"].dropna().astype(str).unique().tolist()

    for period in periods:
        candidate_rows = comparison[
            (comparison["period"] == period)
            & (comparison["candidate_name"] == final_candidate_name)
        ]

        if candidate_rows.empty:
            continue

        candidate = candidate_rows.iloc[0]

        for benchmark_name in benchmark_names:
            benchmark_rows = comparison[
                (comparison["period"] == period)
                & (comparison["candidate_name"] == benchmark_name)
            ]

            if benchmark_rows.empty:
                continue

            benchmark = benchmark_rows.iloc[0]

            rows.append(
                {
                    "period": period,
                    "segment_type": candidate["segment_type"],
                    "candidate_name": final_candidate_name,
                    "benchmark_name": benchmark_name,
                    "candidate_cagr_pct": candidate["cagr_pct"],
                    "benchmark_cagr_pct": benchmark["cagr_pct"],
                    "cagr_delta_pct_points": round(
                        float(candidate["cagr_pct"]) - float(benchmark["cagr_pct"]),
                        3,
                    ),
                    "candidate_calmar": candidate["calmar"],
                    "benchmark_calmar": benchmark["calmar"],
                    "calmar_delta": round(
                        float(candidate["calmar"]) - float(benchmark["calmar"]),
                        3,
                    ),
                    "candidate_max_drawdown_pct": candidate["max_drawdown_pct"],
                    "benchmark_max_drawdown_pct": benchmark["max_drawdown_pct"],
                    "drawdown_delta_pct_points": round(
                        float(candidate["max_drawdown_pct"])
                        - float(benchmark["max_drawdown_pct"]),
                        3,
                    ),
                    "candidate_volatility_pct": candidate["volatility_pct"],
                    "benchmark_volatility_pct": benchmark["volatility_pct"],
                    "volatility_delta_pct_points": round(
                        float(candidate["volatility_pct"])
                        - float(benchmark["volatility_pct"]),
                        3,
                    ),
                    "candidate_trade_count": candidate["trade_count"],
                    "benchmark_trade_count": benchmark["trade_count"],
                    "trade_count_delta": int(candidate["trade_count"])
                    - int(benchmark["trade_count"]),
                }
            )

    return pd.DataFrame(rows)


def _create_final_gate_report(
    comparison: pd.DataFrame,
    delta_report: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()

    phase_config = _phase6c_config(config)

    final_candidate_name = "Phase 6B loose relief candidate"
    execution_benchmark_name = "Phase 4 execution candidate"
    phase3_name = "Phase 3 flat 5bps 3D overlay"

    min_cagr_improvement = float(
        phase_config.get(
            "min_cagr_improvement_vs_execution_benchmark_pct_points",
            0.30,
        )
    )
    min_calmar_improvement = float(
        phase_config.get("min_calmar_improvement_vs_execution_benchmark", 0.010)
    )
    max_drawdown_damage = float(
        phase_config.get("max_allowed_drawdown_damage_pct_points", -0.50)
    )
    max_holdout_cagr_damage = float(
        phase_config.get("max_allowed_holdout_cagr_damage_pct_points", -0.50)
    )
    max_holdout_calmar_damage = float(
        phase_config.get("max_allowed_holdout_calmar_damage", -0.05)
    )
    max_holdout_drawdown_damage = float(
        phase_config.get("max_allowed_holdout_drawdown_damage_pct_points", -0.50)
    )

    full_candidate = _get_metric_row(
        comparison=comparison,
        period="full",
        candidate_name=final_candidate_name,
    )
    full_execution = _get_metric_row(
        comparison=comparison,
        period="full",
        candidate_name=execution_benchmark_name,
    )
    holdout_candidate = _get_metric_row(
        comparison=comparison,
        period="holdout",
        candidate_name=final_candidate_name,
    )
    holdout_execution = _get_metric_row(
        comparison=comparison,
        period="holdout",
        candidate_name=execution_benchmark_name,
    )

    full_cagr_delta = round(
        float(full_candidate["cagr_pct"]) - float(full_execution["cagr_pct"]),
        3,
    )
    full_calmar_delta = round(
        float(full_candidate["calmar"]) - float(full_execution["calmar"]),
        3,
    )
    full_drawdown_delta = round(
        float(full_candidate["max_drawdown_pct"])
        - float(full_execution["max_drawdown_pct"]),
        3,
    )

    full_improves_execution = (
        full_cagr_delta >= min_cagr_improvement
        and full_calmar_delta >= min_calmar_improvement
        and full_drawdown_delta >= max_drawdown_damage
    )

    holdout_cagr_delta = round(
        float(holdout_candidate["cagr_pct"]) - float(holdout_execution["cagr_pct"]),
        3,
    )
    holdout_calmar_delta = round(
        float(holdout_candidate["calmar"]) - float(holdout_execution["calmar"]),
        3,
    )
    holdout_drawdown_delta = round(
        float(holdout_candidate["max_drawdown_pct"])
        - float(holdout_execution["max_drawdown_pct"]),
        3,
    )

    holdout_safe = (
        holdout_cagr_delta >= max_holdout_cagr_damage
        and holdout_calmar_delta >= max_holdout_calmar_damage
        and holdout_drawdown_delta >= max_holdout_drawdown_damage
    )

    episode_rows = delta_report[
        (delta_report["segment_type"] == "episode")
        & (delta_report["benchmark_name"] == execution_benchmark_name)
    ].copy()

    if episode_rows.empty:
        episode_safe = False
        episode_interpretation = "No episode-level delta rows were available."
    else:
        damaged = episode_rows[
            (episode_rows["cagr_delta_pct_points"].astype(float) < max_holdout_cagr_damage)
            | (episode_rows["calmar_delta"].astype(float) < max_holdout_calmar_damage)
            | (
                episode_rows["drawdown_delta_pct_points"].astype(float)
                < max_holdout_drawdown_damage
            )
        ]

        episode_safe = damaged.empty

        if damaged.empty:
            episode_interpretation = (
                "No episode segment breached the final damage thresholds."
            )
        else:
            damaged_periods = ", ".join(damaged["period"].astype(str).tolist())
            episode_interpretation = (
                f"Episode damage thresholds were breached in: {damaged_periods}."
            )

    pinned_spy_12m = phase_config["pinned_spy_12m_momentum"]
    beats_spy_12m = (
        float(full_candidate["cagr_pct"]) > float(pinned_spy_12m["cagr_pct"])
        and float(full_candidate["calmar"]) > float(pinned_spy_12m["calmar"])
        and float(full_candidate["max_drawdown_pct"])
        > float(pinned_spy_12m["max_drawdown_pct"])
    )

    pinned_spy_bh = phase_config["pinned_spy_buy_hold"]
    beats_spy_bh_raw = float(full_candidate["cagr_pct"]) > float(
        pinned_spy_bh["cagr_pct"]
    )

    phase3_row = _get_metric_row(
        comparison=comparison,
        period="full",
        candidate_name=phase3_name,
    )

    phase3_documented_separately = (
        round(float(phase3_row["cagr_pct"]), 2)
        == round(float(phase_config["pinned_phase3_flat_5bps"]["cagr_pct"]), 2)
    )

    final_promoted = (
        full_improves_execution
        and holdout_safe
        and episode_safe
        and beats_spy_12m
    )

    return pd.DataFrame(
        [
            {
                "gate": "Phase 6B candidate improves Phase 4 execution candidate full-period.",
                "status": "Passed" if full_improves_execution else "Failed",
                "evidence_quality": "Compared full-period CAGR, Calmar, and drawdown versus Phase 4 execution candidate",
                "interpretation": (
                    f"Full-period CAGR delta was {full_cagr_delta}, Calmar delta "
                    f"was {full_calmar_delta}, and drawdown delta was "
                    f"{full_drawdown_delta}."
                ),
            },
            {
                "gate": "Phase 6B candidate avoids holdout damage versus Phase 4 execution candidate.",
                "status": "Passed" if holdout_safe else "Failed",
                "evidence_quality": "Compared holdout CAGR, Calmar, and drawdown versus Phase 4 execution candidate",
                "interpretation": (
                    f"Holdout CAGR delta was {holdout_cagr_delta}, Calmar delta "
                    f"was {holdout_calmar_delta}, and drawdown delta was "
                    f"{holdout_drawdown_delta}."
                ),
            },
            {
                "gate": "Phase 6B candidate avoids material episode-level damage.",
                "status": "Passed" if episode_safe else "Failed",
                "evidence_quality": "Compared pre-declared episode deltas versus Phase 4 execution candidate",
                "interpretation": episode_interpretation,
            },
            {
                "gate": "Phase 6B candidate beats pinned SPY 12M strict full-period triple gate.",
                "status": "Passed" if beats_spy_12m else "Failed",
                "evidence_quality": "Compared against pinned SPY 12M CAGR, Calmar, and max drawdown gates",
                "interpretation": (
                    f"Candidate full-period result was {full_candidate['cagr_pct']}% "
                    f"CAGR, {full_candidate['calmar']} Calmar, and "
                    f"{full_candidate['max_drawdown_pct']}% max drawdown. "
                    f"SPY 12M gates are {pinned_spy_12m['cagr_pct']}% CAGR, "
                    f"{pinned_spy_12m['calmar']} Calmar, and "
                    f"{pinned_spy_12m['max_drawdown_pct']}% max drawdown."
                ),
            },
            {
                "gate": "Phase 6B candidate beats SPY Buy & Hold on raw CAGR.",
                "status": "Failed" if not beats_spy_bh_raw else "Passed",
                "evidence_quality": "Compared against pinned SPY Buy & Hold full-period CAGR",
                "interpretation": (
                    f"Candidate full-period CAGR was {full_candidate['cagr_pct']}%, "
                    f"while pinned SPY Buy & Hold CAGR was "
                    f"{pinned_spy_bh['cagr_pct']}%."
                ),
            },
            {
                "gate": "Phase 3 flat 5 bps canonical overlay remains separately documented.",
                "status": "Passed" if phase3_documented_separately else "Review",
                "evidence_quality": "Checked Phase 3 flat-cost result against pinned config",
                "interpretation": (
                    "The flat 5 bps Phase 3 overlay and the execution-realistic "
                    "Phase 6B candidate answer different assumptions and should "
                    "remain separately documented."
                ),
            },
            {
                "gate": "Phase 6B candidate can be promoted as best execution-realistic candidate.",
                "status": "Passed" if final_promoted else "Not yet",
                "evidence_quality": "Requires full-period improvement, holdout safety, episode safety, and SPY 12M gate survival",
                "interpretation": (
                    "Phase 6B loose_relief passed the final promotion decision gates."
                    if final_promoted
                    else "Phase 6B loose_relief did not pass all final promotion gates."
                ),
            },
        ]
    )


def _create_final_project_decision(gate_report: pd.DataFrame) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    final_gate = gate_report[
        gate_report["gate"]
        == "Phase 6B candidate can be promoted as best execution-realistic candidate."
    ]

    final_passed = not final_gate.empty and final_gate.iloc[0]["status"] == "Passed"

    return pd.DataFrame(
        [
            {
                "claim": "SPY Buy & Hold remains the raw wealth benchmark.",
                "status": "Survived",
                "evidence_quality": "Pinned benchmark comparison",
                "interpretation": (
                    "The project still does not claim to beat SPY Buy & Hold on raw "
                    "CAGR or terminal wealth."
                ),
            },
            {
                "claim": "SPY 12M remains the simple defensive timing benchmark.",
                "status": "Survived",
                "evidence_quality": "Pinned benchmark comparison",
                "interpretation": (
                    "SPY 12M remains the clean simple benchmark for defensive timing."
                ),
            },
            {
                "claim": "Phase 3 3D overlay remains the original flat-slippage canonical system.",
                "status": "Survived",
                "evidence_quality": "Flat 5 bps assumption remains separately documented",
                "interpretation": (
                    "The Phase 3 flat-cost overlay should not be silently replaced "
                    "by dynamic-cost variants."
                ),
            },
            {
                "claim": "Phase 4 deep_drawdown_guard remains the validated execution-realistic baseline.",
                "status": "Survived",
                "evidence_quality": "Phase 4F validation",
                "interpretation": (
                    "Phase 4 created the validated dynamic-slippage execution baseline."
                ),
            },
            {
                "claim": "Phase 6B loose_relief is promoted as the best execution-realistic candidate.",
                "status": "Survived" if final_passed else "Not yet",
                "evidence_quality": "Phase 6C final gate report",
                "interpretation": (
                    "Phase 6B loose_relief becomes the best execution-realistic "
                    "candidate."
                    if final_passed
                    else "Phase 6B loose_relief remains an advanced candidate but is "
                    "not promoted."
                ),
            },
            {
                "claim": "Breadth confirmation is rejected for promotion.",
                "status": "Survived",
                "evidence_quality": "Phase 5B materiality validation",
                "interpretation": (
                    "Breadth confirmation failed stricter materiality gates."
                ),
            },
            {
                "claim": "Defensive stress confirmation is rejected.",
                "status": "Survived",
                "evidence_quality": "Phase 6A validation",
                "interpretation": (
                    "Defensive volatility, return-shock, and stress filters worsened "
                    "or failed to materially improve the system."
                ),
            },
            {
                "claim": "Baseline relief is rejected despite stronger headline CAGR.",
                "status": "Survived",
                "evidence_quality": "Phase 6B candidate-level gate report",
                "interpretation": (
                    "Baseline relief had stronger headline CAGR but failed episode "
                    "damage and switch-count discipline."
                ),
            },
            {
                "claim": "The next step should be README update, commit, and checkpoint tag.",
                "status": "Survived",
                "evidence_quality": "Project discipline",
                "interpretation": (
                    "Further strategy testing before documentation would be feature "
                    "chasing."
                ),
            },
            {
                "claim": "Macro/sentiment/ML should start immediately.",
                "status": "Not yet",
                "evidence_quality": "Checkpoint not yet documented",
                "interpretation": (
                    "External data should wait until this final candidate decision is "
                    "documented and tagged."
                ),
            },
        ]
    )


def write_final_candidate_decision_markdown(
    comparison: pd.DataFrame,
    delta_report: pd.DataFrame,
    gate_report: pd.DataFrame,
    project_decision: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    full_comparison = comparison[comparison["period"] == "full"].copy()
    holdout_comparison = comparison[comparison["period"] == "holdout"].copy()
    episode_comparison = comparison[comparison["segment_type"] == "episode"].copy()

    content = f"""# Final Candidate Decision

This report compares the final candidate set and decides whether the Phase 6B loose-relief variant should be promoted as the best execution-realistic candidate.

## Candidate Set

- SPY Buy & Hold
- SPY 12M Momentum
- Phase 3 flat 5 bps 3D overlay
- Phase 4 execution candidate
- Phase 6B loose relief candidate

## Full-Period Comparison

{full_comparison.to_markdown(index=False) if not full_comparison.empty else "No full-period comparison available."}

## Holdout Comparison

{holdout_comparison.to_markdown(index=False) if not holdout_comparison.empty else "No holdout comparison available."}

## Episode Comparison

{episode_comparison.to_markdown(index=False) if not episode_comparison.empty else "No episode comparison available."}

## Delta Versus Benchmarks

{delta_report.to_markdown(index=False) if not delta_report.empty else "No delta report available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Final Project Decision

{project_decision.to_markdown(index=False) if not project_decision.empty else "No project decision available."}

## What Is Not Being Claimed

This project does not claim that the final execution-realistic candidate beats SPY Buy & Hold on raw wealth.

The Phase 3 flat 5 bps overlay remains separately documented because it answers a different execution-cost assumption.

The final candidate is still research-grade and not production-ready.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_regime_switch_overlay_final_candidate_decision(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase6c_config(config)

    if not phase_config.get("enabled", False):
        return {
            "comparison": pd.DataFrame(),
            "delta_report": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
            "project_decision": pd.DataFrame(),
        }

    candidate_results = _create_candidate_results(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    comparison = _calculate_candidate_comparison(
        candidate_results=candidate_results,
        config=config,
    )

    final_candidate_name = "Phase 6B loose relief candidate"
    benchmark_names = [
        "SPY Buy & Hold",
        "SPY 12M Momentum",
        "Phase 3 flat 5bps 3D overlay",
        "Phase 4 execution candidate",
    ]

    delta_report = _create_delta_report(
        comparison=comparison,
        final_candidate_name=final_candidate_name,
        benchmark_names=benchmark_names,
    )

    gate_report = _create_final_gate_report(
        comparison=comparison,
        delta_report=delta_report,
        config=config,
    )

    project_decision = _create_final_project_decision(gate_report)

    return {
        "comparison": comparison,
        "delta_report": delta_report,
        "gate_report": gate_report,
        "project_decision": project_decision,
    }


def save_regime_switch_overlay_final_candidate_decision(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_regime_switch_overlay_final_candidate_decision(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    comparison = outputs["comparison"]
    delta_report = outputs["delta_report"]
    gate_report = outputs["gate_report"]
    project_decision = outputs["project_decision"]

    if comparison.empty:
        return outputs

    comparison_path = reports_dir / "final_candidate_comparison.csv"
    delta_path = reports_dir / "final_candidate_delta_vs_benchmarks.csv"
    gate_path = reports_dir / "final_candidate_gate_report.csv"
    decision_path = reports_dir / "final_project_decision.csv"
    markdown_path = reports_dir / "final_candidate_decision.md"

    comparison.to_csv(comparison_path, index=False)
    delta_report.to_csv(delta_path, index=False)
    gate_report.to_csv(gate_path, index=False)
    project_decision.to_csv(decision_path, index=False)

    write_final_candidate_decision_markdown(
        comparison=comparison,
        delta_report=delta_report,
        gate_report=gate_report,
        project_decision=project_decision,
        output_path=markdown_path,
    )

    print("\nFinal candidate comparison:")
    print(comparison.to_string(index=False))

    print("\nFinal candidate delta versus benchmarks:")
    print(delta_report.to_string(index=False))

    print("\nFinal candidate gate report:")
    print(gate_report.to_string(index=False))

    print("\nFinal project decision:")
    print(project_decision.to_string(index=False))

    print(f"\nSaved final candidate comparison to: {comparison_path}")
    print(f"Saved final candidate delta report to: {delta_path}")
    print(f"Saved final candidate gate report to: {gate_path}")
    print(f"Saved final project decision to: {decision_path}")
    print(f"Saved final candidate decision markdown to: {markdown_path}")

    return outputs