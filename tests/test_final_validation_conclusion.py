from pathlib import Path

from market_strats.analysis.final_validation_conclusion import (
    create_final_validation_conclusion,
    write_final_validation_conclusion_markdown,
)


def test_create_final_validation_conclusion_contains_required_statuses():
    conclusion = create_final_validation_conclusion()

    assert not conclusion.empty
    assert {"claim", "status", "evidence_quality", "interpretation"}.issubset(
        conclusion.columns
    )
    assert "Failed" in set(conclusion["status"])
    assert "Survived" in set(conclusion["status"])


def test_write_final_validation_conclusion_markdown(tmp_path: Path):
    conclusion = create_final_validation_conclusion()
    output_path = tmp_path / "final_validation_conclusion.md"

    write_final_validation_conclusion_markdown(conclusion, output_path)

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Final Validation Conclusion" in text
    assert "Regime Warning" in text
    assert "No strategy dominates across all regimes" in text