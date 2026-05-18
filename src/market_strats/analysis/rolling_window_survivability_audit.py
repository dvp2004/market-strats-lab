from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def _phase7f_config(config: dict) -> dict:
    return config.get("phase7_rolling_window_survivability_audit", {})


def _load_input_returns(
    config: dict,
    reports_dir: str | Path,
) -> pd.DataFrame:
    phase_config = _phase7f_config(config)

    reports_dir = Path(reports_dir)
    input_report_name = str(
        phase_config.get("input_returns_report", "phase7d_bootstrap_input_returns.csv")
    )
    input_path = reports_dir / input_report_name

    require_existing = bool(phase_config.get("require_existing_input_report", True))

    if not input_path.exists() and require_existing:
        raise FileNotFoundError(
            f"Required rolling-window input return report not found: {input_path}. "
            "Run Phase 7D first to generate phase7d_bootstrap_input_returns.csv."
        )

    if not input_path.exists():
        return pd.DataFrame()

    returns = pd.read_csv(input_path)
    returns["date"] = pd.to_datetime(returns["date"])

    required_columns = {
        "date",
        "candidate_return",
        "buy_hold_return",
        "spy_12m_return",
    }
    missing = required_columns - set(returns.columns)

    if missing:
        raise ValueError(
            f"Rolling-window input returns missing columns: {sorted(missing)}"
        )

    for column in required_columns - {"date"}:
        returns[column] = pd.to_numeric(returns[column], errors="coerce")

    returns = returns.dropna(subset=sorted(required_columns)).copy()

    return returns.sort_values("date").reset_index(drop=True)


def _metrics_from_returns(
    returns: np.ndarray,
    initial_capital: float,
) -> dict[str, float]:
    if len(returns) == 0:
        raise ValueError("returns cannot be empty")

    equity = initial_capital * np.cumprod(1.0 + returns)
    ending_value = float(equity[-1])

    years = len(returns) / TRADING_DAYS_PER_YEAR

    if ending_value <= 0:
        cagr_pct = -100.0
    else:
        cagr_pct = ((ending_value / initial_capital) ** (1.0 / years) - 1.0) * 100.0

    rolling_high = np.maximum.accumulate(equity)
    drawdowns = (equity / rolling_high) - 1.0
    max_drawdown_pct = float(drawdowns.min() * 100.0)

    if max_drawdown_pct == 0:
        calmar = np.nan
    else:
        calmar = float(cagr_pct / abs(max_drawdown_pct))

    return {
        "end_value": ending_value,
        "cagr_pct": float(cagr_pct),
        "max_drawdown_pct": max_drawdown_pct,
        "calmar": calmar,
    }


def _rolling_windows_from_config(config: dict) -> list[dict]:
    phase_config = _phase7f_config(config)

    configured_windows = phase_config.get(
        "rolling_windows",
        [
            {"name": "1Y", "trading_days": 252},
            {"name": "3Y", "trading_days": 756},
            {"name": "5Y", "trading_days": 1260},
        ],
    )

    windows: list[dict] = []

    for window in configured_windows:
        windows.append(
            {
                "name": str(window["name"]),
                "trading_days": int(window["trading_days"]),
            }
        )

    return windows


