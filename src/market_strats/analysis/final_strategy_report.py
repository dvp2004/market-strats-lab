from __future__ import annotations

from pathlib import Path

import pandas as pd


FINAL_REPORT_ROWS = [
    {
        "source_file": "SPY_strategy_comparison_metrics.csv",
        "strategy": "Buy and Hold",
        "final_label": "Passive benchmark",
        "final_verdict": (
            "Best simple passive wealth benchmark, but worst drawdown pain. "
            "Useful as baseline, not the preferred risk-controlled strategy."
        ),
    },
    {
        "source_file": "SPY_strategy_comparison_metrics.csv",
        "strategy": "12-Month Absolute Momentum",
        "final_label": "Leading simple core strategy",
        "final_verdict": (
            "Current leading simple strategy. Wealth-equivalent compounding with "
            "materially lower drawdown than buy-and-hold."
        ),
    },
    {
        "source_file": "SPY_core_satellite_diagnostic.csv",
        "strategy": "60/40 Annual Rebalanced Core-Satellite SPY B&H + 12M Momentum",
        "final_label": "Highest gross terminal-wealth SPY architecture",
        "start_date_fallback": "1993-01-29",
        "end_date_fallback": "2026-05-01",
        "final_verdict": (
            "Highest gross terminal wealth among SPY architectures tested. "
            "Useful, but tax-sensitive and higher drawdown than pure 12M momentum."
        ),
    },
    {
        "source_file": "candidate_portfolio_validated_signal_portfolio_metrics.csv",
        "strategy": "Validated Signal Portfolio",
        "final_label": "Defensive diversified portfolio",
        "final_verdict": (
            "Best defensive diversified portfolio. Strong Calmar and drawdown control, "
            "but too much CAGR sacrifice to replace SPY 12M for wealth growth."
        ),
    },
    {
        "source_file": "candidate_portfolio_growth_biased_signal_portfolio_metrics.csv",
        "strategy": "Growth Biased Signal Portfolio",
        "final_label": "Near-miss growth defensive portfolio",
        "final_verdict": (
            "Improved CAGR versus 50/30/20 and passed drawdown/Calmar gates, "
            "but failed the pre-declared CAGR gate."
        ),
    },
    {
        "source_file": "candidate_portfolio_spy_dominant_signal_portfolio_metrics.csv",
        "strategy": "SPY Dominant Signal Portfolio",
        "final_label": "Failed SPY-dominant sensitivity check",
        "final_verdict": (
            "Moved closer to SPY 12M but failed both CAGR and drawdown gates. "
            "Do not continue this weight-tweaking branch."
        ),
    },
]


def _load_report_row(
    reports_dir: Path,
    source_file: str,
    strategy: str,
) -> pd.Series:
    path = reports_dir / source_file

    if not path.exists():
        raise FileNotFoundError(f"Missing required report file: {path}")

    df = pd.read_csv(path)

    if "strategy" not in df.columns:
        raise ValueError(f"{path} does not contain a strategy column")

    row = df[df["strategy"] == strategy]

    if row.empty:
        available = sorted(df["strategy"].dropna().unique())
        raise ValueError(
            f"Strategy '{strategy}' not found in {path}. Available: {available}"
        )

    return row.iloc[0]


def _safe_get(row: pd.Series, column: str, default: object = "") -> object:
    if column not in row.index:
        return default

    value = row[column]

    if pd.isna(value):
        return default

    return value

def _safe_calmar(row: pd.Series) -> object:
    if "calmar" in row.index and not pd.isna(row["calmar"]):
        return row["calmar"]

    if "cagr_pct" not in row.index or "max_drawdown_pct" not in row.index:
        return ""

    cagr = row["cagr_pct"]
    max_drawdown = row["max_drawdown_pct"]

    if pd.isna(cagr) or pd.isna(max_drawdown) or max_drawdown == 0:
        return ""

    return round(float(cagr) / abs(float(max_drawdown)), 3)

def create_final_strategy_decision_report(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    rows: list[dict] = []

    for item in FINAL_REPORT_ROWS:
        source_file = item["source_file"]
        strategy = item["strategy"]

        row = _load_report_row(
            reports_dir=reports_dir,
            source_file=source_file,
            strategy=strategy,
        )

        rows.append(
            {
                "strategy": strategy,
                "final_label": item["final_label"],
                "start_date": _safe_get(row, "start_date", item.get("start_date_fallback", "")),
                "end_date": _safe_get(row, "end_date", item.get("end_date_fallback", "")),
                "end_value": _safe_get(row, "end_value"),
                "cagr_pct": _safe_get(row, "cagr_pct"),
                "calmar": _safe_calmar(row),
                "volatility_pct": _safe_get(row, "volatility_pct"),
                "sharpe": _safe_get(row, "sharpe"),
                "sortino": _safe_get(row, "sortino"),
                "max_drawdown_pct": _safe_get(row, "max_drawdown_pct"),
                "worst_3y_cagr_pct": _safe_get(row, "worst_3y_cagr_pct"),
                "worst_5y_cagr_pct": _safe_get(row, "worst_5y_cagr_pct"),
                "exposure_time_pct": _safe_get(row, "exposure_time_pct"),
                "trade_count": _safe_get(row, "trade_count"),
                "source_file": source_file,
                "final_verdict": item["final_verdict"],
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output


def write_final_strategy_decision_markdown(
    report: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    display_columns = [
        "strategy",
        "final_label",
        "start_date",
        "end_date",
        "end_value",
        "cagr_pct",
        "calmar",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "exposure_time_pct",
        "trade_count",
        "final_verdict",
    ]

    available_columns = [column for column in display_columns if column in report.columns]
    table = report[available_columns].to_markdown(index=False)

    content = f"""# Final Strategy Decision Report

This report consolidates the main surviving and rejected strategy branches.

It is a decision table, not another optimisation output.

## Final Decision Table

{table}

## Current Project Conclusion

- SPY 12M Absolute Momentum remains the leading simple core strategy.
- Annual rebalanced SPY core-satellite produced the highest gross SPY terminal wealth, but is tax-sensitive and higher-drawdown than pure 12M momentum.
- The 50/30/20 diversified signal portfolio is defensive, not a wealth-growth replacement.
- The 70/20/10 and 80/10/10 portfolio variants failed the pre-declared wealth-growth gates.
- The multi-asset wealth-growth branch should stop for now.
- The next serious stage is validation, especially walk-forward testing and assumptions audits.

## Next Validation Priorities

1. Walk-forward / out-of-sample validation.
2. Raw-close signal sensitivity.
3. Cash proxy sensitivity.
4. Tax-aware analysis.
5. Execution assumption sensitivity.
6. Data-source cross-check.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_final_strategy_decision_report(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = create_final_strategy_decision_report(reports_dir=reports_dir)

    csv_path = reports_dir / "final_strategy_decision_report.csv"
    markdown_path = reports_dir / "final_strategy_decision_report.md"

    report.to_csv(csv_path, index=False)
    write_final_strategy_decision_markdown(report, markdown_path)

    print("\nFinal strategy decision report:")
    print(report.to_string(index=False))
    print(f"\nSaved final strategy decision report to: {csv_path}")
    print(f"Saved final strategy decision markdown to: {markdown_path}")

    return report