import importlib.util
import json
from pathlib import Path

import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_regime_informed_results_notebook.py"
)


def _load_builder_module():
    spec = importlib.util.spec_from_file_location(
        "build_regime_informed_results_notebook",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_notebook_source_data(root: Path) -> None:
    regime_dir = root / "reports" / "strategy_factory" / "regime_stress"
    recon_dir = root / "reports" / "strategy_factory" / "regime_reconciliation"
    tracking_dir = root / "reports" / "paper_trading" / "regime_informed_tracking"
    dashboard_dir = root / "reports" / "paper_trading" / "dashboard"
    regime_dir.mkdir(parents=True, exist_ok=True)
    recon_dir.mkdir(parents=True, exist_ok=True)
    tracking_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "regime_robustness_score": 61.48,
                "classification_after_hard_gates": (
                    "provisional_core_candidate_for_further_research"
                ),
                "worst_max_drawdown_pct": -24.12,
                "mean_total_return_pct": 118.82,
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "regime_robustness_score": 50.0,
                "classification_after_hard_gates": "rejected_regime_fragile",
                "worst_max_drawdown_pct": -65.22,
                "mean_total_return_pct": 205.41,
            },
        ]
    ).to_csv(regime_dir / "phase21a_regime_robustness_scores.csv", index=False)
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "worst_max_drawdown_pct": -24.12,
                "mean_total_return_pct": 118.82,
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "worst_max_drawdown_pct": -65.22,
                "mean_total_return_pct": 205.41,
            },
        ]
    ).to_csv(regime_dir / "phase21a_candidate_regime_summary.csv", index=False)
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "regime_name": "global_financial_crisis",
                "regime_available": True,
                "total_return_pct": -10.0,
                "max_drawdown_pct": -18.0,
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "regime_name": "global_financial_crisis",
                "regime_available": True,
                "total_return_pct": -45.0,
                "max_drawdown_pct": -55.0,
            },
        ]
    ).to_csv(regime_dir / "phase21a_regime_metrics.csv", index=False)
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "final_regime_robustness_score": 61.48,
            }
        ]
    ).to_csv(
        regime_dir / "phase21a_regime_robustness_score_components.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "recommended_role": "provisional_core_candidate",
            }
        ]
    ).to_csv(
        recon_dir / "phase21b_paper_shortlist_recommendation.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "canonical_candidate_id": "phase6b_loose_relief_execution_realistic_overlay",
                "candidate_role": "provisional_core_candidate",
                "asset": "SPY",
                "target_weight": 1.0,
                "candidate_caveats": "paper-only",
            },
            {
                "canonical_candidate_id": "canonical_spy_qqq_60_40",
                "candidate_role": "reference_only",
                "asset": "QQQ",
                "target_weight": 0.4,
                "candidate_caveats": "severe drawdown risk",
            },
        ]
    ).to_csv(tracking_dir / "regime_informed_paper_targets.csv", index=False)
    pd.DataFrame([{"key": "selected_signal_date", "value": "2026-06-08"}]).to_csv(
        tracking_dir / "regime_informed_daily_tracking_tear_sheet.csv",
        index=False,
    )
    pd.DataFrame(
        [{"canonical_candidate_id": "canonical_spy_qqq_60_40", "manual_decision": "skip_due_warning"}]
    ).to_csv(tracking_dir / "regime_informed_manual_session_ledger.csv", index=False)
    pd.DataFrame(
        [{"phase21e_decision": "regime_informed_session_ingested_valid_manual_paper_only"}]
    ).to_csv(dashboard_dir / "regime_informed_session_ingestion_status.csv", index=False)
    pd.DataFrame(
        [
            {
                "runtime_seconds": 12.3,
                "daily_paper_status": "daily_paper_workflow_completed_manual_paper_only",
            }
        ]
    ).to_csv(dashboard_dir / "daily_paper_runtime_status.csv", index=False)


def test_notebook_builder_writes_notebook_and_pngs(tmp_path):
    builder = _load_builder_module()
    _write_notebook_source_data(tmp_path)
    output_notebook = tmp_path / "notebooks" / "regime_informed_results_dashboard.ipynb"
    visuals_dir = tmp_path / "reports" / "paper_trading" / "regime_informed_tracking" / "visuals"

    outputs = builder.build_notebook(
        root=tmp_path,
        output_notebook=output_notebook,
        visuals_dir=visuals_dir,
    )

    assert outputs["notebook"].exists()
    for filename in builder.EXPECTED_PNGS.values():
        assert (visuals_dir / filename).exists()


def test_notebook_contains_required_sections_and_local_only_content(tmp_path):
    builder = _load_builder_module()
    _write_notebook_source_data(tmp_path)
    output_notebook = tmp_path / "notebooks" / "regime_informed_results_dashboard.ipynb"
    visuals_dir = tmp_path / "visuals"

    builder.build_notebook(
        root=tmp_path,
        output_notebook=output_notebook,
        visuals_dir=visuals_dir,
    )

    text = output_notebook.read_text(encoding="utf-8")
    notebook = json.loads(text)
    joined = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )
    for heading in builder.SECTION_HEADINGS:
        assert heading in joined
    assert "http://" not in text
    assert "https://" not in text
    assert "requests" not in text
    assert "urlopen" not in text
    assert "NO LIVE TRADING" in joined
    assert "NO REAL MONEY" in joined
    assert "NO BROKER/API" in joined
    assert "NO STRATEGY PROMOTION" in joined
