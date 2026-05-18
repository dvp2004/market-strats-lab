from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_audited_overlay_result,
)


TRADING_DAYS_PER_YEAR = 252


def _phase7d_config(config: dict) -> dict:
    return config.get("phase7_bootstrap_statistical_robustness", {})


def _get_spy_strategy_result(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    strategy_name: str,
) -> pd.DataFrame:
    spy_output = ticker_outputs.get("SPY")

    if spy_output is None:
        raise ValueError("SPY output missing from ticker_outputs")

    strategy_results = spy_output.get("strategy_results")

    if not isinstance(strategy_results, dict):
        raise ValueError("SPY strategy_results missing or invalid")

    if strategy_name not in strategy_results:
        raise ValueError(
            f"SPY strategy result missing: {strategy_name}. "
            f"Available: {sorted(strategy_results)}"
        )

    result = strategy_results[strategy_name].copy()
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)

    return result


def _normalise_return_series(
    result: pd.DataFrame,
    strategy_name: str,
    return_column_name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    required = {"date", "strategy_return"}
    missing = required - set(result.columns)

    if missing:
        raise ValueError(f"{strategy_name} missing columns: {sorted(missing)}")

    output = result[["date", "strategy_return"]].copy()
    output["date"] = pd.to_datetime(output["date"])
    output = output[
        (output["date"] >= pd.Timestamp(start_date))
        & (output["date"] <= pd.Timestamp(end_date))
    ].copy()

    output = output.rename(columns={"strategy_return": return_column_name})
    output[return_column_name] = pd.to_numeric(
        output[return_column_name],
        errors="coerce",
    )

    return output.dropna().sort_values("date").reset_index(drop=True)


def _create_bootstrap_input_returns(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7d_config(config)

    start_date = str(phase_config.get("pinned_start_date", "2006-04-28"))
    end_date = str(phase_config.get("pinned_end_date", "2026-05-01"))

    candidate_result = _create_audited_overlay_result(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    spy_buy_hold = _get_spy_strategy_result(
        ticker_outputs=ticker_outputs,
        strategy_name="Buy and Hold",
    )
    spy_12m = _get_spy_strategy_result(
        ticker_outputs=ticker_outputs,
        strategy_name="12-Month Absolute Momentum",
    )

    candidate_returns = _normalise_return_series(
        result=candidate_result,
        strategy_name="candidate",
        return_column_name="candidate_return",
        start_date=start_date,
        end_date=end_date,
    )
    buy_hold_returns = _normalise_return_series(
        result=spy_buy_hold,
        strategy_name="SPY Buy and Hold",
        return_column_name="buy_hold_return",
        start_date=start_date,
        end_date=end_date,
    )
    spy_12m_returns = _normalise_return_series(
        result=spy_12m,
        strategy_name="SPY 12M Absolute Momentum",
        return_column_name="spy_12m_return",
        start_date=start_date,
        end_date=end_date,
    )

    merged = candidate_returns.merge(buy_hold_returns, on="date", how="inner")
    merged = merged.merge(spy_12m_returns, on="date", how="inner")
    merged = merged.sort_values("date").reset_index(drop=True)

    if merged.empty:
        raise ValueError("No overlapping return rows for bootstrap input")

    return merged


def _bootstrap_block_indices(
    n_rows: int,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n_rows <= 0:
        raise ValueError("n_rows must be positive")

    if block_length <= 0:
        raise ValueError("block_length must be positive")

    indices: list[int] = []

    while len(indices) < n_rows:
        start_idx = int(rng.integers(0, n_rows))
        block = [(start_idx + offset) % n_rows for offset in range(block_length)]
        indices.extend(block)

    return np.asarray(indices[:n_rows], dtype=int)


def _metrics_from_returns(
    returns: np.ndarray,
    initial_capital: float,
) -> dict[str, float]:
    if len(returns) == 0:
        raise ValueError("returns cannot be empty")

    equity = initial_capital * np.cumprod(1.0 + returns)
    ending_value = float(equity[-1])

    years = len(returns) / TRADING_DAYS_PER_YEAR

    if ending_value <= 0:
        cagr_pct = -100.0
    else:
        cagr_pct = ((ending_value / initial_capital) ** (1.0 / years) - 1.0) * 100.0

    rolling_high = np.maximum.accumulate(equity)
    drawdowns = (equity / rolling_high) - 1.0
    max_drawdown_pct = float(drawdowns.min() * 100.0)

    if max_drawdown_pct == 0:
        calmar = np.nan
    else:
        calmar = float(cagr_pct / abs(max_drawdown_pct))

    return {
        "end_value": ending_value,
        "cagr_pct": float(cagr_pct),
        "max_drawdown_pct": max_drawdown_pct,
        "calmar": calmar,
    }


def _create_bootstrap_samples(
    returns: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7d_config(config)

    bootstrap_iterations = int(phase_config.get("bootstrap_iterations", 500))
    block_length = int(phase_config.get("block_length_days", 21))
    random_seed = int(phase_config.get("random_seed", 42))
    initial_capital = float(phase_config.get("initial_capital", 10000.0))

    rng = np.random.default_rng(random_seed)

    required = {
        "candidate_return",
        "buy_hold_return",
        "spy_12m_return",
    }
    missing = required - set(returns.columns)

    if missing:
        raise ValueError(f"bootstrap input missing columns: {sorted(missing)}")

    candidate = returns["candidate_return"].to_numpy(dtype=float)
    buy_hold = returns["buy_hold_return"].to_numpy(dtype=float)
    spy_12m = returns["spy_12m_return"].to_numpy(dtype=float)

    rows: list[dict] = []

    for iteration in range(bootstrap_iterations):
        sample_idx = _bootstrap_block_indices(
            n_rows=len(returns),
            block_length=block_length,
            rng=rng,
        )

        candidate_metrics = _metrics_from_returns(
            candidate[sample_idx],
            initial_capital=initial_capital,
        )
        buy_hold_metrics = _metrics_from_returns(
            buy_hold[sample_idx],
            initial_capital=initial_capital,
        )
        spy_12m_metrics = _metrics_from_returns(
            spy_12m[sample_idx],
            initial_capital=initial_capital,
        )

        rows.append(
            {
                "iteration": iteration,
                "candidate_cagr_pct": candidate_metrics["cagr_pct"],
                "candidate_calmar": candidate_metrics["calmar"],
                "candidate_max_drawdown_pct": candidate_metrics["max_drawdown_pct"],
                "buy_hold_cagr_pct": buy_hold_metrics["cagr_pct"],
                "buy_hold_calmar": buy_hold_metrics["calmar"],
                "buy_hold_max_drawdown_pct": buy_hold_metrics["max_drawdown_pct"],
                "spy_12m_cagr_pct": spy_12m_metrics["cagr_pct"],
                "spy_12m_calmar": spy_12m_metrics["calmar"],
                "spy_12m_max_drawdown_pct": spy_12m_metrics["max_drawdown_pct"],
            }
        )

    samples = pd.DataFrame(rows)

    samples["candidate_minus_buy_hold_cagr_pct_points"] = (
        samples["candidate_cagr_pct"] - samples["buy_hold_cagr_pct"]
    )
    samples["candidate_minus_buy_hold_calmar"] = (
        samples["candidate_calmar"] - samples["buy_hold_calmar"]
    )
    samples["candidate_minus_buy_hold_drawdown_pct_points"] = (
        samples["candidate_max_drawdown_pct"] - samples["buy_hold_max_drawdown_pct"]
    )

    samples["candidate_minus_spy_12m_cagr_pct_points"] = (
        samples["candidate_cagr_pct"] - samples["spy_12m_cagr_pct"]
    )
    samples["candidate_minus_spy_12m_calmar"] = (
        samples["candidate_calmar"] - samples["spy_12m_calmar"]
    )
    samples["candidate_minus_spy_12m_drawdown_pct_points"] = (
        samples["candidate_max_drawdown_pct"] - samples["spy_12m_max_drawdown_pct"]
    )

    return samples


def _summarise_metric_distribution(
    samples: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    rows: list[dict] = []

    for column in columns:
        values = samples[column].dropna().astype(float)

        rows.append(
            {
                "metric": column,
                "mean": round(float(values.mean()), 4),
                "median": round(float(values.median()), 4),
                "p05": round(float(values.quantile(0.05)), 4),
                "p25": round(float(values.quantile(0.25)), 4),
                "p75": round(float(values.quantile(0.75)), 4),
                "p95": round(float(values.quantile(0.95)), 4),
            }
        )

    return pd.DataFrame(rows)


def _create_bootstrap_probability_report(samples: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "claim": "Candidate beats SPY 12M on CAGR",
            "probability": float(
                (samples["candidate_cagr_pct"] > samples["spy_12m_cagr_pct"]).mean()
            ),
        },
        {
            "claim": "Candidate beats SPY 12M on Calmar",
            "probability": float(
                (samples["candidate_calmar"] > samples["spy_12m_calmar"]).mean()
            ),
        },
        {
            "claim": "Candidate has better max drawdown than SPY 12M",
            "probability": float(
                (
                    samples["candidate_max_drawdown_pct"]
                    > samples["spy_12m_max_drawdown_pct"]
                ).mean()
            ),
        },
        {
            "claim": "Candidate beats SPY Buy & Hold on CAGR",
            "probability": float(
                (samples["candidate_cagr_pct"] > samples["buy_hold_cagr_pct"]).mean()
            ),
        },
        {
            "claim": "Candidate beats SPY Buy & Hold on Calmar",
            "probability": float(
                (samples["candidate_calmar"] > samples["buy_hold_calmar"]).mean()
            ),
        },
        {
            "claim": "Candidate has better max drawdown than SPY Buy & Hold",
            "probability": float(
                (
                    samples["candidate_max_drawdown_pct"]
                    > samples["buy_hold_max_drawdown_pct"]
                ).mean()
            ),
        },
    ]

    report = pd.DataFrame(rows)
    report["probability_pct"] = (report["probability"] * 100.0).round(2)

    return report


def _create_bootstrap_gate_report(
    probability_report: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7d_config(config)

    thresholds = {
        "Candidate beats SPY 12M on CAGR": float(
            phase_config.get("min_probability_candidate_beats_spy_12m_cagr", 0.55)
        ),
        "Candidate beats SPY 12M on Calmar": float(
            phase_config.get("min_probability_candidate_beats_spy_12m_calmar", 0.60)
        ),
        "Candidate has better max drawdown than SPY 12M": float(
            phase_config.get(
                "min_probability_candidate_beats_spy_12m_max_drawdown",
                0.60,
            )
        ),
        "Candidate beats SPY Buy & Hold on CAGR": float(
            phase_config.get(
                "max_allowed_probability_candidate_beats_buy_hold_cagr_claim",
                0.50,
            )
        ),
        "Candidate beats SPY Buy & Hold on Calmar": float(
            phase_config.get("min_probability_candidate_beats_buy_hold_calmar", 0.60)
        ),
        "Candidate has better max drawdown than SPY Buy & Hold": float(
            phase_config.get(
                "min_probability_candidate_beats_buy_hold_max_drawdown",
                0.70,
            )
        ),
    }

    rows: list[dict] = []

    for _, row in probability_report.iterrows():
        claim = str(row["claim"])
        probability = float(row["probability"])
        threshold = thresholds[claim]

        if claim == "Candidate beats SPY Buy & Hold on CAGR":
            passed = probability <= threshold
            interpretation = (
                "Candidate is not being falsely promoted as a raw-CAGR winner."
                if passed
                else "Candidate beats buy-and-hold CAGR too often for the current README hierarchy."
            )
        else:
            passed = probability >= threshold
            interpretation = (
                "Bootstrap probability clears threshold."
                if passed
                else "Bootstrap probability does not clear threshold."
            )

        rows.append(
            {
                "claim": claim,
                "status": "Passed" if passed else "Failed",
                "probability": round(probability, 4),
                "probability_pct": round(probability * 100.0, 2),
                "threshold": threshold,
                "interpretation": interpretation,
            }
        )

    return pd.DataFrame(rows)


def _create_bootstrap_conclusion(
    gate_report: pd.DataFrame,
) -> pd.DataFrame:
    failed_gates = gate_report[gate_report["status"] == "Failed"]

    spy_12m_gates = gate_report[
        gate_report["claim"].str.contains("SPY 12M", case=False, na=False)
    ]
    buy_hold_risk_gates = gate_report[
        gate_report["claim"].isin(
            [
                "Candidate beats SPY Buy & Hold on Calmar",
                "Candidate has better max drawdown than SPY Buy & Hold",
            ]
        )
    ]
    buy_hold_cagr_gate = gate_report[
        gate_report["claim"] == "Candidate beats SPY Buy & Hold on CAGR"
    ]

    spy_12m_passed = (spy_12m_gates["status"] == "Passed").all()
    buy_hold_risk_passed = (buy_hold_risk_gates["status"] == "Passed").all()
    buy_hold_cagr_hierarchy_ok = (
        not buy_hold_cagr_gate.empty
        and buy_hold_cagr_gate.iloc[0]["status"] == "Passed"
    )

    return pd.DataFrame(
        [
            {
                "claim": "Final candidate bootstrap robustness versus SPY 12M survived.",
                "status": "Survived" if spy_12m_passed else "Failed",
                "evidence_quality": "Paired block bootstrap on daily returns",
                "interpretation": (
                    "Candidate cleared the SPY 12M CAGR, Calmar, and drawdown probability gates."
                    if spy_12m_passed
                    else "Candidate did not clear all SPY 12M bootstrap gates."
                ),
            },
            {
                "claim": "Final candidate bootstrap risk advantage versus SPY Buy & Hold survived.",
                "status": "Survived" if buy_hold_risk_passed else "Failed",
                "evidence_quality": "Paired block bootstrap on daily returns",
                "interpretation": (
                    "Candidate cleared buy-and-hold Calmar and max-drawdown probability gates."
                    if buy_hold_risk_passed
                    else "Candidate did not clear all buy-and-hold risk bootstrap gates."
                ),
            },
            {
                "claim": "The project hierarchy still correctly treats SPY Buy & Hold as raw wealth benchmark.",
                "status": "Survived" if buy_hold_cagr_hierarchy_ok else "Review needed",
                "evidence_quality": "Bootstrap probability of candidate beating SPY buy-and-hold CAGR",
                "interpretation": (
                    "Bootstrap result does not justify replacing SPY Buy & Hold as raw-CAGR benchmark."
                    if buy_hold_cagr_hierarchy_ok
                    else "Bootstrap result may require revisiting the raw-CAGR hierarchy."
                ),
            },
            {
                "claim": "The final candidate is statistically proven.",
                "status": "Failed",
                "evidence_quality": "Bootstrap is a robustness diagnostic, not formal proof",
                "interpretation": (
                    "Block bootstrap improves robustness discipline but does not prove future performance."
                ),
            },
            {
                "claim": "The next step should be more strategy optimisation.",
                "status": "Not yet" if failed_gates.empty else "No",
                "evidence_quality": "Bootstrap robustness should be interpreted before new variants",
                "interpretation": (
                    "If gates pass, document Phase 7D before adding new strategy variants."
                    if failed_gates.empty
                    else "Fix or document failed statistical robustness gates before adding new variants."
                ),
            },
        ]
    )


def write_bootstrap_statistical_robustness_markdown(
    distribution_summary: pd.DataFrame,
    probability_report: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Phase 7D Bootstrap / Statistical Robustness Audit

This report applies a paired block bootstrap to the final execution-realistic candidate, SPY Buy & Hold, and SPY 12M Momentum.

The purpose is to test whether the final candidate's risk-adjusted advantage is robust across resampled return paths. This is not a formal proof of future performance.

## Metric Distribution Summary

{distribution_summary.to_markdown(index=False) if not distribution_summary.empty else "No distribution summary available."}

## Bootstrap Probability Report

{probability_report.to_markdown(index=False) if not probability_report.empty else "No probability report available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_bootstrap_statistical_robustness(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7d_config(config)

    if not phase_config.get("enabled", False):
        return {
            "input_returns": pd.DataFrame(),
            "samples": pd.DataFrame(),
            "distribution_summary": pd.DataFrame(),
            "probability_report": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    input_returns = _create_bootstrap_input_returns(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    samples = _create_bootstrap_samples(
        returns=input_returns,
        config=config,
    )

    distribution_summary = _summarise_metric_distribution(
        samples=samples,
        columns=[
            "candidate_cagr_pct",
            "candidate_calmar",
            "candidate_max_drawdown_pct",
            "buy_hold_cagr_pct",
            "buy_hold_calmar",
            "buy_hold_max_drawdown_pct",
            "spy_12m_cagr_pct",
            "spy_12m_calmar",
            "spy_12m_max_drawdown_pct",
            "candidate_minus_buy_hold_cagr_pct_points",
            "candidate_minus_buy_hold_calmar",
            "candidate_minus_buy_hold_drawdown_pct_points",
            "candidate_minus_spy_12m_cagr_pct_points",
            "candidate_minus_spy_12m_calmar",
            "candidate_minus_spy_12m_drawdown_pct_points",
        ],
    )

    probability_report = _create_bootstrap_probability_report(samples)
    gate_report = _create_bootstrap_gate_report(
        probability_report=probability_report,
        config=config,
    )
    conclusion = _create_bootstrap_conclusion(gate_report=gate_report)

    return {
        "input_returns": input_returns,
        "samples": samples,
        "distribution_summary": distribution_summary,
        "probability_report": probability_report,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def save_bootstrap_statistical_robustness(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_bootstrap_statistical_robustness(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )

    if outputs["conclusion"].empty:
        return outputs

    input_path = reports_dir / "phase7d_bootstrap_input_returns.csv"
    samples_path = reports_dir / "phase7d_bootstrap_samples.csv"
    distribution_path = reports_dir / "phase7d_bootstrap_distribution_summary.csv"
    probability_path = reports_dir / "phase7d_bootstrap_probability_report.csv"
    gate_path = reports_dir / "phase7d_bootstrap_gate_report.csv"
    conclusion_path = reports_dir / "phase7d_bootstrap_conclusion.csv"
    markdown_path = reports_dir / "phase7d_bootstrap_statistical_robustness.md"

    outputs["input_returns"].to_csv(input_path, index=False)
    outputs["samples"].to_csv(samples_path, index=False)
    outputs["distribution_summary"].to_csv(distribution_path, index=False)
    outputs["probability_report"].to_csv(probability_path, index=False)
    outputs["gate_report"].to_csv(gate_path, index=False)
    outputs["conclusion"].to_csv(conclusion_path, index=False)

    write_bootstrap_statistical_robustness_markdown(
        distribution_summary=outputs["distribution_summary"],
        probability_report=outputs["probability_report"],
        gate_report=outputs["gate_report"],
        conclusion=outputs["conclusion"],
        output_path=markdown_path,
    )

    print("\nPhase 7D bootstrap distribution summary:")
    print(outputs["distribution_summary"].to_string(index=False))

    print("\nPhase 7D bootstrap probability report:")
    print(outputs["probability_report"].to_string(index=False))

    print("\nPhase 7D bootstrap gate report:")
    print(outputs["gate_report"].to_string(index=False))

    print("\nPhase 7D bootstrap conclusion:")
    print(outputs["conclusion"].to_string(index=False))

    print(f"\nSaved Phase 7D bootstrap input returns to: {input_path}")
    print(f"Saved Phase 7D bootstrap samples to: {samples_path}")
    print(f"Saved Phase 7D bootstrap distribution summary to: {distribution_path}")
    print(f"Saved Phase 7D bootstrap probability report to: {probability_path}")
    print(f"Saved Phase 7D bootstrap gate report to: {gate_path}")
    print(f"Saved Phase 7D bootstrap conclusion to: {conclusion_path}")
    print(f"Saved Phase 7D bootstrap markdown to: {markdown_path}")

    return outputs