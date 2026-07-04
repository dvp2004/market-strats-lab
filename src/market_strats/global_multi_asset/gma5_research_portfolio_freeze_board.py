import csv
import json
from pathlib import Path


def generate_freeze_board(report_root: Path) -> None:
    manifest_path = (
        report_root
        / "runs"
        / "gma5_clean_execution_20260622T075912Z_v1"
        / "gma5_clean_execution_manifest_v1.json"
    )
    provenance_path = (
        report_root
        / "runs"
        / "gma5_clean_execution_20260622T075912Z_v1"
        / "gma5_composite_replay_provenance_v1.json"
    )
    recon_path = report_root / "gma5_cost_scenario_full_period_reconciliation_v1.csv"
    learned_path = report_root / "gma5_learned_only_window_scoreboard_v2.csv"

    with open(manifest_path) as f:
        manifest = json.load(f)

    with open(provenance_path) as f:
        provenance = json.load(f)

    # Read metrics
    metrics = {}
    with open(recon_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = row["variant_id"]
            cost = row["cost_scenario"]
            metric = row["metric_name"]
            val = float(row["exported_value"])
            if vid not in metrics:
                metrics[vid] = {
                    "full_common_oos_period": {
                        "baseline_1bps_metrics": {},
                        "severe_50bps_metrics": {},
                    },
                    "learned_only_ridge_window": {
                        "baseline_1bps_metrics": {},
                        "severe_50bps_metrics": {},
                    },
                }

            if cost == "baseline_1bps":
                metrics[vid]["full_common_oos_period"]["baseline_1bps_metrics"][metric] = val
            elif cost == "severe_50bps":
                metrics[vid]["full_common_oos_period"]["severe_50bps_metrics"][metric] = val

    with open(learned_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = row["variant_id"]
            cost = row["cost_scenario"]
            if cost == "baseline_1bps":
                metrics[vid]["learned_only_ridge_window"]["baseline_1bps_metrics"] = {
                    "net CAGR": float(row["net_cagr"]),
                    "maximum drawdown": float(row["maximum_drawdown"]),
                }
            elif cost == "severe_50bps":
                metrics[vid]["learned_only_ridge_window"]["severe_50bps_metrics"] = {
                    "net CAGR": float(row["net_cagr"]),
                    "maximum drawdown": float(row["maximum_drawdown"]),
                }

    variants = []
    classifications = {
        "gma5_equal_weight_atomic_sleeves_v1": {
            "classification": "frozen_research_portfolio",
            "role": "diversified_return_core",
            "rationale": "strongest learned-only CAGR across all four frozen cost scenarios; full-period reconciliation passed; clean composite replay verified.",
            "known_limitations": [],
        },
        "gma5_fixed_alpha_ridge_atomic_ensemble_v1": {
            "classification": "frozen_research_portfolio",
            "role": "lower_drawdown_cost_sensitive_variant",
            "rationale": "materially lower learned-only baseline drawdown and higher baseline Sharpe than equal-weight, but materially weaker severe-cost CAGR. It is not the default return construction.",
            "known_limitations": ["cost_sensitivity", "materially_weaker_severe_cost_cagr"],
        },
        "gma5_risk_weighted_atomic_sleeves_v1": {
            "classification": "archived_from_gma5_v1",
            "role": "no_distinct_role_demonstrated",
            "rationale": "lower learned-only return and lower Sharpe than equal-weight, with no material drawdown advantage.",
            "known_limitations": ["lower_learned_only_return"],
        },
    }

    target_hashes = manifest["runtime_replay_trace"]["composite_target_input_hashes_by_variant"]

    csv_rows = []

    for vid, cinfo in classifications.items():
        vinfo = {
            "variant_id": vid,
            "classification": cinfo["classification"],
            "role": cinfo["role"],
            "original_gma5_run_id": manifest["original_run_id"],
            "clean_execution_run_id": manifest["clean_execution_run_id"],
            "gma5_config_hash": provenance["gma5_config_hash"],
            "gma5_source_hash": provenance["gma5_source_hash"],
            "replay_adapter_source_hash": provenance["replay_adapter_source_hash"],
            "composite_target_input_hash": target_hashes[vid],
            "full_common_oos_period": {"period_start": "2012-05-31", "period_end": "2026-05-01"},
            "learned_only_ridge_window": {"period_start": "2015-05-29", "period_end": "2026-05-01"},
            "baseline_1bps_metrics": {
                "full_common_oos": metrics[vid]["full_common_oos_period"]["baseline_1bps_metrics"],
                "learned_only": metrics[vid]["learned_only_ridge_window"]["baseline_1bps_metrics"],
            },
            "severe_50bps_metrics": {
                "full_common_oos": metrics[vid]["full_common_oos_period"]["severe_50bps_metrics"],
                "learned_only": metrics[vid]["learned_only_ridge_window"]["severe_50bps_metrics"],
            },
            "known_limitations": cinfo["known_limitations"],
        }
        variants.append(vinfo)

        csv_rows.append(
            {
                "variant_id": vid,
                "classification": cinfo["classification"],
                "role": cinfo["role"],
                "rationale": cinfo["rationale"],
            }
        )

    locks = {
        "comparison_scope": "three_gma5_v1_ensemble_variants_only",
        "external_learned_only_comparators_available": False,
        "concurrent_combination_authorized": False,
        "freeze_basis": "content_hashes_and_saved_artifact_provenance_pending_version_control_checkpoint",
        "variants": variants,
    }

    with open(report_root / "gma5_research_portfolio_locks_v1.json", "w") as f:
        json.dump(locks, f, indent=2)

    with open(report_root / "gma5_research_portfolio_freeze_board_v1.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["variant_id", "classification", "role", "rationale"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    md_content = """# GMA-5 V1 Research Portfolio Freeze Board

1. All "strongest" or "primary" wording must be scoped exactly as follows:
`within the three GMA-5 V1 ensemble variants only`

2. The equal-weight and Ridge variants are separate frozen research hypotheses.
They are not approved to be combined, jointly allocated to, paper traded, broker connected, or treated as a multi-portfolio allocation.
Any future prospective or paper observation design must separately specify whether one or both are observed, with no implied combined allocation.

## Classifications
"""
    for r in csv_rows:
        md_content += f"\n### {r['variant_id']}\n"
        md_content += f"- **Classification**: {r['classification']}\n"
        md_content += f"- **Role**: {r['role']}\n"
        md_content += f"- **Rationale**: {r['rationale']}\n"

    with open(report_root / "gma5_research_portfolio_freeze_board_v1.md", "w") as f:
        f.write(md_content)


if __name__ == "__main__":
    generate_freeze_board(Path("reports/global_multi_asset_alpha/gma5_atomic_sleeve_ensemble_v1"))
