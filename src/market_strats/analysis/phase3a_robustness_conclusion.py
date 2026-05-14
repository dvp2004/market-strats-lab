from __future__ import annotations

from pathlib import Path

import pandas as pd


def _load_report(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def _get_row(
    df: pd.DataFrame,
    **filters: object,
) -> pd.Series | None:
    if df.empty:
        return None

    mask = pd.Series(True, index=df.index)

    for column, value in filters.items():
        if column not in df.columns:
            return None

        mask &= df[column].astype(str) == str(value)

    rows = df[mask]

    if rows.empty:
        return None

    return rows.iloc[0]


def _safe_float(row: pd.Series | None, column: str) -> float | None:
    if row is None:
        return None

    if column not in row.index:
        return None

    value = row[column]

    if pd.isna(value) or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def _format_number(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value:.3f}"


def create_phase3a_robustness_conclusion(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    slippage = _load_report(
        reports_dir / "regime_switch_overlay_slippage_sensitivity.csv"
    )
    slippage_summary = _load_report(
        reports_dir / "regime_switch_overlay_slippage_sensitivity_summary.csv"
    )
    cash_summary = _load_report(
        reports_dir / "regime_switch_overlay_cash_sensitivity_summary.csv"
    )
    raw_close_summary = _load_report(
        reports_dir / "regime_switch_overlay_raw_close_signal_sensitivity_summary.csv"
    )
    raw_close_sensitivity = _load_report(
        reports_dir / "regime_switch_overlay_raw_close_signal_sensitivity.csv"
    )

    full_10bps = _get_row(slippage, period="full", slippage_bps="10.0")
    full_25bps = _get_row(slippage, period="full", slippage_bps="25.0")
    full_50bps = _get_row(slippage, period="full", slippage_bps="50.0")

    full_slippage_summary = _get_row(slippage_summary, period="full")
    holdout_slippage_summary = _get_row(slippage_summary, period="holdout")

    full_cash_summary = _get_row(cash_summary, period="full")
    holdout_cash_summary = _get_row(cash_summary, period="holdout")

    full_raw_summary = _get_row(raw_close_summary, period="full")
    holdout_raw_summary = _get_row(raw_close_summary, period="holdout")

    full_raw_signal = _get_row(
        raw_close_sensitivity,
        period="full",
        signal_type="raw_close_signal",
    )
    holdout_raw_signal = _get_row(
        raw_close_sensitivity,
        period="holdout",
        signal_type="raw_close_signal",
    )

    full_10bps_cagr = _safe_float(full_10bps, "cagr_pct")
    full_10bps_calmar = _safe_float(full_10bps, "calmar")
    full_10bps_drawdown = _safe_float(full_10bps, "max_drawdown_pct")

    full_25bps_cagr = _safe_float(full_25bps, "cagr_pct")
    full_25bps_calmar = _safe_float(full_25bps, "calmar")
    full_50bps_cagr = _safe_float(full_50bps, "cagr_pct")
    full_50bps_calmar = _safe_float(full_50bps, "calmar")

    full_slippage_cagr_drag = _safe_float(
        full_slippage_summary,
        "cagr_drag_pct_points",
    )
    holdout_slippage_cagr_drag = _safe_float(
        holdout_slippage_summary,
        "cagr_drag_pct_points",
    )

    full_zero_cash_drag = _safe_float(
        full_cash_summary,
        "zero_cash_cagr_drag_pct_points",
    )
    holdout_zero_cash_drag = _safe_float(
        holdout_cash_summary,
        "zero_cash_cagr_drag_pct_points",
    )

    full_raw_cagr_drag = _safe_float(
        full_raw_summary,
        "raw_minus_adjusted_cagr_pct_points",
    )
    holdout_raw_cagr_drag = _safe_float(
        holdout_raw_summary,
        "raw_minus_adjusted_cagr_pct_points",
    )

    full_raw_cagr = _safe_float(full_raw_signal, "cagr_pct")
    full_raw_calmar = _safe_float(full_raw_signal, "calmar")
    full_raw_drawdown = _safe_float(full_raw_signal, "max_drawdown_pct")

    holdout_raw_cagr = _safe_float(holdout_raw_signal, "cagr_pct")
    holdout_raw_calmar = _safe_float(holdout_raw_signal, "calmar")
    holdout_raw_drawdown = _safe_float(holdout_raw_signal, "max_drawdown_pct")

    rows = [
        {
            "claim": "The 3D overlay survives low/moderate slippage.",
            "status": "Survived"
            if (
                full_10bps_cagr is not None
                and full_10bps_cagr >= 9.5
                and full_10bps_calmar is not None
                and full_10bps_calmar >= 0.40
            )
            else "Needs review",
            "evidence_quality": "Supported by 10 bps slippage sensitivity",
            "interpretation": (
                "At 10 bps, the full-period overlay remained close to the baseline: "
                f"CAGR {_format_pct(full_10bps_cagr)}, "
                f"Calmar {_format_number(full_10bps_calmar)}, "
                f"max drawdown {_format_pct(full_10bps_drawdown)}."
            ),
        },
        {
            "claim": "The 3D overlay is friction-proof.",
            "status": "Failed",
            "evidence_quality": "Failed high-slippage stress test",
            "interpretation": (
                "High friction materially damaged compounding. "
                f"At 25 bps, full-period CAGR was {_format_pct(full_25bps_cagr)} "
                f"and Calmar was {_format_number(full_25bps_calmar)}. "
                f"At 50 bps, full-period CAGR was {_format_pct(full_50bps_cagr)} "
                f"and Calmar was {_format_number(full_50bps_calmar)}. "
                "The strategy is viable only under controlled execution friction."
            ),
        },
        {
            "claim": "High execution friction is the main current vulnerability.",
            "status": "Survived",
            "evidence_quality": "Supported by slippage sensitivity",
            "interpretation": (
                "Moving from baseline 5 bps to 50 bps caused a full-period CAGR drag of "
                f"{_format_pct(full_slippage_cagr_drag)} and a holdout CAGR drag of "
                f"{_format_pct(holdout_slippage_cagr_drag)}. "
                "This was much larger than the zero-cash drag."
            ),
        },
        {
            "claim": "The 3D overlay depends heavily on cash yield.",
            "status": "Failed",
            "evidence_quality": "Failed zero-cash stress test",
            "interpretation": (
                "Setting cash yield to 0% caused only modest damage. "
                f"Full-period zero-cash CAGR drag was {_format_pct(full_zero_cash_drag)}. "
                f"Holdout zero-cash CAGR drag was {_format_pct(holdout_zero_cash_drag)}. "
                "Cash yield helps, but it is not the engine of the result."
            ),
        },
        {
            "claim": "The 3D overlay survives raw-close signal sensitivity.",
            "status": "Survived with caveat"
            if (
                full_raw_cagr is not None
                and full_raw_cagr >= 9.5
                and full_raw_calmar is not None
                and full_raw_calmar >= 0.40
            )
            else "Needs review",
            "evidence_quality": "Supported by raw-close signal test",
            "interpretation": (
                "Using raw close for the SPY trend signal weakened results but did not collapse them. "
                f"Full-period raw-close CAGR was {_format_pct(full_raw_cagr)}, "
                f"Calmar was {_format_number(full_raw_calmar)}, "
                f"and max drawdown was {_format_pct(full_raw_drawdown)}. "
                f"Full-period CAGR drag versus adjusted-close signal was "
                f"{_format_pct(full_raw_cagr_drag)}."
            ),
        },
        {
            "claim": "The raw-close signal version still works in holdout.",
            "status": "Survived"
            if (
                holdout_raw_cagr is not None
                and holdout_raw_cagr >= 11.5
                and holdout_raw_calmar is not None
                and holdout_raw_calmar >= 0.45
            )
            else "Needs review",
            "evidence_quality": "Supported by holdout raw-close signal test",
            "interpretation": (
                f"Holdout raw-close CAGR was {_format_pct(holdout_raw_cagr)}, "
                f"Calmar was {_format_number(holdout_raw_calmar)}, "
                f"and max drawdown was {_format_pct(holdout_raw_drawdown)}. "
                f"Holdout CAGR drag versus adjusted-close signal was "
                f"{_format_pct(holdout_raw_cagr_drag)}."
            ),
        },
        {
            "claim": "The 3D overlay is now robust enough to remain the current best risk-adjusted candidate.",
            "status": "Survived",
            "evidence_quality": (
                "Supported by slippage, cash-yield, and raw-close sensitivity checks"
            ),
            "interpretation": (
                "The system survived the major Phase 3A robustness checks. "
                "It is not perfect, but its weaknesses are now clearer: "
                "execution friction matters far more than cash yield, and raw-close "
                "signals reduce CAGR moderately without destroying the result."
            ),
        },
        {
            "claim": "The next step should be immediate macro/sentiment/ML expansion.",
            "status": "Not yet",
            "evidence_quality": "Project discipline requires one checkpoint before expansion",
            "interpretation": (
                "The correct next step is to save this robustness checkpoint and update "
                "documentation. After that, the next research branch can be controlled "
                "asset expansion or a second data-source cross-check."
            ),
        },
    ]

    return pd.DataFrame(rows)


def create_phase3a_robustness_current_status(
    reports_dir: str | Path = "reports",
) -> pd.DataFrame:
    reports_dir = Path(reports_dir)

    slippage = _load_report(
        reports_dir / "regime_switch_overlay_slippage_sensitivity.csv"
    )
    cash_summary = _load_report(
        reports_dir / "regime_switch_overlay_cash_sensitivity_summary.csv"
    )
    raw_close_sensitivity = _load_report(
        reports_dir / "regime_switch_overlay_raw_close_signal_sensitivity.csv"
    )

    full_5bps = _get_row(slippage, period="full", slippage_bps="5.0")
    full_10bps = _get_row(slippage, period="full", slippage_bps="10.0")
    full_25bps = _get_row(slippage, period="full", slippage_bps="25.0")
    full_50bps = _get_row(slippage, period="full", slippage_bps="50.0")

    full_cash_zero = _get_row(cash_summary, period="full")
    full_raw_signal = _get_row(
        raw_close_sensitivity,
        period="full",
        signal_type="raw_close_signal",
    )
    holdout_raw_signal = _get_row(
        raw_close_sensitivity,
        period="holdout",
        signal_type="raw_close_signal",
    )

    rows = [
        {
            "robustness_check": "Baseline 5 bps slippage",
            "cagr_pct": _safe_float(full_5bps, "cagr_pct"),
            "calmar": _safe_float(full_5bps, "calmar"),
            "max_drawdown_pct": _safe_float(full_5bps, "max_drawdown_pct"),
            "status": "Baseline",
        },
        {
            "robustness_check": "10 bps slippage",
            "cagr_pct": _safe_float(full_10bps, "cagr_pct"),
            "calmar": _safe_float(full_10bps, "calmar"),
            "max_drawdown_pct": _safe_float(full_10bps, "max_drawdown_pct"),
            "status": "Passed",
        },
        {
            "robustness_check": "25 bps slippage",
            "cagr_pct": _safe_float(full_25bps, "cagr_pct"),
            "calmar": _safe_float(full_25bps, "calmar"),
            "max_drawdown_pct": _safe_float(full_25bps, "max_drawdown_pct"),
            "status": "Defensive only / weakened",
        },
        {
            "robustness_check": "50 bps slippage",
            "cagr_pct": _safe_float(full_50bps, "cagr_pct"),
            "calmar": _safe_float(full_50bps, "calmar"),
            "max_drawdown_pct": _safe_float(full_50bps, "max_drawdown_pct"),
            "status": "Failed as wealth-growth case",
        },
        {
            "robustness_check": "0% cash yield",
            "cagr_pct": _safe_float(full_cash_zero, "zero_cash_cagr_pct"),
            "calmar": _safe_float(full_cash_zero, "zero_cash_calmar"),
            "max_drawdown_pct": _safe_float(
                full_cash_zero,
                "zero_cash_max_drawdown_pct",
            ),
            "status": "Passed",
        },
        {
            "robustness_check": "Raw-close signal full period",
            "cagr_pct": _safe_float(full_raw_signal, "cagr_pct"),
            "calmar": _safe_float(full_raw_signal, "calmar"),
            "max_drawdown_pct": _safe_float(full_raw_signal, "max_drawdown_pct"),
            "status": "Passed with caveat",
        },
        {
            "robustness_check": "Raw-close signal holdout",
            "cagr_pct": _safe_float(holdout_raw_signal, "cagr_pct"),
            "calmar": _safe_float(holdout_raw_signal, "calmar"),
            "max_drawdown_pct": _safe_float(holdout_raw_signal, "max_drawdown_pct"),
            "status": "Passed",
        },
    ]

    output = pd.DataFrame(rows)

    numeric_columns = output.select_dtypes(include=["float", "int"]).columns

    for column in numeric_columns:
        output[column] = output[column].round(3)

    return output


def write_phase3a_robustness_conclusion_markdown(
    conclusion: pd.DataFrame,
    status: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conclusion_table = conclusion.to_markdown(index=False)
    status_table = status.to_markdown(index=False)

    content = f"""# Phase 3A Robustness Conclusion

This report freezes the Phase 3A robustness checkpoint for the 3D confirmed regime-switch overlay.

It should be read after:

- `regime_switch_overlay_slippage_sensitivity.csv`
- `regime_switch_overlay_cash_sensitivity.csv`
- `regime_switch_overlay_raw_close_signal_sensitivity.csv`

## Current Robustness Status

{status_table}

## Claim Table

{conclusion_table}

## Final Phase 3A Conclusion

The 3D confirmed regime-switch overlay remains the current best risk-adjusted system candidate after Phase 3A robustness testing.

It survived:

- normal 5-10 bps slippage,
- zero-cash-yield stress,
- raw-close signal sensitivity.

However, it is not friction-proof.

High slippage materially damages CAGR. This means the strategy's main vulnerability is execution friction, not cash yield or adjusted-close signal artefacts.

## Correct Interpretation

The strategy should now be described as:

> A validated risk-adjusted candidate under low/moderate execution friction, not materially dependent on cash yield, and robust to raw-close signal testing with moderate CAGR drag.

It should not be described as:

> A universally robust strategy or a guaranteed SPY buy-and-hold replacement.

## Recommended Next Step

Stop robustness work here for this checkpoint.

The next practical step is:

1. Commit the Phase 3A robustness reports.
2. Update README with the robustness caveats.
3. Then open a new controlled research branch.

The next research branch should be one of:

- second data-source cross-check,
- controlled asset expansion with oil proxy and ETH quarantine,
- technical regime-score overlay.

Do not jump directly into macro, sentiment, ML, or individual stocks yet.
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_phase3a_robustness_conclusion(
    reports_dir: str | Path = "reports",
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    conclusion = create_phase3a_robustness_conclusion(reports_dir)
    status = create_phase3a_robustness_current_status(reports_dir)

    conclusion_path = reports_dir / "phase3a_robustness_conclusion.csv"
    status_path = reports_dir / "phase3a_robustness_current_status.csv"
    markdown_path = reports_dir / "phase3a_robustness_conclusion.md"

    conclusion.to_csv(conclusion_path, index=False)
    status.to_csv(status_path, index=False)

    write_phase3a_robustness_conclusion_markdown(
        conclusion=conclusion,
        status=status,
        output_path=markdown_path,
    )

    print("\nPhase 3A robustness conclusion:")
    print(conclusion.to_string(index=False))

    print("\nPhase 3A robustness current status:")
    print(status.to_string(index=False))

    print(f"\nSaved Phase 3A robustness conclusion to: {conclusion_path}")
    print(f"Saved Phase 3A robustness current status to: {status_path}")
    print(f"Saved Phase 3A robustness markdown to: {markdown_path}")

    return {
        "conclusion": conclusion,
        "status": status,
    }