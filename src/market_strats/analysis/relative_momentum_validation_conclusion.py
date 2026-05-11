from __future__ import annotations

from pathlib import Path

import pandas as pd


CLAIMS = [
    {
        "claim": "Trend confirmation improves relative momentum allocator quality.",
        "status": "Survived",
        "evidence_quality": "Survived reference and holdout",
        "interpretation": (
            "Adding the 200D trend filter improved the equal-weight allocator in both "
            "reference and holdout periods. This supports the idea that 12M momentum alone "
            "can be stale and needs current-trend confirmation."
        ),
    },
    {
        "claim": "The equal-weight trend-confirmed allocator is the best balanced Phase 2 allocator.",
        "status": "Survived",
        "evidence_quality": "Survived full-period, reference, and holdout comparison",
        "interpretation": (
            "It had the strongest allocator CAGR in both reference and holdout periods while "
            "maintaining better drawdown behaviour than SPY buy-and-hold."
        ),
    },
    {
        "claim": "The constrained trend-confirmed allocator is the best defensive Phase 2 allocator.",
        "status": "Survived",
        "evidence_quality": "Survived full-period, reference, and holdout comparison",
        "interpretation": (
            "Constraints reduced volatility and drawdown and produced the strongest defensive "
            "profile among Phase 2 allocators, but with meaningful CAGR sacrifice."
        ),
    },
    {
        "claim": "Portfolio constraints improve allocator liveability.",
        "status": "Survived",
        "evidence_quality": "Supported by full-period and split-period results",
        "interpretation": (
            "Max asset and group caps improved Calmar, volatility, and drawdown. The cost was "
            "lower terminal wealth and lower CAGR."
        ),
    },
    {
        "claim": "Inverse-volatility weighting solves the allocator problem.",
        "status": "Failed",
        "evidence_quality": "Failed versus equal-weight trend-confirmed allocator",
        "interpretation": (
            "Inverse-volatility weighting reduced volatility but sacrificed too much CAGR. "
            "It is useful defensively, but it did not become the leading allocator."
        ),
    },
    {
        "claim": "Phase 2 relative momentum allocators beat SPY 12M as wealth-growth strategies.",
        "status": "Failed",
        "evidence_quality": "Failed holdout comparison",
        "interpretation": (
            "The best Phase 2 allocator lagged SPY 12M on holdout CAGR. Phase 2 has not "
            "yet produced a superior wealth-growth replacement."
        ),
    },
    {
        "claim": "Phase 2 relative momentum allocators beat SPY buy-and-hold in bull-heavy regimes.",
        "status": "Failed",
        "evidence_quality": "Failed holdout comparison",
        "interpretation": (
            "SPY buy-and-hold dominated the 2016-2026 holdout on raw compounding and Calmar. "
            "The allocators were too defensive for that regime."
        ),
    },
    {
        "claim": "Relative momentum allocation adds defensive/regime-diversifying value.",
        "status": "Survived",
        "evidence_quality": "Supported by reference and full-period behaviour",
        "interpretation": (
            "The allocators performed well in the reference period and improved drawdown "
            "relative to SPY buy-and-hold. Their value is defensive and regime-diversifying, "
            "not universal wealth maximisation."
        ),
    },
    {
        "claim": "Sentiment, macro, and ML are justified immediately.",
        "status": "Not yet",
        "evidence_quality": "Portfolio-construction issues remain",
        "interpretation": (
            "The allocator still needs clearer regime logic before adding complex data layers. "
            "Adding sentiment or macro now would risk hiding basic allocation weaknesses."
        ),
    },
    {
        "claim": "The next research question is regime selection.",
        "status": "Survived",
        "evidence_quality": "Implied by reference/holdout split",
        "interpretation": (
            "The allocator did well in the mixed/choppy reference period but lagged badly in "
            "the bull-heavy holdout. The next question is when to prefer tactical allocation "
            "versus staying closer to SPY exposure."
        ),
    },
]


def create_relative_momentum_validation_conclusion() -> pd.DataFrame:
    return pd.DataFrame(CLAIMS)


def write_relative_momentum_validation_conclusion_markdown(
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    table = conclusion.to_markdown(index=False)

    content = f"""# Relative Momentum Validation Conclusion

This report converts the Phase 2 tactical asset allocation evidence into final claims.

It should be read after:

- `relative_momentum_variant_decision_report.csv`
- `relative_momentum_holdout_validation.csv`
- `relative_momentum_holdout_validation_summary.csv`

## Final Phase 2 Claim Table

{table}

## Phase 2 Conclusion

The Phase 2 relative momentum allocator branch produced a useful defensive tactical allocator, not a superior wealth-growth allocator.

The key finding is:

> Trend confirmation works. Constraints work defensively. But the allocator still fails to beat SPY 12M as a wealth-growth replacement in the bull-heavy holdout period.

## Current Phase 2 Winners

| Objective | Current Best Answer |
|---|---|
| Best balanced Phase 2 allocator | Top 3 Equal Weight Trend-Confirmed Relative Momentum |
| Best defensive Phase 2 allocator | Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum |
| Best raw wealth benchmark | SPY Buy and Hold |
| Main defensive timing benchmark | SPY 12M Absolute Momentum |

## What Failed

- Plain relative momentum without trend confirmation.
- Inverse-volatility weighting as the main solution.
- Phase 2 allocators as SPY 12M wealth-growth replacements.
- Phase 2 allocators as SPY buy-and-hold replacements in bull-heavy regimes.
- Adding sentiment/macro/ML immediately.

## What Survived

- Trend confirmation.
- Portfolio constraints as a defensive/liveability tool.
- Equal-weight trend-confirmed allocator as the best balanced Phase 2 candidate.
- Constrained trend-confirmed allocator as the best defensive Phase 2 candidate.
- The need for regime selection before adding more complex signals.

## Next Research Direction

The next question is no longer:

> Can relative momentum allocation work?

The better question is:

> Can we identify when tactical allocation should be preferred over staying closer to SPY exposure?

That points toward a future regime overlay, but it should be built carefully.

Potential next steps, in order:

1. Build a regime diagnostic report comparing allocator performance during equity bull, bear, recovery, inflation shock, and commodity-led periods.
2. Add exposure diagnostics showing when the allocator was underweight SPY during bull markets.
3. Test a simple equity-regime overlay, not a sentiment or ML model yet.
4. Only after that consider macro/sentiment inputs.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_relative_momentum_validation_conclusion(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    conclusion = create_relative_momentum_validation_conclusion()

    csv_path = reports_dir / "relative_momentum_validation_conclusion.csv"
    markdown_path = reports_dir / "relative_momentum_validation_conclusion.md"

    conclusion.to_csv(csv_path, index=False)
    write_relative_momentum_validation_conclusion_markdown(
        conclusion=conclusion,
        output_path=markdown_path,
    )

    print("\nRelative momentum validation conclusion:")
    print(conclusion.to_string(index=False))
    print(f"\nSaved relative momentum validation conclusion to: {csv_path}")
    print(f"Saved relative momentum validation conclusion markdown to: {markdown_path}")

    return conclusion