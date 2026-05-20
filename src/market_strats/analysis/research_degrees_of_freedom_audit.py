from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE8E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "claim_context": {
        "final_candidate": "SPY 3D confirmed overlay + deep_drawdown_guard + loose_relief",
        "final_candidate_role": "Best execution-realistic risk-adjusted candidate built so far",
        "raw_wealth_benchmark": "SPY Buy & Hold",
        "simple_defensive_benchmark": "SPY 12M Momentum",
        "canonical_start_date": "2006-04-28",
        "canonical_end_date": "2026-05-01",
    },
    "gates": {
        "require_failed_branches_documented": True,
        "require_multiple_comparisons_caveat": True,
        "require_raw_wealth_hierarchy_preserved": True,
        "require_final_claim_narrowed": True,
        "max_promoted_share_of_tested_units": 0.25,
        "min_failed_or_rejected_units": 5,
    },
    "inventory": [],
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
    user_config = config.get("phase8e_research_degrees_of_freedom_audit", {})
    return _deep_merge_dict(DEFAULT_PHASE8E_CONFIG, user_config)


def build_phase8e_inventory(phase_config: dict[str, Any]) -> pd.DataFrame:
    inventory = phase_config.get("inventory", [])

    if not inventory:
        return pd.DataFrame(
            columns=[
                "phase",
                "branch",
                "tested_units",
                "promoted_units",
                "failed_or_rejected_units",
                "mixed_or_caveated_units",
                "status",
                "notes",
            ]
        )

    frame = pd.DataFrame(inventory).copy()

    required_columns = {
        "phase",
        "branch",
        "tested_units",
        "promoted_units",
        "failed_or_rejected_units",
        "mixed_or_caveated_units",
        "status",
        "notes",
    }
    missing_columns = required_columns.difference(frame.columns)

    if missing_columns:
        raise ValueError(
            "Phase 8E inventory is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    numeric_columns = [
        "tested_units",
        "promoted_units",
        "failed_or_rejected_units",
        "mixed_or_caveated_units",
    ]

    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)

    return frame[
        [
            "phase",
            "branch",
            "tested_units",
            "promoted_units",
            "failed_or_rejected_units",
            "mixed_or_caveated_units",
            "status",
            "notes",
        ]
    ]


def build_phase8e_summary(inventory: pd.DataFrame, phase_config: dict[str, Any]) -> pd.DataFrame:
    claim_context = phase_config.get("claim_context", {})

    total_tested = int(inventory["tested_units"].sum()) if not inventory.empty else 0
    total_promoted = int(inventory["promoted_units"].sum()) if not inventory.empty else 0
    total_failed = (
        int(inventory["failed_or_rejected_units"].sum()) if not inventory.empty else 0
    )
    total_mixed = (
        int(inventory["mixed_or_caveated_units"].sum()) if not inventory.empty else 0
    )
    branch_count = int(len(inventory))

    promoted_share = total_promoted / total_tested if total_tested > 0 else 0.0
    failed_or_mixed_share = (
        (total_failed + total_mixed) / total_tested if total_tested > 0 else 0.0
    )

    if total_tested == 0:
        claim_strength = "Invalid — no inventory supplied"
    elif failed_or_mixed_share >= 0.50:
        claim_strength = "Narrow / heavily caveated"
    else:
        claim_strength = "Moderate but still caveated"

    return pd.DataFrame(
        [
            {
                "final_candidate": claim_context.get("final_candidate"),
                "final_candidate_role": claim_context.get("final_candidate_role"),
                "raw_wealth_benchmark": claim_context.get("raw_wealth_benchmark"),
                "simple_defensive_benchmark": claim_context.get(
                    "simple_defensive_benchmark"
                ),
                "canonical_start_date": claim_context.get("canonical_start_date"),
                "canonical_end_date": claim_context.get("canonical_end_date"),
                "branch_count": branch_count,
                "total_tested_units": total_tested,
                "total_promoted_units": total_promoted,
                "total_failed_or_rejected_units": total_failed,
                "total_mixed_or_caveated_units": total_mixed,
                "promoted_share_of_tested_units": promoted_share,
                "failed_or_mixed_share_of_tested_units": failed_or_mixed_share,
                "claim_strength_after_audit": claim_strength,
            }
        ]
    )


