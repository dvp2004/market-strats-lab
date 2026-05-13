from pathlib import Path

from market_strats.analysis.regime_switch_overlay_validation_conclusion import (
    create_regime_switch_overlay_current_winners,
    create_regime_switch_overlay_validation_conclusion,
    write_regime_switch_overlay_validation_conclusion_markdown,
)


def test_create_regime_switch_overlay_validation_conclusion_contains_statuses():
    conclusion = create_regime_switch_overlay_validation_conclusion()

    assert not conclusion.empty
    assert {"claim", "status", "evidence_quality", "interpretation"}.issubset(
        conclusion.columns
    )
    assert "Survived" in set(conclusion["status"])
    assert "Failed" in set(conclusion["status"])
    assert "Not yet" in set(conclusion["status"])


def test_create_regime_switch_overlay_current_winners_contains_overlay():
    winners = create_regime_switch_overlay_current_winners()

    assert not winners.empty
    assert {"objective", "winner", "reason"}.issubset(winners.columns)
    assert "SPY Trend Regime Switch Overlay 3D Confirmed" in set(winners["winner"])


def test_write_regime_switch_overlay_validation_conclusion_markdown(tmp_path: Path):
    conclusion = create_regime_switch_overlay_validation_conclusion()
    winners = create_regime_switch_overlay_current_winners()

    output_path = tmp_path / "regime_switch_overlay_validation_conclusion.md"

    write_regime_switch_overlay_validation_conclusion_markdown(
        conclusion=conclusion,
        winners=winners,
        output_path=output_path,
    )

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Regime Switch Overlay Validation Conclusion" in text
    assert "Current Winners" in text
    assert "3D confirmed overlay" in text