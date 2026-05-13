from __future__ import annotations

from pathlib import Path

import pandas as pd


CLAIMS = [
    {
        "claim": "The raw SPY 200D binary overlay is sufficient.",
        "status": "Failed",
        "evidence_quality": "Failed full-period metrics and whipsaw audit",
        "interpretation": (
            "The raw 200D overlay was too sensitive around the 200D boundary. "
            "It produced excessive switching and did not become a new leader."
        ),
    },
    {
        "claim": "The raw SPY 200D overlay failed mainly because of whipsaw.",
        "status": "Survived",
        "evidence_quality": "Supported by overlay audit",
        "interpretation": (
            "The raw overlay had 114 switches, 86 whipsaws, a 75.44% whipsaw rate, "
            "and a median switch duration of only 5 trading days. This confirms that "
            "boundary noise around the 200D SMA was a major failure mechanism."
        ),
    },
    {
        "claim": "The 3D confirmation filter reduced whipsaw damage.",
        "status": "Survived",
        "evidence_quality": "Supported by audit comparison",
        "interpretation": (
            "The 3D confirmed overlay reduced switches from 114 to 52, reduced whipsaws "
            "from 86 to 29, and increased the median switch duration from 5 to 20 trading days."
        ),
    },
    {
        "claim": "The 3D confirmed overlay beats SPY 12M as a full-period system.",
        "status": "Survived",
        "evidence_quality": "Supported by full-period comparison",
        "interpretation": (
            "Full-period, the 3D overlay beat SPY 12M on CAGR, Calmar, max drawdown, "
            "volatility, Sharpe, Sortino, terminal value, and rolling-window survivability."
        ),
    },
    {
        "claim": "The 3D confirmed overlay beats SPY 12M in holdout.",
        "status": "Survived",
        "evidence_quality": "Supported by 2016-2026 holdout comparison",
        "interpretation": (
            "In the holdout, the 3D overlay produced 12.06% CAGR and 0.506 Calmar versus "
            "SPY 12M's 11.49% CAGR and 0.341 Calmar. It also had a materially lower max "
            "drawdown: -23.83% versus -33.72%."
        ),
    },
    {
        "claim": "The 3D confirmed overlay passes the strict SPY 12M triple gate in holdout.",
        "status": "Survived",
        "evidence_quality": "Supported by holdout CAGR, Calmar, and drawdown comparison",
        "interpretation": (
            "The overlay beat SPY 12M in holdout on all three strict gates: CAGR, Calmar, "
            "and max drawdown."
        ),
    },
    {
        "claim": "The 3D confirmed overlay passes the strict SPY 12M triple gate in reference.",
        "status": "Failed / near miss",
        "evidence_quality": "Reference drawdown comparison slightly failed",
        "interpretation": (
            "In the reference period, the 3D overlay beat SPY 12M on CAGR and Calmar, "
            "but its max drawdown was slightly worse: -19.06% versus -18.61%. "
            "The difference is small, but the strict gate was not fully passed."
        ),
    },
    {
        "claim": "The 3D confirmed overlay beats SPY buy-and-hold on raw wealth.",
        "status": "Failed",
        "evidence_quality": "Failed full-period and holdout raw CAGR comparison",
        "interpretation": (
            "SPY buy-and-hold still wins raw terminal wealth and raw CAGR, especially in "
            "bull-heavy regimes. The overlay is not the raw wealth winner."
        ),
    },
    {
        "claim": "The 3D confirmed overlay is the current best overall risk-adjusted project candidate.",
        "status": "Survived",
        "evidence_quality": "Supported by full-period, rolling-window, and holdout evidence",
        "interpretation": (
            "The 3D overlay is currently the best balance of return, drawdown, Calmar, "
            "volatility, and rolling-window stability. It is not the best raw wealth strategy, "
            "but it is the strongest risk-adjusted system built so far."
        ),
    },
    {
        "claim": "The standalone constrained allocator remains the best pure defensive allocator.",
        "status": "Survived",
        "evidence_quality": "Supported by allocator and holdout comparisons",
        "interpretation": (
            "The constrained allocator often has the best or near-best defensive profile, "
            "but its CAGR sacrifice makes it weaker than the 3D overlay as a complete system."
        ),
    },
    {
        "claim": "More confirmation-window, band, blend, macro, sentiment, BTC, or individual-stock testing is justified immediately.",
        "status": "Not yet",
        "evidence_quality": "Overfitting risk after successful 3D result",
        "interpretation": (
            "The project now has a strong candidate. The correct next step is documentation, "
            "README update, and GitHub cleanup, not more parameter testing."
        ),
    },
    {
        "claim": "The next project step should be final documentation and repository polish.",
        "status": "Survived",
        "evidence_quality": "Current research branch has a validated checkpoint",
        "interpretation": (
            "The regime-switch branch has enough evidence to document the result clearly. "
            "The next practical step is updating the README, documenting the methodology, "
            "and pushing the cleaned project state."
        ),
    },
]


