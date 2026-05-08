from __future__ import annotations

from pathlib import Path

import pandas as pd


CLAIMS = [
    {
        "claim": "No strategy dominates across all regimes on both return and risk.",
        "status": "Survived",
        "evidence_quality": "Supported by full-period, reference, and holdout comparison",
        "interpretation": (
            "The project produced objective-dependent winners rather than one universal winner."
        ),
    },
    {
        "claim": "Buy and Hold is the best raw compounding strategy in bull-heavy regimes.",
        "status": "Survived",
        "evidence_quality": "Survived holdout",
        "interpretation": (
            "Buy and Hold dominated the 2016-2026 holdout on CAGR and Calmar because the period strongly favoured full equity exposure."
        ),
    },
    {
        "claim": "SPY 12M Absolute Momentum is the best overall strategy.",
        "status": "Failed",
        "evidence_quality": "Failed holdout",
        "interpretation": (
            "SPY 12M was excellent in the reference period but materially lagged Buy and Hold in the 2016-2026 holdout. It should not be called the best overall strategy."
        ),
    },
    {
        "claim": "SPY 12M Absolute Momentum is a strong defensive timing strategy.",
        "status": "Survived",
        "evidence_quality": "Survived reference, weakened in holdout",
        "interpretation": (
            "SPY 12M sharply improved the reference-period return/drawdown profile but did not reduce holdout drawdown versus Buy and Hold. Its role is defensive timing, not universal superiority."
        ),
    },
    {
        "claim": "Momentum/cash filters can lag badly in V-shaped recovery and bull-heavy regimes.",
        "status": "Survived",
        "evidence_quality": "Supported by holdout",
        "interpretation": (
            "The 2016-2026 holdout included fast rebounds and strong equity rallies. SPY 12M paid a meaningful opportunity-cost premium for protection."
        ),
    },
    {
        "claim": "Annual rebalanced core-satellite helps reduce tracking-error regret versus pure momentum.",
        "status": "Survived",
        "evidence_quality": "Supported by holdout",
        "interpretation": (
            "Annual core-satellite outperformed pure SPY 12M in the holdout because the permanent SPY core stayed invested during bull/rebound periods."
        ),
    },
    {
        "claim": "Annual rebalanced core-satellite is regime-dependent.",
        "status": "Survived",
        "evidence_quality": "Mixed reference/holdout evidence",
        "interpretation": (
            "It underperformed SPY 12M in the reference period but outperformed SPY 12M in the holdout. This supports the idea that core-satellite is a regime compromise, not a universal winner."
        ),
    },
    {
        "claim": "50/30/20 diversified signal portfolio is a defensive/capital-preservation portfolio.",
        "status": "Survived",
        "evidence_quality": "Survived both periods",
        "interpretation": (
            "It consistently reduced drawdown and had strong Calmar behaviour, but sacrificed too much CAGR to be a wealth-growth replacement."
        ),
    },
    {
        "claim": "50/30/20 diversified signal portfolio is a wealth-growth replacement for SPY 12M.",
        "status": "Failed",
        "evidence_quality": "Failed full-period and holdout comparison",
        "interpretation": (
            "It improved drawdown efficiency but lagged SPY 12M meaningfully on CAGR."
        ),
    },
    {
        "claim": "70/20/10 and 80/10/10 solve the multi-asset wealth-growth problem.",
        "status": "Failed",
        "evidence_quality": "Failed pre-declared decision gates",
        "interpretation": (
            "Increasing SPY weight improved CAGR but eroded drawdown protection. Neither variant cleared the pre-declared gates."
        ),
    },
    {
        "claim": "EFA 200D SMA is a validated non-SPY signal.",
        "status": "Survived",
        "evidence_quality": "Survived neighbouring-window robustness",
        "interpretation": (
            "EFA daily SMA robustness supported the 150D-250D region. EFA 200D remains a return-enhancing candidate for EFA itself."
        ),
    },
    {
        "claim": "EFA 10M SMA is a validated return-enhancing monthly signal.",
        "status": "Failed",
        "evidence_quality": "Failed monthly robustness as return-enhancing",
        "interpretation": (
            "Monthly SMA windows mainly reduced drawdown but did not beat Buy and Hold on CAGR. EFA 10M is risk-control, not return-enhancing."
        ),
    },
    {
        "claim": "The multi-asset wealth-growth branch should stop for now.",
        "status": "Survived",
        "evidence_quality": "Supported by 50/30/20, 70/20/10, and 80/10/10 tests",
        "interpretation": (
            "The tested multi-asset portfolios are useful defensively but did not beat SPY 12M as the core wealth-growth solution."
        ),
    },
]


