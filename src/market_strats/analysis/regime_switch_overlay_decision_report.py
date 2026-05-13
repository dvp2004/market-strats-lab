from __future__ import annotations

from pathlib import Path

import pandas as pd


DECISION_ROWS = [
    {
        "source_file": "regime_switch_spy_trend_regime_switch_overlay_metrics.csv",
        "strategy": "SPY Trend Regime Switch Overlay",
        "classification": "Rejected / whipsaw-prone raw overlay",
        "final_verdict": (
            "Failed as a new leader. It improved drawdown versus SPY 12M but lost too much "
            "CAGR and failed versus the constrained allocator on defensive quality. The audit "
            "showed excessive whipsaw around the 200D boundary."
        ),
    },
    {
        "source_file": (
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        "strategy": "SPY Trend Regime Switch Overlay 3D Confirmed",
        "classification": "Current best overall system candidate",
        "final_verdict": (
            "Current strongest full-period system. It beat SPY 12M on CAGR, Calmar, "
            "volatility, max drawdown, Sharpe, Sortino, and rolling-window survivability. "
            "It still trails SPY buy-and-hold on raw terminal wealth."
        ),
    },
    {
        "source_file": (
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        "strategy": "SPY Buy and Hold",
        "classification": "Raw wealth benchmark",
        "final_verdict": (
            "Still the raw terminal-wealth benchmark. It has the highest CAGR in this "
            "comparison but carries much larger max drawdown and weaker liveability."
        ),
    },
    {
        "source_file": (
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        "strategy": "SPY 12-Month Absolute Momentum",
        "classification": "Phase 1 defensive timing benchmark",
        "final_verdict": (
            "Strong defensive timing benchmark, but now beaten by the 3D confirmed overlay "
            "on both return and risk metrics in the full-period comparison."
        ),
    },
    {
        "source_file": (
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        "strategy": "Top 3 Equal Weight Trend Confirmed Relative Momentum Allocator",
        "classification": "Best standalone balanced allocator",
        "final_verdict": (
            "Still the best standalone Phase 2 allocator, but it is now inferior to the "
            "3D confirmed overlay on full-period CAGR, Calmar, drawdown, and rolling-window behaviour."
        ),
    },
    {
        "source_file": (
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        "strategy": (
            "Top 3 Equal Weight Trend Confirmed Constrained Relative Momentum Allocator"
        ),
        "classification": "Best standalone defensive allocator",
        "final_verdict": (
            "Best standalone defensive allocator, but the 3D confirmed overlay now has much "
            "higher CAGR and better Calmar while keeping comparable drawdown control."
        ),
    },
]


CLAIM_ROWS = [
    {
        "claim": "The raw SPY 200D binary overlay is sufficient.",
        "status": "Failed",
        "evidence_quality": "Failed metrics and whipsaw audit",
        "interpretation": (
            "The raw overlay was too sensitive around the 200D boundary and produced excessive "
            "switching and whipsaw."
        ),
    },
    {
        "claim": "The 3D confirmation filter reduces whipsaw damage.",
        "status": "Survived",
        "evidence_quality": "Supported by audit comparison",
        "interpretation": (
            "Switch count and whipsaw count fell materially after adding 3-day confirmation."
        ),
    },
    {
        "claim": "The 3D confirmed overlay beats SPY 12M as a full-period system.",
        "status": "Survived",
        "evidence_quality": "Supported by full-period metrics",
        "interpretation": (
            "The 3D overlay beat SPY 12M on CAGR, Calmar, volatility, drawdown, Sharpe, and Sortino."
        ),
    },
    {
        "claim": "The 3D confirmed overlay beats SPY buy-and-hold on raw wealth.",
        "status": "Failed",
        "evidence_quality": "Failed full-period terminal wealth comparison",
        "interpretation": (
            "SPY buy-and-hold still had the higher terminal value and CAGR, but with much worse drawdown."
        ),
    },
    {
        "claim": "The 3D confirmed overlay is the current best overall risk-adjusted candidate.",
        "status": "Survived",
        "evidence_quality": "Supported by full-period and rolling-window metrics",
        "interpretation": (
            "It currently has the strongest balance of CAGR, drawdown, Calmar, volatility, and rolling-window stability."
        ),
    },
    {
        "claim": "More overlay parameter testing is justified immediately.",
        "status": "Not yet",
        "evidence_quality": "Overfitting risk after strong 3D result",
        "interpretation": (
            "The next step should be holdout validation, not testing 5D, 7D, bands, blends, macro, or sentiment."
        ),
    },
]


def _load_strategy_row(
    reports_dir: Path,
    source_file: str,
    strategy: str,
) -> pd.Series | None:
    path = reports_dir / source_file

    if not path.exists():
        return None

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


def _safe_get(row: pd.Series | None, column: str, default: object = "") -> object:
    if row is None:
        return default

    if column not in row.index:
        return default

    value = row[column]

    if pd.isna(value):
        return default

    return value


def _to_float(value: object) -> float | None:
    try:
        if value == "":
            return None

        return float(value)
    except (TypeError, ValueError):
        return None


def _calculate_delta(value: object, benchmark_value: object) -> object:
    value_float = _to_float(value)
    benchmark_float = _to_float(benchmark_value)

    if value_float is None or benchmark_float is None:
        return ""

    return round(value_float - benchmark_float, 3)


def create_regime_switch_overlay_decision_report(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    spy_12m_row = _load_strategy_row(
        reports_dir=reports_dir,
        source_file=(
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        strategy="SPY 12-Month Absolute Momentum",
    )

    spy_buy_hold_row = _load_strategy_row(
        reports_dir=reports_dir,
        source_file=(
            "regime_switch_spy_trend_regime_switch_overlay_3d_confirmed_metrics.csv"
        ),
        strategy="SPY Buy and Hold",
    )

    rows: list[dict] = []

    for item in DECISION_ROWS:
        row = _load_strategy_row(
            reports_dir=reports_dir,
            source_file=item["source_file"],
            strategy=item["strategy"],
        )

        if row is None:
            rows.append(
                {
                    "strategy": item["strategy"],
                    "classification": item["classification"],
                    "available": False,
                    "source_file": item["source_file"],
                    "final_verdict": (
                        "Metrics file not available. Re-run the corresponding overlay "
                        "configuration to populate this row."
                    ),
                }
            )
            continue

        cagr = _safe_get(row, "cagr_pct")
        calmar = _safe_get(row, "calmar")
        max_drawdown = _safe_get(row, "max_drawdown_pct")
        volatility = _safe_get(row, "volatility_pct")
        end_value = _safe_get(row, "end_value")

        rows.append(
            {
                "strategy": item["strategy"],
                "classification": item["classification"],
                "available": True,
                "start_date": _safe_get(row, "start_date"),
                "end_date": _safe_get(row, "end_date"),
                "end_value": end_value,
                "cagr_pct": cagr,
                "cagr_delta_vs_spy_12m_pct_points": _calculate_delta(
                    cagr,
                    _safe_get(spy_12m_row, "cagr_pct"),
                ),
                "cagr_delta_vs_spy_buy_hold_pct_points": _calculate_delta(
                    cagr,
                    _safe_get(spy_buy_hold_row, "cagr_pct"),
                ),
                "calmar": calmar,
                "calmar_delta_vs_spy_12m": _calculate_delta(
                    calmar,
                    _safe_get(spy_12m_row, "calmar"),
                ),
                "calmar_delta_vs_spy_buy_hold": _calculate_delta(
                    calmar,
                    _safe_get(spy_buy_hold_row, "calmar"),
                ),
                "volatility_pct": volatility,
                "volatility_delta_vs_spy_12m_pct_points": _calculate_delta(
                    volatility,
                    _safe_get(spy_12m_row, "volatility_pct"),
                ),
                "sharpe": _safe_get(row, "sharpe"),
                "sortino": _safe_get(row, "sortino"),
                "max_drawdown_pct": max_drawdown,
                "drawdown_improvement_vs_spy_12m_pct_points": _calculate_delta(
                    max_drawdown,
                    _safe_get(spy_12m_row, "max_drawdown_pct"),
                ),
                "drawdown_improvement_vs_spy_buy_hold_pct_points": _calculate_delta(
                    max_drawdown,
                    _safe_get(spy_buy_hold_row, "max_drawdown_pct"),
                ),
                "worst_month_pct": _safe_get(row, "worst_month_pct"),
                "exposure_time_pct": _safe_get(row, "exposure_time_pct"),
                "trade_count": _safe_get(row, "trade_count"),
                "source_file": item["source_file"],
                "final_verdict": item["final_verdict"],
            }
        )

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output


def create_regime_switch_overlay_claim_report() -> pd.DataFrame:
    return pd.DataFrame(CLAIM_ROWS)


def write_regime_switch_overlay_decision_markdown(
    decision_report: pd.DataFrame,
    claim_report: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    decision_columns = [
        "strategy",
        "classification",
        "available",
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
        "final_verdict",
    ]

    available_decision_columns = [
        column for column in decision_columns if column in decision_report.columns
    ]

    decision_table = decision_report[available_decision_columns].to_markdown(
        index=False
    )
    claim_table = claim_report.to_markdown(index=False)

    content = f"""# Regime Switch Overlay Decision Report

This report consolidates the regime-switch overlay branch.

It compares the raw 200D overlay, the 3D confirmed overlay, SPY benchmarks, and the relevant Phase 2 allocators.

## Decision Table

{decision_table}

## Claim Table

{claim_table}

## Current Conclusion

The raw SPY 200D regime-switch overlay failed because it was whipsaw-prone.

The 3D confirmed overlay materially improved the branch and is currently the best overall risk-adjusted system candidate produced by the project.

It beats SPY 12M on the full-period return/risk trade-off, but it does not beat SPY buy-and-hold on raw terminal wealth.

## Current Winners

| Objective | Current Winner |
|---|---|
| Raw terminal wealth | SPY Buy and Hold |
| Defensive timing benchmark | SPY 12M Absolute Momentum |
| Best standalone balanced allocator | Top 3 Equal Weight Trend-Confirmed Relative Momentum |
| Best standalone defensive allocator | Top 3 Equal Weight Trend-Confirmed Constrained Relative Momentum |
| Best overall full-period risk-adjusted system | SPY Trend Regime Switch Overlay 3D Confirmed |

## What Comes Next

The next step is holdout validation for the 3D confirmed overlay.

Do not test more confirmation windows, bands, soft blends, macro, sentiment, BTC, or individual stocks until the 3D overlay survives or fails holdout validation.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_regime_switch_overlay_decision_report(
    reports_dir: str | Path = "reports",
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    decision_report = create_regime_switch_overlay_decision_report(
        reports_dir=reports_dir
    )
    claim_report = create_regime_switch_overlay_claim_report()

    decision_csv_path = reports_dir / "regime_switch_overlay_decision_report.csv"
    claim_csv_path = reports_dir / "regime_switch_overlay_claim_report.csv"
    markdown_path = reports_dir / "regime_switch_overlay_decision_report.md"

    decision_report.to_csv(decision_csv_path, index=False)
    claim_report.to_csv(claim_csv_path, index=False)

    write_regime_switch_overlay_decision_markdown(
        decision_report=decision_report,
        claim_report=claim_report,
        output_path=markdown_path,
    )

    print("\nRegime switch overlay decision report:")
    print(decision_report.to_string(index=False))

    print("\nRegime switch overlay claim report:")
    print(claim_report.to_string(index=False))

    print(f"\nSaved regime switch overlay decision report to: {decision_csv_path}")
    print(f"Saved regime switch overlay claim report to: {claim_csv_path}")
    print(f"Saved regime switch overlay markdown to: {markdown_path}")

    return {
        "decision_report": decision_report,
        "claim_report": claim_report,
    }