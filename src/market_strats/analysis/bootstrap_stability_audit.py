from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_strats.analysis.bootstrap_statistical_robustness import (
    _create_bootstrap_gate_report,
    _create_bootstrap_input_returns,
    _create_bootstrap_probability_report,
    _create_bootstrap_samples,
)


def _phase7e_config(config: dict) -> dict:
    return config.get("phase7_bootstrap_stability_audit", {})


def _load_or_create_input_returns(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: Path,
) -> pd.DataFrame:
    phase_config = _phase7e_config(config)

    input_report_name = str(
        phase_config.get("input_returns_report", "phase7d_bootstrap_input_returns.csv")
    )
    input_report_path = reports_dir / input_report_name
    require_existing = bool(phase_config.get("require_existing_input_report", True))

    if input_report_path.exists():
        input_returns = pd.read_csv(input_report_path)
        input_returns["date"] = pd.to_datetime(input_returns["date"])
        return input_returns.sort_values("date").reset_index(drop=True)

    if require_existing:
        raise FileNotFoundError(
            f"Required bootstrap input report not found: {input_report_path}. "
            "Run Phase 7D first or set require_existing_input_report=false."
        )

    return _create_bootstrap_input_returns(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )


def _profile_config(
    base_config: dict,
    block_length_days: int,
    random_seed: int,
    bootstrap_iterations: int,
) -> dict:
    phase_config = _phase7e_config(base_config)

    return {
        "phase7_bootstrap_statistical_robustness": {
            "enabled": True,
            "bootstrap_iterations": bootstrap_iterations,
            "block_length_days": block_length_days,
            "random_seed": random_seed,
            "initial_capital": float(phase_config.get("initial_capital", 10000.0)),
            "min_probability_candidate_beats_spy_12m_cagr": float(
                phase_config.get("min_probability_candidate_beats_spy_12m_cagr", 0.55)
            ),
            "min_probability_candidate_beats_spy_12m_calmar": float(
                phase_config.get("min_probability_candidate_beats_spy_12m_calmar", 0.60)
            ),
            "min_probability_candidate_beats_spy_12m_max_drawdown": float(
                phase_config.get(
                    "min_probability_candidate_beats_spy_12m_max_drawdown",
                    0.60,
                )
            ),
            "min_probability_candidate_beats_buy_hold_calmar": float(
                phase_config.get("min_probability_candidate_beats_buy_hold_calmar", 0.60)
            ),
            "min_probability_candidate_beats_buy_hold_max_drawdown": float(
                phase_config.get(
                    "min_probability_candidate_beats_buy_hold_max_drawdown",
                    0.70,
                )
            ),
            "max_allowed_probability_candidate_beats_buy_hold_cagr_claim": float(
                phase_config.get(
                    "max_allowed_probability_candidate_beats_buy_hold_cagr_claim",
                    0.50,
                )
            ),
        }
    }