def _create_rolling_window_metrics(
    input_returns: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    phase_config = _phase7f_config(config)
    initial_capital = float(phase_config.get("initial_capital", 10000.0))

    windows = _rolling_windows_from_config(config)
    rows: list[dict] = []

    strategy_columns = {
        "candidate": "candidate_return",
        "buy_hold": "buy_hold_return",
        "spy_12m": "spy_12m_return",
    }

    for window in windows:
        window_name = window["name"]
        window_days = int(window["trading_days"])

        if window_days <= 1:
            raise ValueError("rolling window trading_days must be greater than 1")

        if len(input_returns) < window_days:
            continue

        for end_idx in range(window_days - 1, len(input_returns)):
            start_idx = end_idx - window_days + 1
            window_slice = input_returns.iloc[start_idx : end_idx + 1].copy()

            row = {
                "window_name": window_name,
                "trading_days": window_days,
                "start_date": window_slice["date"].iloc[0].date().isoformat(),
                "end_date": window_slice["date"].iloc[-1].date().isoformat(),
            }

            for strategy_name, return_column in strategy_columns.items():
                metrics = _metrics_from_returns(
                    returns=window_slice[return_column].to_numpy(dtype=float),
                    initial_capital=initial_capital,
                )

                row[f"{strategy_name}_cagr_pct"] = round(metrics["cagr_pct"], 4)
                row[f"{strategy_name}_calmar"] = round(metrics["calmar"], 4)
                row[f"{strategy_name}_max_drawdown_pct"] = round(
                    metrics["max_drawdown_pct"],
                    4,
                )

            row["candidate_minus_buy_hold_cagr_pct_points"] = round(
                row["candidate_cagr_pct"] - row["buy_hold_cagr_pct"],
                4,
            )
            row["candidate_minus_buy_hold_calmar"] = round(
                row["candidate_calmar"] - row["buy_hold_calmar"],
                4,
            )
            row["candidate_minus_buy_hold_drawdown_pct_points"] = round(
                row["candidate_max_drawdown_pct"] - row["buy_hold_max_drawdown_pct"],
                4,
            )

            row["candidate_minus_spy_12m_cagr_pct_points"] = round(
                row["candidate_cagr_pct"] - row["spy_12m_cagr_pct"],
                4,
            )
            row["candidate_minus_spy_12m_calmar"] = round(
                row["candidate_calmar"] - row["spy_12m_calmar"],
                4,
            )
            row["candidate_minus_spy_12m_drawdown_pct_points"] = round(
                row["candidate_max_drawdown_pct"] - row["spy_12m_max_drawdown_pct"],
                4,
            )

            rows.append(row)

    return pd.DataFrame(rows)


def _share_true(series: pd.Series) -> float:
    if series.empty:
        return np.nan

    return float(series.astype(bool).mean())


def _create_window_survivability_summary(
    rolling_metrics: pd.DataFrame,
) -> pd.DataFrame:
    if rolling_metrics.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    for window_name, group in rolling_metrics.groupby("window_name", sort=False):
        rows.append(
            {
                "window_name": window_name,
                "trading_days": int(group["trading_days"].iloc[0]),
                "window_count": int(len(group)),
                "candidate_beats_spy_12m_cagr_share": round(
                    _share_true(
                        group["candidate_cagr_pct"] > group["spy_12m_cagr_pct"]
                    ),
                    4,
                ),
                "candidate_beats_spy_12m_calmar_share": round(
                    _share_true(
                        group["candidate_calmar"] > group["spy_12m_calmar"]
                    ),
                    4,
                ),
                "candidate_beats_spy_12m_drawdown_share": round(
                    _share_true(
                        group["candidate_max_drawdown_pct"]
                        > group["spy_12m_max_drawdown_pct"]
                    ),
                    4,
                ),
                "candidate_beats_buy_hold_cagr_share": round(
                    _share_true(
                        group["candidate_cagr_pct"] > group["buy_hold_cagr_pct"]
                    ),
                    4,
                ),
                "candidate_beats_buy_hold_calmar_share": round(
                    _share_true(
                        group["candidate_calmar"] > group["buy_hold_calmar"]
                    ),
                    4,
                ),
                "candidate_beats_buy_hold_drawdown_share": round(
                    _share_true(
                        group["candidate_max_drawdown_pct"]
                        > group["buy_hold_max_drawdown_pct"]
                    ),
                    4,
                ),
                "candidate_worst_cagr_pct": round(
                    float(group["candidate_cagr_pct"].min()),
                    4,
                ),
                "candidate_median_cagr_pct": round(
                    float(group["candidate_cagr_pct"].median()),
                    4,
                ),
                "candidate_worst_calmar": round(
                    float(group["candidate_calmar"].min()),
                    4,
                ),
                "candidate_median_calmar": round(
                    float(group["candidate_calmar"].median()),
                    4,
                ),
                "candidate_worst_max_drawdown_pct": round(
                    float(group["candidate_max_drawdown_pct"].min()),
                    4,
                ),
                "candidate_median_max_drawdown_pct": round(
                    float(group["candidate_max_drawdown_pct"].median()),
                    4,
                ),
                "worst_candidate_minus_spy_12m_cagr_pct_points": round(
                    float(group["candidate_minus_spy_12m_cagr_pct_points"].min()),
                    4,
                ),
                "worst_candidate_minus_buy_hold_cagr_pct_points": round(
                    float(group["candidate_minus_buy_hold_cagr_pct_points"].min()),
                    4,
                ),
            }
        )

    return pd.DataFrame(rows)


def _create_worst_window_report(
    rolling_metrics: pd.DataFrame,
) -> pd.DataFrame:
    if rolling_metrics.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    criteria = [
        {
            "criterion": "Worst candidate CAGR",
            "column": "candidate_cagr_pct",
            "ascending": True,
        },
        {
            "criterion": "Worst candidate Calmar",
            "column": "candidate_calmar",
            "ascending": True,
        },
        {
            "criterion": "Worst candidate max drawdown",
            "column": "candidate_max_drawdown_pct",
            "ascending": True,
        },
        {
            "criterion": "Worst candidate CAGR versus SPY 12M",
            "column": "candidate_minus_spy_12m_cagr_pct_points",
            "ascending": True,
        },
        {
            "criterion": "Worst candidate CAGR versus Buy & Hold",
            "column": "candidate_minus_buy_hold_cagr_pct_points",
            "ascending": True,
        },
    ]

    for window_name, group in rolling_metrics.groupby("window_name", sort=False):
        for criterion in criteria:
            sorted_group = group.sort_values(
                by=str(criterion["column"]),
                ascending=bool(criterion["ascending"]),
            )

            selected = sorted_group.iloc[0]

            rows.append(
                {
                    "window_name": window_name,
                    "criterion": criterion["criterion"],
                    "start_date": selected["start_date"],
                    "end_date": selected["end_date"],
                    "candidate_cagr_pct": selected["candidate_cagr_pct"],
                    "candidate_calmar": selected["candidate_calmar"],
                    "candidate_max_drawdown_pct": selected[
                        "candidate_max_drawdown_pct"
                    ],
                    "buy_hold_cagr_pct": selected["buy_hold_cagr_pct"],
                    "buy_hold_calmar": selected["buy_hold_calmar"],
                    "buy_hold_max_drawdown_pct": selected[
                        "buy_hold_max_drawdown_pct"
                    ],
                    "spy_12m_cagr_pct": selected["spy_12m_cagr_pct"],
                    "spy_12m_calmar": selected["spy_12m_calmar"],
                    "spy_12m_max_drawdown_pct": selected[
                        "spy_12m_max_drawdown_pct"
                    ],
                    "candidate_minus_spy_12m_cagr_pct_points": selected[
                        "candidate_minus_spy_12m_cagr_pct_points"
                    ],
                    "candidate_minus_buy_hold_cagr_pct_points": selected[
                        "candidate_minus_buy_hold_cagr_pct_points"
                    ],
                }
            )

    return pd.DataFrame(rows)


def _create_survivability_gate_report(
    summary: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    phase_config = _phase7f_config(config)

    spy_12m_calmar_gate = float(
        phase_config.get("min_candidate_beats_spy_12m_calmar_window_share", 0.55)
    )
    spy_12m_drawdown_gate = float(
        phase_config.get("min_candidate_beats_spy_12m_drawdown_window_share", 0.55)
    )
    buy_hold_calmar_gate = float(
        phase_config.get("min_candidate_beats_buy_hold_calmar_window_share", 0.60)
    )
    buy_hold_drawdown_gate = float(
        phase_config.get("min_candidate_beats_buy_hold_drawdown_window_share", 0.70)
    )
    buy_hold_cagr_max = float(
        phase_config.get(
            "max_candidate_beats_buy_hold_cagr_window_share_for_raw_wealth_hierarchy",
            0.50,
        )
    )
    worst_3y_cagr_floor = float(
        phase_config.get("max_allowed_worst_3y_candidate_cagr_pct", 0.0)
    )
    worst_5y_cagr_floor = float(
        phase_config.get("max_allowed_worst_5y_candidate_cagr_pct", 0.0)
    )

    rows: list[dict] = []

    for _, row in summary.iterrows():
        window_name = str(row["window_name"])

        checks = [
            {
                "claim": f"{window_name}: Candidate beats SPY 12M on Calmar in enough rolling windows.",
                "value": float(row["candidate_beats_spy_12m_calmar_share"]),
                "threshold": spy_12m_calmar_gate,
                "operator": ">=",
            },
            {
                "claim": f"{window_name}: Candidate has better drawdown than SPY 12M in enough rolling windows.",
                "value": float(row["candidate_beats_spy_12m_drawdown_share"]),
                "threshold": spy_12m_drawdown_gate,
                "operator": ">=",
            },
            {
                "claim": f"{window_name}: Candidate beats Buy & Hold on Calmar in enough rolling windows.",
                "value": float(row["candidate_beats_buy_hold_calmar_share"]),
                "threshold": buy_hold_calmar_gate,
                "operator": ">=",
            },
            {
                "claim": f"{window_name}: Candidate has better drawdown than Buy & Hold in enough rolling windows.",
                "value": float(row["candidate_beats_buy_hold_drawdown_share"]),
                "threshold": buy_hold_drawdown_gate,
                "operator": ">=",
            },
            {
                "claim": f"{window_name}: Candidate is not being falsely promoted as rolling raw-CAGR winner over Buy & Hold.",
                "value": float(row["candidate_beats_buy_hold_cagr_share"]),
                "threshold": buy_hold_cagr_max,
                "operator": "<=",
            },
        ]

        if window_name == "3Y":
            checks.append(
                {
                    "claim": "3Y: Candidate worst rolling CAGR avoids negative territory.",
                    "value": float(row["candidate_worst_cagr_pct"]),
                    "threshold": worst_3y_cagr_floor,
                    "operator": ">=",
                }
            )

        if window_name == "5Y":
            checks.append(
                {
                    "claim": "5Y: Candidate worst rolling CAGR avoids negative territory.",
                    "value": float(row["candidate_worst_cagr_pct"]),
                    "threshold": worst_5y_cagr_floor,
                    "operator": ">=",
                }
            )

        for check in checks:
            if check["operator"] == ">=":
                passed = check["value"] >= check["threshold"]
            elif check["operator"] == "<=":
                passed = check["value"] <= check["threshold"]
            else:
                raise ValueError(f"Unsupported operator: {check['operator']}")

            rows.append(
                {
                    "window_name": window_name,
                    "claim": check["claim"],
                    "status": "Passed" if passed else "Failed",
                    "value": round(check["value"], 4),
                    "threshold": check["threshold"],
                    "operator": check["operator"],
                    "interpretation": (
                        "Rolling-window gate passed."
                        if passed
                        else "Rolling-window gate failed."
                    ),
                }
            )

    return pd.DataFrame(rows)


def _create_survivability_conclusion(
    gate_report: pd.DataFrame,
) -> pd.DataFrame:
    if gate_report.empty:
        return pd.DataFrame()

    failed = gate_report[gate_report["status"] == "Failed"]

    spy_12m_failed = failed[
        failed["claim"].str.contains("SPY 12M", case=False, na=False)
    ]
    buy_hold_failed = failed[
        failed["claim"].str.contains("Buy & Hold", case=False, na=False)
    ]
    worst_cagr_failed = failed[
        failed["claim"].str.contains("worst rolling CAGR", case=False, na=False)
    ]

    all_passed = failed.empty

    return pd.DataFrame(
        [
            {
                "claim": "Final candidate rolling-window survivability survived.",
                "status": "Survived" if all_passed else "Failed",
                "evidence_quality": "Rolling 1Y/3Y/5Y window comparison against SPY 12M and SPY Buy & Hold",
                "interpretation": (
                    "All rolling-window survivability gates passed."
                    if all_passed
                    else f"{len(failed)} rolling-window gate(s) failed."
                ),
            },
            {
                "claim": "Final candidate rolling-window edge versus SPY 12M survived.",
                "status": "Survived" if spy_12m_failed.empty else "Failed",
                "evidence_quality": "Rolling-window Calmar and drawdown comparisons",
                "interpretation": (
                    "All SPY 12M rolling-window gates passed."
                    if spy_12m_failed.empty
                    else "At least one SPY 12M rolling-window gate failed."
                ),
            },
            {
                "claim": "Final candidate rolling-window risk advantage versus SPY Buy & Hold survived.",
                "status": "Survived" if buy_hold_failed.empty else "Failed",
                "evidence_quality": "Rolling-window Calmar, drawdown, and raw-CAGR hierarchy checks",
                "interpretation": (
                    "All Buy & Hold rolling-window hierarchy/risk gates passed."
                    if buy_hold_failed.empty
                    else "At least one Buy & Hold rolling-window gate failed."
                ),
            },
            {
                "claim": "Final candidate avoids bad long rolling-return windows.",
                "status": "Survived" if worst_cagr_failed.empty else "Failed",
                "evidence_quality": "Worst rolling 3Y and 5Y CAGR checks",
                "interpretation": (
                    "Worst 3Y/5Y rolling CAGR gates passed."
                    if worst_cagr_failed.empty
                    else "Worst 3Y/5Y rolling CAGR gate failed."
                ),
            },
            {
                "claim": "The final candidate is guaranteed to be liveable.",
                "status": "Failed",
                "evidence_quality": "Rolling-window survivability is a diagnostic, not behavioural proof",
                "interpretation": (
                    "Rolling-window results improve liveability evidence but cannot prove an investor would stick with it."
                ),
            },
            {
                "claim": "The next step should be more strategy optimisation.",
                "status": "Not yet" if all_passed else "No",
                "evidence_quality": "Rolling-window survivability should be documented before new variants",
                "interpretation": (
                    "Document Phase 7F before adding new strategy variants."
                    if all_passed
                    else "Document or investigate failed rolling-window gates before adding new variants."
                ),
            },
        ]
    )


def write_rolling_window_survivability_markdown(
    summary: pd.DataFrame,
    worst_windows: pd.DataFrame,
    gate_report: pd.DataFrame,
    conclusion: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Phase 7F Rolling-Window Survivability Audit

This report tests whether the final candidate's path-quality advantage survives rolling 1Y, 3Y, and 5Y windows.

The audit uses the Phase 7D bootstrap input return series and compares the final candidate against SPY Buy & Hold and SPY 12M Momentum.

## Rolling-Window Summary

{summary.to_markdown(index=False) if not summary.empty else "No rolling-window summary available."}

## Worst Windows

{worst_windows.to_markdown(index=False) if not worst_windows.empty else "No worst-window report available."}

## Gate Report

{gate_report.to_markdown(index=False) if not gate_report.empty else "No gate report available."}

## Conclusion

{conclusion.to_markdown(index=False) if not conclusion.empty else "No conclusion available."}
"""

    output_path.write_text(content, encoding="utf-8")

    return output_path


def create_rolling_window_survivability_audit(
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase7f_config(config)

    if not phase_config.get("enabled", False):
        return {
            "rolling_metrics": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "worst_windows": pd.DataFrame(),
            "gate_report": pd.DataFrame(),
            "conclusion": pd.DataFrame(),
        }

    input_returns = _load_input_returns(
        config=config,
        reports_dir=reports_dir,
    )
    rolling_metrics = _create_rolling_window_metrics(
        input_returns=input_returns,
        config=config,
    )
    summary = _create_window_survivability_summary(rolling_metrics)
    worst_windows = _create_worst_window_report(rolling_metrics)
    gate_report = _create_survivability_gate_report(
        summary=summary,
        config=config,
    )
    conclusion = _create_survivability_conclusion(gate_report)

    return {
        "rolling_metrics": rolling_metrics,
        "summary": summary,
        "worst_windows": worst_windows,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }


def save_rolling_window_survivability_audit(
    config: dict,
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    outputs = create_rolling_window_survivability_audit(
        config=config,
        reports_dir=reports_dir,
    )

    if outputs["conclusion"].empty:
        return outputs

    metrics_path = reports_dir / "phase7f_rolling_window_metrics.csv"
    summary_path = reports_dir / "phase7f_rolling_window_survivability_summary.csv"
    worst_path = reports_dir / "phase7f_rolling_window_worst_windows.csv"
    gate_path = reports_dir / "phase7f_rolling_window_gate_report.csv"
    conclusion_path = reports_dir / "phase7f_rolling_window_conclusion.csv"
    markdown_path = reports_dir / "phase7f_rolling_window_survivability.md"

    outputs["rolling_metrics"].to_csv(metrics_path, index=False)
    outputs["summary"].to_csv(summary_path, index=False)
    outputs["worst_windows"].to_csv(worst_path, index=False)
    outputs["gate_report"].to_csv(gate_path, index=False)
    outputs["conclusion"].to_csv(conclusion_path, index=False)

    write_rolling_window_survivability_markdown(
        summary=outputs["summary"],
        worst_windows=outputs["worst_windows"],
        gate_report=outputs["gate_report"],
        conclusion=outputs["conclusion"],
        output_path=markdown_path,
    )

    print("\nPhase 7F rolling-window survivability summary:")
    print(outputs["summary"].to_string(index=False))

    print("\nPhase 7F rolling-window worst windows:")
    print(outputs["worst_windows"].to_string(index=False))

    print("\nPhase 7F rolling-window gate report:")
    print(outputs["gate_report"].to_string(index=False))

    print("\nPhase 7F rolling-window conclusion:")
    print(outputs["conclusion"].to_string(index=False))

    print(f"\nSaved Phase 7F rolling-window metrics to: {metrics_path}")
    print(f"Saved Phase 7F rolling-window summary to: {summary_path}")
    print(f"Saved Phase 7F rolling-window worst windows to: {worst_path}")
    print(f"Saved Phase 7F rolling-window gate report to: {gate_path}")
    print(f"Saved Phase 7F rolling-window conclusion to: {conclusion_path}")
    print(f"Saved Phase 7F rolling-window markdown to: {markdown_path}")

    return outputs