CURRENT_WINNERS = [
    {
        "objective": "Raw terminal wealth",
        "winner": "SPY Buy and Hold",
        "reason": (
            "Still has the highest raw CAGR and terminal value, but with much larger drawdown."
        ),
    },
    {
        "objective": "Simple defensive timing benchmark",
        "winner": "SPY 12-Month Absolute Momentum",
        "reason": (
            "Strong simple timing benchmark, but beaten by the 3D overlay on the full-period "
            "and holdout risk-adjusted comparison."
        ),
    },
    {
        "objective": "Best standalone balanced allocator",
        "winner": "Top 3 Equal Weight Trend-Confirmed Relative Momentum Allocator",
        "reason": (
            "Best standalone Phase 2 allocator by balance of CAGR and drawdown before overlay logic."
        ),
    },
    {
        "objective": "Best standalone defensive allocator",
        "winner": "Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum Allocator",
        "reason": (
            "Best standalone defensive/liveability allocator, but lower CAGR than the 3D overlay."
        ),
    },
    {
        "objective": "Best overall risk-adjusted system",
        "winner": "SPY Trend Regime Switch Overlay 3D Confirmed",
        "reason": (
            "Best overall balance of CAGR, Calmar, drawdown, volatility, and rolling-window stability."
        ),
    },
]


def create_regime_switch_overlay_validation_conclusion() -> pd.DataFrame:
    return pd.DataFrame(CLAIMS)


def create_regime_switch_overlay_current_winners() -> pd.DataFrame:
    return pd.DataFrame(CURRENT_WINNERS)


def write_regime_switch_overlay_validation_conclusion_markdown(
    conclusion: pd.DataFrame,
    winners: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conclusion_table = conclusion.to_markdown(index=False)
    winners_table = winners.to_markdown(index=False)

    content = f"""# Regime Switch Overlay Validation Conclusion

This report freezes the current conclusion of the regime-switch overlay branch.

It should be read after:

- `regime_switch_overlay_decision_report.csv`
- `regime_switch_overlay_claim_report.csv`
- `regime_switch_overlay_audit.csv`
- `regime_switch_overlay_holdout_validation.csv`
- `regime_switch_overlay_holdout_validation_summary.csv`

## Claim Table

{conclusion_table}

## Current Winners

{winners_table}

## Final Regime-Switch Branch Conclusion

The raw SPY 200D binary overlay failed because it was too whipsaw-prone.

The 3D confirmed overlay fixed a major part of that problem and is currently the strongest overall risk-adjusted system produced by the project.

Full-period, it beat SPY 12M on CAGR, Calmar, max drawdown, volatility, Sharpe, Sortino, terminal value, and rolling-window survivability.

In holdout, it also beat SPY 12M on the strict triple gate:

- higher CAGR,
- higher Calmar,
- better max drawdown.

It does not beat SPY buy-and-hold on raw wealth. SPY buy-and-hold remains the raw compounding benchmark.

## Correct Interpretation

The 3D overlay is not a magic alpha machine.

It is a regime-aware risk-management system that keeps exposure to SPY when SPY is healthy and moves to a constrained tactical allocator after persistent trend deterioration.

Its main value is not maximising raw terminal wealth. Its value is improving the return/drawdown/liveability trade-off.

## What Should Not Happen Next

Do not immediately test:

- 5D confirmation,
- 7D confirmation,
- 1% / 2% bands,
- soft blends,
- macro filters,
- sentiment filters,
- BTC,
- individual stocks,
- ML models.

That would create optimisation creep after a strong result.

## Recommended Next Step

The next step is repository/documentation cleanup:

1. Update `README.md`.
2. Document Phase 1 and Phase 2 methodology.
3. Add a clear “Current Best System” section.
4. Explain caveats and non-goals.
5. Push the cleaned code and reports to GitHub.

Only after that should a new research branch be opened.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_validation_conclusion(
    reports_dir: str | Path = "reports",
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    conclusion = create_regime_switch_overlay_validation_conclusion()
    winners = create_regime_switch_overlay_current_winners()

    conclusion_path = reports_dir / "regime_switch_overlay_validation_conclusion.csv"
    winners_path = reports_dir / "regime_switch_overlay_current_winners.csv"
    markdown_path = reports_dir / "regime_switch_overlay_validation_conclusion.md"

    conclusion.to_csv(conclusion_path, index=False)
    winners.to_csv(winners_path, index=False)

    write_regime_switch_overlay_validation_conclusion_markdown(
        conclusion=conclusion,
        winners=winners,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay validation conclusion:")
    print(conclusion.to_string(index=False))

    print("\nRegime switch overlay current winners:")
    print(winners.to_string(index=False))

    print(f"\nSaved regime switch overlay validation conclusion to: {conclusion_path}")
    print(f"Saved regime switch overlay current winners to: {winners_path}")
    print(f"Saved regime switch overlay validation markdown to: {markdown_path}")

    return {
        "conclusion": conclusion,
        "winners": winners,
    }