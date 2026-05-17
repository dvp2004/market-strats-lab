from pathlib import Path

import pandas as pd

from market_strats.analysis.report_integrity_audit import (
    _create_endpoint_audit,
    _create_final_checkpoint_claim_audit,
    _create_integrity_conclusion,
)


def test_create_endpoint_audit_flags_future_end_date(tmp_path: Path):
    reports_dir = tmp_path

    pd.DataFrame(
        {
            "strategy": ["A", "B"],
            "end_date": ["2026-05-01", "2026-05-13"],
        }
    ).to_csv(reports_dir / "test_report.csv", index=False)

    audit = _create_endpoint_audit(
        reports_dir=reports_dir,
        pinned_end_date="2026-05-01",
    )

    row = audit[audit["file_name"] == "test_report.csv"].iloc[0]

    assert row["status"] == "Failed"
    assert row["bad_row_count"] == 1


def test_create_final_checkpoint_claim_audit_passes(tmp_path: Path):
    reports_dir = tmp_path

    pd.DataFrame(
        {
            "period": ["full"],
            "candidate_name": ["Phase 6B loose relief candidate"],
            "cagr_pct": [10.35],
            "calmar": [0.429],
            "max_drawdown_pct": [-24.12],
            "end_value": [71779.16],
            "trade_count": [36],
        }
    ).to_csv(reports_dir / "final_candidate_comparison.csv", index=False)

    config = {
        "phase7_report_integrity_audit": {
            "expected_final_candidate": {
                "candidate_name": "Phase 6B loose relief candidate",
                "period": "full",
                "cagr_pct": 10.35,
                "calmar": 0.429,
                "max_drawdown_pct": -24.12,
                "end_value": 71779.16,
                "trade_count": 36,
            }
        }
    }

    audit = _create_final_checkpoint_claim_audit(
        reports_dir=reports_dir,
        config=config,
    )

    assert set(audit["status"]) == {"Passed"}


def test_create_integrity_conclusion_passes_when_all_inputs_pass():
    endpoint_audit = pd.DataFrame(
        {
            "status": ["Passed", "No end_date column"],
        }
    )
    expected_report_audit = pd.DataFrame(
        {
            "status": ["Passed"],
        }
    )
    claim_audit = pd.DataFrame(
        {
            "status": ["Passed"],
        }
    )
    readme_audit = pd.DataFrame(
        {
            "status": ["Passed"],
        }
    )

    conclusion = _create_integrity_conclusion(
        endpoint_audit=endpoint_audit,
        expected_report_audit=expected_report_audit,
        claim_audit=claim_audit,
        readme_audit=readme_audit,
    )

    final_row = conclusion[
        conclusion["claim"] == "Checkpoint is ready to commit and tag."
    ].iloc[0]

    assert final_row["status"] == "Passed"