from pathlib import Path

import pandas as pd

from market_strats.analysis.phase3a_robustness_conclusion import (
    create_phase3a_robustness_conclusion,
    create_phase3a_robustness_current_status,
    write_phase3a_robustness_conclusion_markdown,
)


def test_create_phase3a_robustness_conclusion_runs(tmp_path: Path):
    pd.DataFrame(
        {
            "period": ["full", "full", "full", "full", "holdout", "holdout"],
            "slippage_bps": [5.0, 10.0, 25.0, 50.0, 5.0, 50.0],
            "cagr_pct": [10.2, 9.9, 9.1, 7.7, 12.0, 9.7],
            "calmar": [0.42, 0.41, 0.37, 0.30, 0.50, 0.38],
            "max_drawdown_pct": [-24.0, -24.0, -24.5, -25.0, -24.0, -25.0],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_slippage_sensitivity.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "period": ["full", "holdout"],
            "cagr_drag_pct_points": [-2.5, -2.3],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_slippage_sensitivity_summary.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "period": ["full", "holdout"],
            "zero_cash_cagr_pct": [9.8, 11.7],
            "zero_cash_calmar": [0.41, 0.49],
            "zero_cash_max_drawdown_pct": [-24.0, -24.0],
            "zero_cash_cagr_drag_pct_points": [-0.37, -0.37],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_cash_sensitivity_summary.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "period": ["full", "holdout"],
            "raw_minus_adjusted_cagr_pct_points": [-0.49, -0.34],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_raw_close_signal_sensitivity_summary.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "period": ["full", "holdout"],
            "signal_type": ["raw_close_signal", "raw_close_signal"],
            "cagr_pct": [9.87, 12.0],
            "calmar": [0.414, 0.503],
            "max_drawdown_pct": [-23.84, -23.84],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_raw_close_signal_sensitivity.csv",
        index=False,
    )

    conclusion = create_phase3a_robustness_conclusion(tmp_path)

    assert not conclusion.empty
    assert {"claim", "status", "evidence_quality", "interpretation"}.issubset(
        conclusion.columns
    )
    assert "Failed" in set(conclusion["status"])
    assert "Survived" in set(conclusion["status"])


def test_create_phase3a_robustness_current_status_runs(tmp_path: Path):
    pd.DataFrame(
        {
            "period": ["full", "full", "full", "full"],
            "slippage_bps": [5.0, 10.0, 25.0, 50.0],
            "cagr_pct": [10.2, 9.9, 9.1, 7.7],
            "calmar": [0.42, 0.41, 0.37, 0.30],
            "max_drawdown_pct": [-24.0, -24.0, -24.5, -25.0],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_slippage_sensitivity.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "period": ["full"],
            "zero_cash_cagr_pct": [9.8],
            "zero_cash_calmar": [0.41],
            "zero_cash_max_drawdown_pct": [-24.0],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_cash_sensitivity_summary.csv",
        index=False,
    )

    pd.DataFrame(
        {
            "period": ["full", "holdout"],
            "signal_type": ["raw_close_signal", "raw_close_signal"],
            "cagr_pct": [9.87, 12.0],
            "calmar": [0.414, 0.503],
            "max_drawdown_pct": [-23.84, -23.84],
        }
    ).to_csv(
        tmp_path / "regime_switch_overlay_raw_close_signal_sensitivity.csv",
        index=False,
    )

    status = create_phase3a_robustness_current_status(tmp_path)

    assert not status.empty
    assert {"robustness_check", "cagr_pct", "calmar", "max_drawdown_pct", "status"}.issubset(
        status.columns
    )


def test_write_phase3a_robustness_conclusion_markdown(tmp_path: Path):
    conclusion = pd.DataFrame(
        {
            "claim": ["Test claim"],
            "status": ["Survived"],
            "evidence_quality": ["Test evidence"],
            "interpretation": ["Test interpretation"],
        }
    )

    status = pd.DataFrame(
        {
            "robustness_check": ["Test check"],
            "cagr_pct": [10.0],
            "calmar": [0.4],
            "max_drawdown_pct": [-25.0],
            "status": ["Passed"],
        }
    )

    output_path = tmp_path / "phase3a_robustness_conclusion.md"

    write_phase3a_robustness_conclusion_markdown(
        conclusion=conclusion,
        status=status,
        output_path=output_path,
    )

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Phase 3A Robustness Conclusion" in text
    assert "Current Robustness Status" in text