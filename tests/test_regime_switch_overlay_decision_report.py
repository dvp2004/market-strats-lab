from pathlib import Path

import pandas as pd

from market_strats.analysis.regime_switch_overlay_decision_report import (
    create_regime_switch_overlay_claim_report,
    create_regime_switch_overlay_decision_report,
    write_regime_switch_overlay_decision_markdown,
)


def _write_metrics_file(path: Path, strategy_names: list[str]) -> None:
    rows = []

    for index, strategy in enumerate(strategy_names):
        rows.append(
            {
                "strategy": strategy,
                "start_date": "2006-01-01",
                "end_date": "2026-01-01",
                "end_value": 50_000 + index * 1_000,
                "cagr_pct": 8.0 + index,
                "calmar": 0.25 + index * 0.05,
                "volatility_pct": 15.0 - index * 0.5,
                "sharpe": 0.6 + index * 0.02,
                "sortino": 0.7 + index * 0.02,
                "max_drawdown_pct": -35.0 + index,
                "worst_month_pct": -10.0,
                "exposure_time_pct": 90.0,
                "trade_count": 20 + index,
            }
        )

    pd.DataFrame(rows).to_csv(path, index=False)


def test_create_regime_switch_overlay_decision_report_runs(tmp_path: Path):
    _write_metrics_file(
        tmp_path / "regime_switch_spy_trend_regime_switch_overlay_metrics.csv",
        [
            "SPY Trend Regime Switch Overlay",
        ],
    )

    _write_metrics_file(
        tmp_path
        / "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv",
        [
            "SPY Trend Regime Switch Overlay 3D Confirmed",
            "SPY Buy and Hold",
            "SPY 12-Month Absolute Momentum",
            "Top 3 Equal Weight Trend Confirmed Relative Momentum Allocator",
            "Top 3 Equal Weight Trend Confirmed Constrained Relative Momentum Allocator",
        ],
    )

    report = create_regime_switch_overlay_decision_report(reports_dir=tmp_path)

    assert not report.empty
    assert "classification" in report.columns
    assert "final_verdict" in report.columns
    assert "calmar_delta_vs_spy_12m" in report.columns
    assert "SPY Trend Regime Switch Overlay 3D Confirmed" in set(report["strategy"])


def test_create_regime_switch_overlay_claim_report_contains_statuses():
    report = create_regime_switch_overlay_claim_report()

    assert not report.empty
    assert {"claim", "status", "evidence_quality", "interpretation"}.issubset(
        report.columns
    )
    assert "Survived" in set(report["status"])
    assert "Failed" in set(report["status"])
    assert "Not yet" in set(report["status"])


def test_write_regime_switch_overlay_decision_markdown(tmp_path: Path):
    decision_report = pd.DataFrame(
        {
            "strategy": ["Test Strategy"],
            "classification": ["Test Classification"],
            "available": [True],
            "cagr_pct": [10.0],
            "calmar": [0.4],
            "max_drawdown_pct": [-25.0],
            "final_verdict": ["Test verdict."],
        }
    )

    claim_report = create_regime_switch_overlay_claim_report()

    output_path = tmp_path / "regime_switch_overlay_decision_report.md"

    write_regime_switch_overlay_decision_markdown(
        decision_report=decision_report,
        claim_report=claim_report,
        output_path=output_path,
    )

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Regime Switch Overlay Decision Report" in text
    assert "Decision Table" in text
    assert "Claim Table" in text