def _run_stability_profiles(
    input_returns: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    phase_config = _phase7e_config(config)

    block_lengths = [
        int(value) for value in phase_config.get("block_lengths_days", [5, 21, 63])
    ]
    random_seeds = [int(value) for value in phase_config.get("random_seeds", [7, 42, 123])]
    bootstrap_iterations = int(phase_config.get("bootstrap_iterations", 300))

    profile_rows: list[dict] = []
    gate_rows: list[pd.DataFrame] = []

    profile_id = 0

    for block_length in block_lengths:
        for seed in random_seeds:
            profile_id += 1

            profile_cfg = _profile_config(
                base_config=config,
                block_length_days=block_length,
                random_seed=seed,
                bootstrap_iterations=bootstrap_iterations,
            )

            samples = _create_bootstrap_samples(
                returns=input_returns,
                config=profile_cfg,
            )
            probability_report = _create_bootstrap_probability_report(samples)
            gate_report = _create_bootstrap_gate_report(
                probability_report=probability_report,
                config=profile_cfg,
            )

            all_gates_passed = bool((gate_report["status"] == "Passed").all())

            profile_rows.append(
                {
                    "profile_id": profile_id,
                    "block_length_days": block_length,
                    "random_seed": seed,
                    "bootstrap_iterations": bootstrap_iterations,
                    "all_gates_passed": all_gates_passed,
                    "passed_gate_count": int((gate_report["status"] == "Passed").sum()),
                    "failed_gate_count": int((gate_report["status"] == "Failed").sum()),
                }
            )

            expanded_gate_report = gate_report.copy()
            expanded_gate_report.insert(0, "profile_id", profile_id)
            expanded_gate_report.insert(1, "block_length_days", block_length)
            expanded_gate_report.insert(2, "random_seed", seed)
            gate_rows.append(expanded_gate_report)

    profiles = pd.DataFrame(profile_rows)
    gates = pd.concat(gate_rows, ignore_index=True) if gate_rows else pd.DataFrame()

    return profiles, gates


def _create_probability_stability_summary(gates: pd.DataFrame) -> pd.DataFrame:
    if gates.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for claim, group in gates.groupby("claim"):
        probabilities = group["probability"].astype(float)

        rows.append(
            {
                "claim": claim,
                "profile_count": int(len(group)),
                "passed_profile_count": int((group["status"] == "Passed").sum()),
                "failed_profile_count": int((group["status"] == "Failed").sum()),
                "min_probability": round(float(probabilities.min()), 4),
                "mean_probability": round(float(probabilities.mean()), 4),
                "median_probability": round(float(probabilities.median()), 4),
                "max_probability": round(float(probabilities.max()), 4),
                "min_probability_pct": round(float(probabilities.min() * 100.0), 2),
                "mean_probability_pct": round(float(probabilities.mean() * 100.0), 2),
                "max_probability_pct": round(float(probabilities.max() * 100.0), 2),
            }
        )

    return pd.DataFrame(rows)


def _create_stability_conclusion(
    profiles: pd.DataFrame,
    gates: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7e_config(config)

    if profiles.empty or gates.empty:
        return pd.DataFrame()

    profile_count = int(len(profiles))
    passing_profiles = int(profiles["all_gates_passed"].sum())
    passing_share = passing_profiles / profile_count if profile_count else 0.0

    min_required_share = float(phase_config.get("min_profiles_passing_all_gates", 1.0))
    all_profiles_passed = passing_share >= min_required_share

    failed_gates = gates[gates["status"] == "Failed"]

    return pd.DataFrame(
        [
            {
                "claim": "Bootstrap conclusion is stable across block lengths and random seeds.",
                "status": "Survived" if all_profiles_passed else "Failed",
                "evidence_quality": "Repeated paired block bootstrap using multiple block lengths and seeds",
                "interpretation": (
                    f"{passing_profiles}/{profile_count} bootstrap profiles passed all gates "
                    f"({passing_share:.1%}); required {min_required_share:.1%}."
                ),
            },
            {
                "claim": "The final candidate's SPY 12M edge is not dependent on one bootstrap setup.",
                "status": "Survived"
                if failed_gates[
                    failed_gates["claim"].str.contains("SPY 12M", case=False, na=False)
                ].empty
                else "Failed",
                "evidence_quality": "Gate results by bootstrap profile",
                "interpretation": (
                    "All SPY 12M bootstrap gates passed across tested profiles."
                    if failed_gates[
                        failed_gates["claim"].str.contains("SPY 12M", case=False, na=False)
                    ].empty
                    else "At least one SPY 12M bootstrap gate failed in a tested profile."
                ),
            },
            {
                "claim": "The project hierarchy remains stable under bootstrap sensitivity.",
                "status": "Survived"
                if failed_gates[
                    failed_gates["claim"].str.contains("Buy & Hold", case=False, na=False)
                ].empty
                else "Review needed",
                "evidence_quality": "Buy-and-hold CAGR hierarchy and risk gates across profiles",
                "interpretation": (
                    "Buy-and-hold hierarchy and candidate risk-advantage gates survived across tested profiles."
                    if failed_gates[
                        failed_gates["claim"].str.contains("Buy & Hold", case=False, na=False)
                    ].empty
                    else "At least one buy-and-hold hierarchy/risk gate failed in a tested profile."
                ),
            },
            {
                "claim": "The final candidate is statistically proven.",
                "status": "Failed",
                "evidence_quality": "Bootstrap sensitivity is still a resampling diagnostic",
                "interpretation": (
                    "Passing multiple bootstrap profiles strengthens robustness evidence, but it still does not prove future performance."
                ),
            },
            {
                "claim": "The next step should be more strategy optimisation.",
                "status": "Not yet" if all_profiles_passed else "No",
                "evidence_quality": "Bootstrap stability should be documented before new variants",
                "interpretation": (
                    "Document Phase 7E before adding new strategy variants."
                    if all_profiles_passed
                    else "Resolve or document bootstrap instability before adding new variants."
                ),
            },
        ]
    )


def write_bootstrap_stability_markdown(
    profiles: pd.DataFrame,
    probability_summary: pd.DataFrame,
    gates: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Phase 7E Bootstrap Stability Audit

This report tests whether the Phase 7D bootstrap conclusion is stable across multiple block lengths and random seeds.

It reuses the Phase 7D bootstrap input return series, then reruns the paired block bootstrap under neighbouring resampling assumptions.

## Profile Summary

{profiles.to_markdown(index=False) if not profiles.empty else "No profile summary available."}

## Probability Stability Summary

{probability_summary.to_markdown(index=False) if not probability_summary.empty else "No probability summary available."}

## Gate Results

{gates.to_markdown(index=False) if not gates.empty else "No gate results available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_bootstrap_stability_audit(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7e_config(config)

    if not phase_config.get("enabled", False):
        return {
            "profiles": pd.DataFrame(),
            "gates": pd.DataFrame(),
            "probability_summary": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    reports_dir = Path(reports_dir)

    input_returns = _load_or_create_input_returns(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
        reports_dir=reports_dir,
    )

    profiles, gates = _run_stability_profiles(
        input_returns=input_returns,
        config=config,
    )
    probability_summary = _create_probability_stability_summary(gates)
    conclusion = _create_stability_conclusion(
        profiles=profiles,
        gates=gates,
        config=config,
    )

    return {
        "profiles": profiles,
        "gates": gates,
        "probability_summary": probability_summary,
        "conclusion": conclusion,
    }


def save_bootstrap_stability_audit(
    relative_momentum_outputs: dict[str, dict[str, pd.DataFrame]],
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_bootstrap_stability_audit(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
        reports_dir=reports_dir,
    )

    if outputs["conclusion"].empty:
        return outputs

    profiles_path = reports_dir / "phase7e_bootstrap_stability_profiles.csv"
    gates_path = reports_dir / "phase7e_bootstrap_stability_gate_report.csv"
    probability_path = (
        reports_dir / "phase7e_bootstrap_stability_probability_summary.csv"
    )
    conclusion_path = reports_dir / "phase7e_bootstrap_stability_conclusion.csv"
    markdown_path = reports_dir / "phase7e_bootstrap_stability.md"

    outputs["profiles"].to_csv(profiles_path, index=False)
    outputs["gates"].to_csv(gates_path, index=False)
    outputs["probability_summary"].to_csv(probability_path, index=False)
    outputs["conclusion"].to_csv(conclusion_path, index=False)

    write_bootstrap_stability_markdown(
        profiles=outputs["profiles"],
        probability_summary=outputs["probability_summary"],
        gates=outputs["gates"],
        conclusion=outputs["conclusion"],
        output_path=markdown_path,
    )

    print("\nPhase 7E bootstrap stability profiles:")
    print(outputs["profiles"].to_string(index=False))

    print("\nPhase 7E bootstrap stability probability summary:")
    print(outputs["probability_summary"].to_string(index=False))

    print("\nPhase 7E bootstrap stability gate report:")
    print(outputs["gates"].to_string(index=False))

    print("\nPhase 7E bootstrap stability conclusion:")
    print(outputs["conclusion"].to_string(index=False))

    print(f"\nSaved Phase 7E bootstrap stability profiles to: {profiles_path}")
    print(f"Saved Phase 7E bootstrap stability gate report to: {gates_path}")
    print(f"Saved Phase 7E bootstrap stability probability summary to: {probability_path}")
    print(f"Saved Phase 7E bootstrap stability conclusion to: {conclusion_path}")
    print(f"Saved Phase 7E bootstrap stability markdown to: {markdown_path}")

    return outputs