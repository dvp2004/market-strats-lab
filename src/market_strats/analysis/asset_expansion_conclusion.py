from __future__ import annotations

from pathlib import Path

import pandas as pd


def create_asset_expansion_conclusion(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)
    decision_path = reports_dir / "asset_expansion_diagnostic_decision.csv"

    if not decision_path.exists():
        return pd.DataFrame(
            [
                {
                    "claim": "Asset expansion diagnostic is available.",
                    "status": "Failed",
                    "evidence_quality": "Missing decision report",
                    "interpretation": "No asset expansion diagnostic decision file was found.",
                }
            ]
        )

    decision = pd.read_csv(decision_path)

    if decision.empty:
        return pd.DataFrame()

    row = decision.iloc[0]

    return pd.DataFrame(
        [
            {
                "claim": "Adding USO improves the standalone allocator.",
                "status": "Survived"
                if bool(row.get("allocator_pass", False))
                else "Failed",
                "evidence_quality": "Supported by allocator full-period comparison",
                "interpretation": (
                    f"Base allocator CAGR was {row.get('baseline_allocator_cagr_pct')}%, "
                    f"while Base + Oil allocator CAGR was "
                    f"{row.get('expanded_allocator_cagr_pct')}%. "
                    f"Calmar changed from {row.get('baseline_allocator_calmar')} "
                    f"to {row.get('expanded_allocator_calmar')}."
                ),
            },
            {
                "claim": "Adding USO improves the full-period 3D overlay.",
                "status": "Survived"
                if bool(row.get("overlay_full_pass", False))
                else "Failed",
                "evidence_quality": "Supported by full-period overlay comparison",
                "interpretation": (
                    f"Base overlay CAGR was {row.get('baseline_overlay_full_cagr_pct')}%, "
                    f"while Base + Oil overlay CAGR was "
                    f"{row.get('expanded_overlay_full_cagr_pct')}%. "
                    f"Calmar changed from {row.get('baseline_overlay_full_calmar')} "
                    f"to {row.get('expanded_overlay_full_calmar')}."
                ),
            },
            {
                "claim": "Adding USO materially improves the holdout 3D overlay.",
                "status": "Failed",
                "evidence_quality": "Failed holdout materiality gate",
                "interpretation": (
                    f"Holdout overlay CAGR changed from "
                    f"{row.get('baseline_overlay_holdout_cagr_pct')}% to "
                    f"{row.get('expanded_overlay_holdout_cagr_pct')}%, a delta of "
                    f"{row.get('overlay_holdout_cagr_delta_pct_points')} percentage points. "
                    f"Holdout Calmar changed by only "
                    f"{row.get('overlay_holdout_calmar_delta')}."
                ),
            },
            {
                "claim": "USO was ignored by the allocator.",
                "status": "Failed",
                "evidence_quality": "Allocation summary shows USO was used",
                "interpretation": (
                    f"USO average weight was {row.get('added_asset_avg_weight_pct')}%, "
                    f"held for {row.get('added_asset_days_held')} days, and had a final "
                    f"weight of {row.get('added_asset_final_weight_pct')}%."
                ),
            },
            {
                "claim": "USO should be promoted to the main validated system immediately.",
                "status": "Failed",
                "evidence_quality": "Holdout improvement was too small",
                "interpretation": (
                    "USO is promising, but not validated. It improved the allocator and "
                    "full-period overlay, but did not materially improve holdout overlay "
                    "performance."
                ),
            },
            {
                "claim": "ETH should be tested in the same branch as USO.",
                "status": "Failed",
                "evidence_quality": "ETH has a different and shorter data history",
                "interpretation": (
                    "ETH should remain quarantined and tested separately because it changes "
                    "the common sample period and has a structurally different risk profile."
                ),
            },
        ]
    )


def write_asset_expansion_conclusion_markdown(
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    table = conclusion.to_markdown(index=False) if not conclusion.empty else ""

    content = f"""# Asset Expansion Conclusion

This report freezes the controlled USO oil-proxy expansion branch.

## Claim Table

{table}

## Final Conclusion

USO improved the standalone allocator and improved the full-period 3D overlay.

However, the holdout improvement was too small to call USO a validated addition to the main system.

Correct classification:

> Promising but not validated.

USO should stay as a candidate for future testing, not as a promoted core asset.

ETH should be tested separately as a quarantined crypto branch.
"""

    output_path.write_text(content, encoding="utf-8")
    return output_path


def save_asset_expansion_conclusion(
    reports_dir: str | Path = "reports",
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    conclusion = create_asset_expansion_conclusion(reports_dir)

    conclusion_path = reports_dir / "asset_expansion_conclusion.csv"
    markdown_path = reports_dir / "asset_expansion_conclusion.md"

    conclusion.to_csv(conclusion_path, index=False)
    write_asset_expansion_conclusion_markdown(conclusion, markdown_path)

    print("\nAsset expansion conclusion:")
    print(conclusion.to_string(index=False))

    print(f"\nSaved asset expansion conclusion to: {conclusion_path}")
    print(f"Saved asset expansion conclusion markdown to: {markdown_path}")

    return {"conclusion": conclusion}