def create_final_validation_conclusion() -> pd.DataFrame:
    return pd.DataFrame(CLAIMS)


def write_final_validation_conclusion_markdown(
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    table = conclusion.to_markdown(index=False)

    content = f"""# Final Validation Conclusion

This report converts the full-period, reference-period, and holdout-period evidence into final project claims.

It is the capstone report for the ETF/SPY phase of Market Strats Lab.

## Regime Warning

The results are heavily influenced by the 1993-2026 US macro regime: declining rates for much of the sample, US mega-cap dominance, repeated central-bank liquidity support, fast V-shaped recoveries, and the post-2023 AI-led rally.

The 2016-2026 holdout was not neutral. It included:
- a strong 2016-2019 bull market,
- a fast 2020 crash and V-shaped recovery,
- a 2022 drawdown followed by a sharp 2023 rebound,
- a powerful 2023-2026 mega-cap/AI-led rally.

That sequence is structurally unfavourable to slow 12-month momentum/cash filters. It weakens claims that SPY 12M is universally superior, but it does not invalidate its defensive timing role.

## Final Claim Table

{table}

## Final Project Conclusion

No strategy dominates across all regimes.

The project produced objective-dependent winners:

| Objective | Best current answer |
|---|---|
| Raw wealth in bull-heavy regimes | Buy and Hold |
| Defensive timing | SPY 12M Absolute Momentum |
| Behavioural compromise / tracking-error regret control | Annual Rebalanced SPY Core-Satellite |
| Capital preservation / lowest drawdown | 50/30/20 Defensive Diversified Portfolio |

## What Failed

- SPY 12M as the universal best overall strategy.
- Multi-asset portfolios as superior wealth-growth replacements for SPY 12M.
- EFA 10M as a validated return-enhancing monthly signal.
- Drawdown tranche / dip-buying as a standalone strategy.
- Continued weight tweaking after 50/30/20, 70/20/10, and 80/10/10.

## What Survived

- SPY 12M as a defensive timing strategy.
- Annual core-satellite as a regime compromise.
- 50/30/20 as a defensive diversified portfolio.
- EFA 200D SMA as a validated EFA-specific trend signal.

## Research Phase Status

The ETF/SPY research phase is effectively complete.

The next serious work is not more strategy variants. It is validation and implementation realism:

1. Raw-close signal sensitivity.
2. Cash proxy sensitivity.
3. Tax-aware analysis.
4. Execution/slippage sensitivity.
5. Data-source cross-check.
6. Walk-forward variants beyond a single holdout split.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_final_validation_conclusion(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    conclusion = create_final_validation_conclusion()

    csv_path = reports_dir / "final_validation_conclusion.csv"
    markdown_path = reports_dir / "final_validation_conclusion.md"

    conclusion.to_csv(csv_path, index=False)
    write_final_validation_conclusion_markdown(conclusion, markdown_path)

    print("\nFinal validation conclusion:")
    print(conclusion.to_string(index=False))
    print(f"\nSaved final validation conclusion to: {csv_path}")
    print(f"Saved final validation conclusion markdown to: {markdown_path}")

    return conclusion