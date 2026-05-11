from pathlib import Path

from market_strats.analysis.relative_momentum_validation_conclusion import (
    create_relative_momentum_validation_conclusion,
    write_relative_momentum_validation_conclusion_markdown,
)


def test_create_relative_momentum_validation_conclusion_contains_statuses():
    conclusion = create_relative_momentum_validation_conclusion()

    assert not conclusion.empty
    assert {"claim", "status", "evidence_quality", "interpretation"}.issubset(
        conclusion.columns
    )
    assert "Survived" in set(conclusion["status"])
    assert "Failed" in set(conclusion["status"])
    assert "Not yet" in set(conclusion["status"])


def test_write_relative_momentum_validation_conclusion_markdown(tmp_path: Path):
    conclusion = create_relative_momentum_validation_conclusion()
    output_path = tmp_path / "relative_momentum_validation_conclusion.md"

    write_relative_momentum_validation_conclusion_markdown(
        conclusion=conclusion,
        output_path=output_path,
    )

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Relative Momentum Validation Conclusion" in text
    assert "Phase 2 Conclusion" in text
    assert "Trend confirmation works" in text