def build_phase8e_claim_adjustment(
    summary: pd.DataFrame,
    inventory: pd.DataFrame,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    row = summary.iloc[0]
    failed_or_mixed_share = float(row["failed_or_mixed_share_of_tested_units"])
    promoted_share = float(row["promoted_share_of_tested_units"])

    if failed_or_mixed_share >= 0.50:
        adjusted_claim = (
            "The final candidate should be described as the best execution-realistic "
            "risk-adjusted candidate built so far, not as a broadly proven market-beating "
            "system. The number of failed, rejected, and caveated branches means claims "
            "must remain narrow."
        )
    else:
        adjusted_claim = (
            "The final candidate still requires caveated wording because multiple "
            "strategy families and diagnostics were tested."
        )

    rejected_branches = (
        inventory[inventory["promoted_units"] == 0]["branch"].tolist()
        if not inventory.empty
        else []
    )

    return pd.DataFrame(
        [
            {
                "claim_area": "Final candidate wording",
                "recommended_wording": adjusted_claim,
                "promoted_share_of_tested_units": promoted_share,
                "failed_or_mixed_share_of_tested_units": failed_or_mixed_share,
                "branches_without_promotions": "; ".join(rejected_branches),
            }
        ]
    )


def _gate_row(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_phase8e_gate_report(
    inventory: pd.DataFrame,
    summary: pd.DataFrame,
    claim_adjustment: pd.DataFrame,
    phase_config: dict[str, Any],
) -> pd.DataFrame:
    gates = phase_config.get("gates", {})

    if summary.empty:
        return pd.DataFrame(
            [
                _gate_row(
                    "Phase 8E summary exists",
                    False,
                    "No summary was created.",
                )
            ]
        )

    row = summary.iloc[0]

    total_failed = int(row["total_failed_or_rejected_units"])
    promoted_share = float(row["promoted_share_of_tested_units"])
    max_promoted_share = float(gates.get("max_promoted_share_of_tested_units", 0.25))
    min_failed = int(gates.get("min_failed_or_rejected_units", 5))

    require_failed_documented = bool(gates.get("require_failed_branches_documented", True))
    require_multiple_caveat = bool(gates.get("require_multiple_comparisons_caveat", True))
    require_raw_hierarchy = bool(gates.get("require_raw_wealth_hierarchy_preserved", True))
    require_narrow_claim = bool(gates.get("require_final_claim_narrowed", True))

    failed_documented = total_failed >= min_failed
    multiple_caveat_present = not claim_adjustment.empty
    raw_hierarchy_preserved = (
        row["raw_wealth_benchmark"] == "SPY Buy & Hold"
        and row["final_candidate_role"] != "Raw wealth benchmark"
    )
    final_claim_narrowed = (
        "best execution-realistic risk-adjusted candidate built so far"
        in str(row["final_candidate_role"]).lower()
    )

    rows = [
        _gate_row(
            "Inventory contains tested research branches",
            not inventory.empty and int(row["branch_count"]) > 0,
            f"{int(row['branch_count'])} branches",
        ),
        _gate_row(
            "Failed/rejected branches are documented",
            (not require_failed_documented) or failed_documented,
            f"{total_failed} failed/rejected units; required >= {min_failed}",
        ),
        _gate_row(
            "Promoted share of tested units is not excessive",
            promoted_share <= max_promoted_share,
            f"{promoted_share:.2%}; limit {max_promoted_share:.2%}",
        ),
        _gate_row(
            "Multiple-comparisons caveat is produced",
            (not require_multiple_caveat) or multiple_caveat_present,
            "claim-adjustment table created",
        ),
        _gate_row(
            "Raw wealth hierarchy is preserved",
            (not require_raw_hierarchy) or raw_hierarchy_preserved,
            f"raw benchmark={row['raw_wealth_benchmark']}",
        ),
        _gate_row(
            "Final claim is narrow rather than overpromoted",
            (not require_narrow_claim) or final_claim_narrowed,
            f"role={row['final_candidate_role']}",
        ),
    ]

    gate_report = pd.DataFrame(rows)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    return gate_report


def build_phase8e_conclusion(gate_report: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    all_passed = bool(gate_report["passed"].all())

    if summary.empty:
        verdict = "Failed — missing inventory"
        interpretation = "Phase 8E could not evaluate research degrees of freedom."
    elif all_passed:
        verdict = "Completed — claims narrowed"
        interpretation = (
            "The project documented research degrees of freedom and preserved narrow "
            "claim wording. This does not statistically correct for all multiple "
            "comparisons, but it makes the research ledger more honest."
        )
    else:
        verdict = "Failed audit discipline"
        interpretation = (
            "The project did not satisfy every research-degrees-of-freedom audit gate. "
            "Do not move to richer signals until the ledger is corrected."
        )

    return pd.DataFrame(
        [
            {
                "phase": "Phase 8E",
                "diagnostic": "Multiple-comparisons / research-degrees-of-freedom audit",
                "verdict": verdict,
                "all_gates_passed": all_passed,
                "interpretation": interpretation,
            }
        ]
    )


def write_phase8e_markdown(
    inventory: pd.DataFrame,
    summary: pd.DataFrame,
    claim_adjustment: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# Phase 8E — Multiple-Comparisons / Research-Degrees-of-Freedom Audit",
        "",
        "## Purpose",
        "",
        (
            "This audit documents how many strategy families, diagnostics, and "
            "research branches contributed to the final project claim."
        ),
        "",
        (
            "It is not a formal multiple-comparisons correction and it is not "
            "statistical proof. It is a research-ledger discipline check."
        ),
        "",
        "## Inventory",
        "",
        inventory.to_markdown(index=False),
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Claim Adjustment",
        "",
        claim_adjustment.to_markdown(index=False),
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
        "- This is not a formal family-wise error-rate correction.",
        "- Inventory counts are research-ledger units, not independent trials.",
        "- The audit narrows wording; it does not prove future performance.",
        "- Failed branches should remain documented rather than hidden.",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase8e_research_degrees_of_freedom_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _get_phase_config(config)

    if not phase_config.get("enabled", False):
        empty = pd.DataFrame()
        return {
            "inventory": empty,
            "summary": empty,
            "claim_adjustment": empty,
            "gate_report": empty,
            "conclusion": empty,
        }

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    inventory = build_phase8e_inventory(phase_config)
    summary = build_phase8e_summary(inventory, phase_config)
    claim_adjustment = build_phase8e_claim_adjustment(summary, inventory)
    gate_report = build_phase8e_gate_report(
        inventory,
        summary,
        claim_adjustment,
        phase_config,
    )
    conclusion = build_phase8e_conclusion(gate_report, summary)

    inventory.to_csv(
        reports_path / "phase8e_research_degrees_of_freedom_inventory.csv",
        index=False,
    )
    summary.to_csv(
        reports_path / "phase8e_research_degrees_of_freedom_summary.csv",
        index=False,
    )
    claim_adjustment.to_csv(
        reports_path / "phase8e_research_degrees_of_freedom_claim_adjustment.csv",
        index=False,
    )
    gate_report.to_csv(
        reports_path / "phase8e_research_degrees_of_freedom_gate_report.csv",
        index=False,
    )
    conclusion.to_csv(
        reports_path / "phase8e_research_degrees_of_freedom_conclusion.csv",
        index=False,
    )

    write_phase8e_markdown(
        inventory=inventory,
        summary=summary,
        claim_adjustment=claim_adjustment,
        gate_report=gate_report,
        conclusion=conclusion,
        output_path=reports_path / "phase8e_research_degrees_of_freedom_audit.md",
    )

    print("Wrote Phase 8E research-degrees-of-freedom audit reports.")

    return {
        "inventory": inventory,
        "summary": summary,
        "claim_adjustment": claim_adjustment,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }