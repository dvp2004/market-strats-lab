from __future__ import annotations

from pathlib import Path

import pandas as pd


RELATIVE_MOMENTUM_VARIANTS = [
    {
        "source_file": (
            "relative_momentum_top_3_equal_weight_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "Top 3 Equal Weight Relative Momentum Allocator",
        "classification": "Rejected baseline",
        "verdict": (
            "Valid baseline but weak. It reduced drawdown versus SPY buy-and-hold, "
            "but lagged SPY 12M on CAGR, Calmar, volatility, and max drawdown."
        ),
    },
    {
        "source_file": (
            "relative_momentum_top_3_inverse_volatility_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "Top 3 Inverse Volatility Relative Momentum Allocator",
        "classification": "Defensive improvement, still weak",
        "verdict": (
            "Inverse-volatility sizing improved drawdown and volatility versus equal-weight, "
            "but reduced CAGR and still failed versus SPY 12M."
        ),
    },
    {
        "source_file": (
            "relative_momentum_top_3_equal_weight_trend_confirmed_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "Top 3 Equal Weight Trend Confirmed Relative Momentum Allocator",
        "classification": "Phase 2 leading candidate",
        "verdict": (
            "Current best Phase 2 allocator. Trend confirmation improved CAGR, Calmar, "
            "and drawdown versus the equal-weight baseline. It beats SPY 12M on Calmar "
            "and drawdown, but not on CAGR, Sharpe, Sortino, or volatility."
        ),
    },
    {
        "source_file": (
            "relative_momentum_top_3_inverse_volatility_trend_confirmed_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "Top 3 Inverse Volatility Trend Confirmed Relative Momentum Allocator",
        "classification": "Defensive variant",
        "verdict": (
            "Smoother defensive version. It improved volatility and drawdown, but gave up "
            "too much CAGR versus the equal-weight trend-confirmed version."
        ),
    },
    {
        "source_file": (
            "relative_momentum_top_3_equal_weight_trend_confirmed_constrained_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "Top 3 Equal Weight Trend Confirmed Constrained Relative Momentum Allocator",
        "classification": "Constrained Phase 2 candidate",
        "verdict": (
            "Tests whether practical concentration limits improve liveability and "
            "drawdown control versus the unconstrained trend-confirmed leader."
        ),
    },
]


BENCHMARK_ROWS = [
    {
        "source_file": (
            "relative_momentum_top_3_equal_weight_trend_confirmed_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "SPY Buy and Hold",
        "classification": "Raw wealth benchmark",
        "verdict": (
            "Highest raw compounding benchmark over this common period, but much larger "
            "drawdown than the tactical allocators."
        ),
    },
    {
        "source_file": (
            "relative_momentum_top_3_equal_weight_trend_confirmed_relative_momentum_allocator_metrics.csv"
        ),
        "strategy": "SPY 12-Month Absolute Momentum",
        "classification": "Phase 1 defensive timing benchmark",
        "verdict": (
            "Still the main benchmark to beat. It has higher CAGR than the Phase 2 "
            "allocators, but worse drawdown and lower Calmar than the leading "
            "trend-confirmed allocator."
        ),
    },
]


def _load_strategy_row(
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


def _calculate_delta(value: object, benchmark_value: object) -> object:
    if value == "" or benchmark_value == "":
        return ""

    try:
        return round(float(value) - float(benchmark_value), 3)
    except (TypeError, ValueError):
        return ""


def create_relative_momentum_variant_decision_report(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    all_items = RELATIVE_MOMENTUM_VARIANTS + BENCHMARK_ROWS

    loaded_rows: list[dict] = []

    spy_12m_row = _load_strategy_row(
        reports_dir=reports_dir,
        source_file=(
            "relative_momentum_top_3_equal_weight_trend_confirmed_relative_momentum_allocator_metrics.csv"
        ),
        strategy="SPY 12-Month Absolute Momentum",
    )

    spy_12m_cagr = _safe_get(spy_12m_row, "cagr_pct")
    spy_12m_calmar = _safe_get(spy_12m_row, "calmar")
    spy_12m_max_drawdown = _safe_get(spy_12m_row, "max_drawdown_pct")
    spy_12m_volatility = _safe_get(spy_12m_row, "volatility_pct")

    for item in all_items:
        row = _load_strategy_row(
            reports_dir=reports_dir,
            source_file=item["source_file"],
            strategy=item["strategy"],
        )

        cagr = _safe_get(row, "cagr_pct")
        calmar = _safe_get(row, "calmar")
        max_drawdown = _safe_get(row, "max_drawdown_pct")
        volatility = _safe_get(row, "volatility_pct")

        loaded_rows.append(
            {
                "strategy": item["strategy"],
                "classification": item["classification"],
                "start_date": _safe_get(row, "start_date"),
                "end_date": _safe_get(row, "end_date"),
                "end_value": _safe_get(row, "end_value"),
                "cagr_pct": cagr,
                "cagr_delta_vs_spy_12m_pct_points": _calculate_delta(
                    cagr,
                    spy_12m_cagr,
                ),
                "calmar": calmar,
                "calmar_delta_vs_spy_12m": _calculate_delta(
                    calmar,
                    spy_12m_calmar,
                ),
                "volatility_pct": volatility,
                "volatility_delta_vs_spy_12m_pct_points": _calculate_delta(
                    volatility,
                    spy_12m_volatility,
                ),
                "sharpe": _safe_get(row, "sharpe"),
                "sortino": _safe_get(row, "sortino"),
                "max_drawdown_pct": max_drawdown,
                "drawdown_improvement_vs_spy_12m_pct_points": _calculate_delta(
                    max_drawdown,
                    spy_12m_max_drawdown,
                ),
                "worst_month_pct": _safe_get(row, "worst_month_pct"),
                "exposure_time_pct": _safe_get(row, "exposure_time_pct"),
                "trade_count": _safe_get(row, "trade_count"),
                "source_file": item["source_file"],
                "verdict": item["verdict"],
            }
        )

    output = pd.DataFrame(loaded_rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output


def write_relative_momentum_variant_decision_markdown(
    report: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    display_columns = [
        "strategy",
        "classification",
        "start_date",
        "end_date",
        "end_value",
        "cagr_pct",
        "cagr_delta_vs_spy_12m_pct_points",
        "calmar",
        "calmar_delta_vs_spy_12m",
        "max_drawdown_pct",
        "drawdown_improvement_vs_spy_12m_pct_points",
        "volatility_pct",
        "sharpe",
        "sortino",
        "exposure_time_pct",
        "trade_count",
        "verdict",
    ]

    available_columns = [column for column in display_columns if column in report.columns]
    table = report[available_columns].to_markdown(index=False)

    content = f"""# Relative Momentum Variant Decision Report

This report consolidates the Phase 2 tactical asset allocation variants.

It compares the relative momentum allocators against SPY buy-and-hold and SPY 12-month absolute momentum.

## Decision Table

{table}

## Current Phase 2 Conclusion

- Equal-weight relative momentum was a valid but weak baseline.
- Inverse-volatility weighting improved risk but reduced CAGR.
- Trend confirmation materially improved the allocator.
- The equal-weight trend-confirmed allocator is the current Phase 2 leader.
- It beats SPY 12M on drawdown and Calmar, but not on CAGR, Sharpe, Sortino, or volatility.
- The next problem is portfolio construction: concentration and practical allocation constraints.
- Sentiment, macro, and ML should still wait until the price/risk allocator is structurally stronger.

## Next Research Direction

The next implementation should add practical portfolio constraints, such as:

- maximum single-asset weight,
- maximum commodity weight,
- maximum high-volatility sleeve weight,
- optional minimum cash buffer,
- concentration diagnostics.

Do not add news sentiment or macro features yet.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_relative_momentum_variant_decision_report(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = create_relative_momentum_variant_decision_report(reports_dir=reports_dir)

    csv_path = reports_dir / "relative_momentum_variant_decision_report.csv"
    markdown_path = reports_dir / "relative_momentum_variant_decision_report.md"

    report.to_csv(csv_path, index=False)
    write_relative_momentum_variant_decision_markdown(report, markdown_path)

    print("\nRelative momentum variant decision report:")
    print(report.to_string(index=False))
    print(f"\nSaved relative momentum variant decision report to: {csv_path}")
    print(f"Saved relative momentum variant decision markdown to: {markdown_path}")

    return report