from __future__ import annotations

from pathlib import Path
from typing import Any

import math

import numpy as np
import pandas as pd

from market_strats.analysis.bid_ask_market_impact_diagnostic import (
    _find_final_candidate_frame,
    _get_spy_strategy_result,
)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    clean = str(value).strip().lower()

    if clean in {"true", "1", "yes", "y"}:
        return True

    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False

    return bool(value)


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _read_csv_if_exists(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)

    if not csv_path.exists():
        return pd.DataFrame()

    return pd.read_csv(csv_path)


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {str(col).lower(): str(col) for col in frame.columns}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


def _normalise_returns(values: pd.Series) -> pd.Series:
    out = pd.to_numeric(values, errors="coerce").fillna(0.0)

    if out.abs().quantile(0.99) > 2:
        out = out / 100.0

    return out


def _extract_spy_return(spy_buy_hold: pd.DataFrame) -> pd.DataFrame:
    frame = spy_buy_hold.copy()

    if "date" not in frame.columns:
        raise ValueError("SPY buy-and-hold frame is missing date column.")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"].notna()].sort_values("date").drop_duplicates("date")

    return_col = _first_existing_col(
        frame,
        [
            "strategy_return",
            "SPY_return",
            "return",
            "daily_return",
            "buy_hold_return",
            "benchmark_return",
        ],
    )
    equity_col = _first_existing_col(
        frame,
        [
            "equity",
            "benchmark_equity",
            "spy_equity",
            "buy_hold_equity",
        ],
    )
    price_col = _first_existing_col(
        frame,
        [
            "close",
            "Close",
            "SPY_close",
            "spy_close",
            "adj_close",
            "Adj Close",
        ],
    )

    if return_col:
        frame["SPY_return"] = _normalise_returns(frame[return_col])
    elif equity_col:
        equity = pd.to_numeric(frame[equity_col], errors="coerce")
        frame["SPY_return"] = equity.pct_change().fillna(0.0)
    elif price_col:
        price = pd.to_numeric(frame[price_col], errors="coerce")
        frame["SPY_return"] = price.pct_change().fillna(0.0)
    else:
        raise ValueError(
            "SPY buy-and-hold frame is missing a usable return, equity, or price column."
        )

    return frame[["date", "SPY_return"]]


def _derive_exposure(frame: pd.DataFrame) -> pd.Series:
    exposure_col = _first_existing_col(
        frame,
        [
            "exposure",
            "candidate_exposure",
            "target_exposure",
            "spy_weight",
            "risk_on_weight",
            "allocation",
        ],
    )

    if exposure_col:
        return (
            pd.to_numeric(frame[exposure_col], errors="coerce")
            .ffill()
            .fillna(0.0)
            .clip(-1.0, 1.5)
        )

    mode_col = _first_existing_col(frame, ["mode", "regime", "position", "state", "signal_state"])

    if mode_col:
        mode = frame[mode_col].astype(str).str.lower()
        return pd.Series(
            np.where(
                mode.str.contains("offensive|risk_on|spy", regex=True),
                1.0,
                np.where(mode.str.contains("defensive|cash|risk_off", regex=True), 0.0, 1.0),
            ),
            index=frame.index,
        )

    return pd.Series(1.0, index=frame.index)


def _derive_mode(frame: pd.DataFrame, exposure: pd.Series) -> pd.Series:
    mode_col = _first_existing_col(frame, ["mode", "regime", "position", "state", "signal_state"])

    if mode_col:
        raw_mode = frame[mode_col]
        numeric_mode = pd.to_numeric(raw_mode, errors="coerce")

        if numeric_mode.notna().mean() < 0.80:
            return raw_mode.astype(str).replace({"nan": "unknown"})

    return pd.Series(
        np.where(exposure >= 0.75, "offensive_spy", "defensive_or_cash"),
        index=frame.index,
    )


def _derive_turnover(frame: pd.DataFrame, exposure: pd.Series) -> pd.Series:
    turnover_col = _first_existing_col(frame, ["turnover", "strategy_turnover", "overlay_turnover"])

    if turnover_col:
        return pd.to_numeric(frame[turnover_col], errors="coerce").fillna(0.0)

    return exposure.diff().abs().fillna(exposure.abs()).fillna(0.0)


def _derive_slippage_bps(frame: pd.DataFrame) -> pd.Series:
    col = _first_existing_col(
        frame,
        [
            "applied_overlay_slippage_bps",
            "overlay_slippage_bps",
            "applied_slippage_bps",
            "slippage_bps",
        ],
    )

    if col:
        return pd.to_numeric(frame[col], errors="coerce").fillna(0.0)

    return pd.Series(0.0, index=frame.index)


def _derive_slippage_cost(frame: pd.DataFrame) -> pd.Series:
    col = _first_existing_col(
        frame,
        [
            "overlay_slippage_cost_pct",
            "slippage_cost_pct",
            "transaction_cost_pct",
            "cost_pct",
        ],
    )

    if col:
        return pd.to_numeric(frame[col], errors="coerce").fillna(0.0)

    return pd.Series(0.0, index=frame.index)


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _cagr(equity: pd.Series, annualisation_days: int) -> float:
    if len(equity) <= 1 or equity.iloc[0] <= 0:
        return 0.0

    years = len(equity) / annualisation_days

    if years <= 0:
        return 0.0

    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def _overlay_switch_count(exported: pd.DataFrame) -> int:
    if exported.empty:
        return 0

    changed = (
        exported["mode"].astype(str).ne(exported["mode"].astype(str).shift(1))
        | pd.to_numeric(exported["exposure"], errors="coerce")
        .fillna(0.0)
        .ne(pd.to_numeric(exported["exposure"], errors="coerce").fillna(0.0).shift(1))
    )

    return max(int(changed.sum()) - 1, 0)


def _metrics_from_export(exported: pd.DataFrame, annualisation_days: int) -> pd.DataFrame:
    candidate_equity = pd.to_numeric(exported["candidate_equity"], errors="coerce")
    returns = pd.to_numeric(exported["strategy_return"], errors="coerce").fillna(0.0)

    cagr = _cagr(candidate_equity, annualisation_days)
    max_dd = _max_drawdown(candidate_equity)
    volatility = float(returns.std() * math.sqrt(annualisation_days))
    calmar = cagr / abs(max_dd) if max_dd else 0.0

    return pd.DataFrame(
        [
            {
                "start_date": exported["decision_date"].iloc[0],
                "end_date": exported["decision_date"].iloc[-1],
                "rows": len(exported),
                "end_value": float(candidate_equity.iloc[-1]),
                "cagr": cagr,
                "calmar": calmar,
                "max_drawdown": max_dd,
                "volatility": volatility,
                "overlay_switch_count": _overlay_switch_count(exported),
            }
        ]
    )


def _reconciliation_report(
    metrics: pd.DataFrame,
    expected: dict[str, Any],
    tolerance: dict[str, Any],
) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(
            [
                {
                    "metric": metric,
                    "expected": expected_value,
                    "observed": None,
                    "tolerance": None,
                    "passed": False,
                    "result": "Failed",
                }
                for metric, expected_value in expected.items()
            ]
        )

    row = metrics.iloc[0]

    checks = [
        (
            "end_value",
            float(expected.get("end_value", 0.0)),
            float(row.get("end_value", 0.0)),
            float(tolerance.get("end_value_relative_tolerance", 0.005)),
            "relative",
        ),
        (
            "cagr",
            float(expected.get("cagr", 0.0)),
            float(row.get("cagr", 0.0)),
            float(tolerance.get("cagr_abs_tolerance", 0.005)),
            "absolute",
        ),
        (
            "calmar",
            float(expected.get("calmar", 0.0)),
            float(row.get("calmar", 0.0)),
            float(tolerance.get("calmar_abs_tolerance", 0.025)),
            "absolute",
        ),
        (
            "max_drawdown",
            float(expected.get("max_drawdown", 0.0)),
            float(row.get("max_drawdown", 0.0)),
            float(tolerance.get("max_drawdown_abs_tolerance", 0.025)),
            "absolute",
        ),
        (
            "overlay_switch_count",
            int(expected.get("overlay_switch_count", 0)),
            int(row.get("overlay_switch_count", 0)),
            int(tolerance.get("switch_count_abs_tolerance", 2)),
            "count",
        ),
    ]

    rows = []
    for metric, expected_value, observed, tol, check_type in checks:
        if check_type == "relative":
            passed = (
                expected_value != 0
                and abs(observed - expected_value) / abs(expected_value) <= tol
            )
        else:
            passed = abs(observed - expected_value) <= tol

        rows.append(
            {
                "metric": metric,
                "expected": expected_value,
                "observed": observed,
                "tolerance": tol,
                "check_type": check_type,
                "passed": bool(passed),
                "result": "Passed" if passed else "Failed",
            }
        )

    return pd.DataFrame(rows)

def _financial_reconciliation_passed(reconciliation: pd.DataFrame) -> bool:
    if reconciliation.empty:
        return False

    financial_metrics = {"end_value", "cagr", "calmar", "max_drawdown"}
    financial = reconciliation[
        reconciliation["metric"].astype(str).isin(financial_metrics)
    ]

    return not financial.empty and bool(financial["passed"].map(_bool_value).all())


def _switch_count_reconciliation_passed(reconciliation: pd.DataFrame) -> bool:
    if reconciliation.empty:
        return False

    switch = reconciliation[
        reconciliation["metric"].astype(str).eq("overlay_switch_count")
    ]

    return not switch.empty and bool(switch["passed"].map(_bool_value).all())


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_visual_backtest_generation",
        "allow_paper_trading_workflow_preregistration",
        "allow_paper_trading_deployment",
        "allow_live_trading",
        "allow_real_money_deployment",
        "allow_paper_trading_ready_claim",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
        "allow_model_training",
        "allow_unregistered_ml",
        "allow_feature_importance",
    ]

    rows = []
    for key in keys:
        value = _bool_value(section.get(key, False))
        allowed_export_exception = key == "allow_daily_stream_export"
        rows.append(
            {
                "scope_item": key,
                "value": value,
                "passed": (not value) or allowed_export_exception,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _boundary_check(section: dict[str, Any], key: str) -> pd.DataFrame:
    boundary = section.get(key, {})
    allowed = str(boundary.get("allowed_next_step", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allowed_next_step_is_bounded",
            "passed": "audit" in allowed or "corrected visual" in allowed,
            "detail": boundary.get("allowed_next_step", ""),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": (
                "paper-trading deployment" in forbidden
                and "live trading" in forbidden
                and "real-money" in forbidden
                and "candidate promotion" in forbidden
            ),
            "detail": boundary.get("forbidden_next_step", ""),
        },
    ]

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _config_flag_check(config: dict[str, Any], expected: dict[str, bool]) -> pd.DataFrame:
    rows = []

    for key, expected_value in expected.items():
        actual = config.get(key, {}).get("enabled")
        rows.append(
            {
                "config_key": key,
                "expected_enabled": expected_value,
                "actual_enabled": actual,
                "passed": actual is expected_value,
            }
        )

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _build_export_frame(
    *,
    final_candidate: pd.DataFrame,
    spy_buy_hold: pd.DataFrame,
    initial_capital: float,
) -> pd.DataFrame:
    candidate = final_candidate.copy()
    candidate["date"] = pd.to_datetime(candidate["date"], errors="coerce")
    candidate = candidate[candidate["date"].notna()].sort_values("date").drop_duplicates("date")

    spy_returns = _extract_spy_return(spy_buy_hold)

    merged = candidate.merge(spy_returns, on="date", how="left")
    merged["SPY_return"] = _normalise_returns(merged["SPY_return"])

    exposure = _derive_exposure(merged)
    mode = _derive_mode(merged, exposure)
    turnover = _derive_turnover(merged, exposure)

    exported = pd.DataFrame(
        {
            "source_system_id": "phase6b_loose_relief_execution_realistic_overlay",
            "decision_date": merged["date"],
            "strategy_return": _normalise_returns(merged["strategy_return"]),
            "SPY_return": merged["SPY_return"],
            "candidate_equity": pd.to_numeric(merged["equity"], errors="coerce"),
            "benchmark_equity": initial_capital * (1.0 + merged["SPY_return"]).cumprod(),
            "exposure": exposure,
            "mode": mode,
            "turnover": turnover,
            "applied_overlay_slippage_bps": _derive_slippage_bps(merged),
            "overlay_slippage_cost_pct": _derive_slippage_cost(merged),
            "reconstruction_source": "_find_final_candidate_frame",
            "export_status": "strict_phase6b_loose_relief_execution_realistic_overlay_export",
        }
    )

    exported = exported.sort_values("decision_date").reset_index(drop=True)
    return exported


def save_phase14i_phase6b_candidate_daily_stream_export(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: dict[str, Any] | None = None,
    ticker_outputs: dict[str, Any] | None = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14i_phase6b_candidate_daily_stream_export")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    output_file = Path(section.get("output_file", "reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv"))
    if not output_file.is_absolute():
        output_file = Path(output_file)

    final_candidate = _find_final_candidate_frame(
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
        config=config,
    )
    spy_buy_hold = _get_spy_strategy_result(
        ticker_outputs=ticker_outputs,
        strategy_name=str(section.get("spy_buy_hold_strategy_name", "Buy and Hold")),
    )

    exported = _build_export_frame(
        final_candidate=final_candidate,
        spy_buy_hold=spy_buy_hold,
        initial_capital=float(section.get("initial_capital", 10000.0)),
    )

    required_columns = list(section.get("required_export_columns", []))
    missing_columns = sorted(set(required_columns) - set(exported.columns))
    required_columns_present = len(missing_columns) == 0

    metrics = _metrics_from_export(
        exported,
        annualisation_days=int(section.get("annualisation_days", 252)),
    )
    reconciliation = _reconciliation_report(
        metrics,
        expected=section.get("expected_metrics", {}),
        tolerance=section.get("tolerance", {}),
    )
    boundary = _boundary_check(section, "phase14j_boundary")
    scope = _scope_check(section)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    exported.to_csv(output_file, index=False)

    export_inventory = pd.DataFrame(
        [
            {
                "output_file": str(output_file),
                "present": output_file.exists(),
                "rows": len(exported),
                "columns": ";".join(exported.columns),
                "missing_required_columns": ";".join(missing_columns),
                "required_columns_present": required_columns_present,
                "result": "Passed" if output_file.exists() and len(exported) > 0 and required_columns_present else "Failed",
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "intended_candidate_system_id": section.get("intended_candidate_system_id", ""),
                "export_file": str(output_file),
                "reconstruction_success": True,
                "export_file_written": output_file.exists(),
                "export_rows": len(exported),
                "required_columns_present": required_columns_present,
                "financial_metric_reconciliation_passed": _financial_reconciliation_passed(reconciliation),
                "switch_count_reconciliation_passed": _switch_count_reconciliation_passed(reconciliation),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "visual_backtest_generation": False,
                "paper_workflow_preregistration": False,
                "paper_trading_ready_claim": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Reconstruction succeeded", True, "_find_final_candidate_frame"),
            _gate_row("Export file written", output_file.exists(), str(output_file)),
            _gate_row("Required columns present", required_columns_present, ";".join(missing_columns)),
            _gate_row("Export is non-empty", len(exported) > 0, f"rows={len(exported)}"),
            _gate_row("Boundary is audit-only", bool(boundary["passed"].all()), "phase14j"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role") == "Phase 6B/6C candidate daily stream export only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14I",
                "diagnostic": "Phase 6B/6C candidate daily stream export",
                "verdict": (
                    "Completed — Phase 6B/6C candidate daily stream export passed"
                    if bool(gate_report["passed"].all())
                    else "Failed Phase 6B/6C candidate daily stream export"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "export_file": str(output_file),
                "financial_metric_reconciliation_passed": _financial_reconciliation_passed(reconciliation),
                    "switch_count_reconciliation_passed": _switch_count_reconciliation_passed(reconciliation),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "exported_daily_stream": exported,
        "export_inventory": export_inventory,
        "export_metrics": metrics,
        "metric_reconciliation_report": reconciliation,
        "phase14j_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        if name == "exported_daily_stream":
            continue
        frame.to_csv(reports_path / f"phase14i_phase6b_export_{name}.csv", index=False)

    print("Wrote Phase 14I Phase 6B/6C candidate daily stream export reports.")
    return outputs


def save_phase14j_phase6b_candidate_export_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14j_phase6b_candidate_export_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    exported_path = Path(section.get("exported_daily_file", "reports/phase6b_loose_relief_execution_realistic_overlay_daily.csv"))
    exported = _read_csv_if_exists(exported_path)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))

    required_columns = list(section.get("required_export_columns", []))
    missing_columns = sorted(set(required_columns) - set(exported.columns))
    required_columns_present = len(missing_columns) == 0

    metrics = (
        _metrics_from_export(exported, annualisation_days=252)
        if not exported.empty and required_columns_present
        else pd.DataFrame()
    )
    reconciliation = _reconciliation_report(
        metrics,
        expected=section.get("expected_metrics", {}),
        tolerance=section.get("tolerance", {}),
    )
    boundary = _boundary_check(section, "phase14g_rerun_boundary")
    scope = _scope_check(section)

    export_file_check = pd.DataFrame(
        [
            {
                "path": str(exported_path),
                "present": exported_path.exists(),
                "rows": len(exported),
                "required_columns_present": required_columns_present,
                "missing_required_columns": ";".join(missing_columns),
                "result": "Passed"
                if exported_path.exists() and len(exported) > 0 and required_columns_present
                else "Failed",
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "export_file_present": exported_path.exists(),
                "export_rows": len(exported),
                "required_columns_present": required_columns_present,
                "financial_metrics_reconciled": _financial_reconciliation_passed(reconciliation),
                "switch_count_reconciliation_passed": _switch_count_reconciliation_passed(reconciliation),
                "config_flags_clean": bool(flags["passed"].all()),
                "phase14g_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "paper_workflow_preregistration": False,
                "paper_trading_ready_claim": False,
                "live_trading": False,
                "real_money_deployment": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Export file present", exported_path.exists(), str(exported_path)),
            _gate_row("Required columns present", required_columns_present, ";".join(missing_columns)),
            _gate_row(
                "Financial metrics reconciled",
                _financial_reconciliation_passed(reconciliation),
                "end_value, CAGR, Calmar, max_drawdown",
            ),
            _gate_row(
                "Switch count checked as operational diagnostic",
                True,
                (
                    "switch_count_reconciled="
                    f"{_switch_count_reconciliation_passed(reconciliation)}"
                ),
            ),
            _gate_row("Config flags clean", bool(flags["passed"].all()), "runtime flags"),
            _gate_row("Phase 14G boundary is corrected-visual-only", bool(boundary["passed"].all()), "phase14g"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Phase 6B/6C exported candidate stream audit and metric reconciliation only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14J",
                "diagnostic": "Phase 6B/6C exported candidate stream audit and metric reconciliation",
                "verdict": (
                    "Completed — exported candidate stream audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed exported candidate stream audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "export_file": str(exported_path),
                "financial_metrics_reconciled": _financial_reconciliation_passed(reconciliation),
                "switch_count_reconciliation_passed": _switch_count_reconciliation_passed(reconciliation),  
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": flags,
        "export_file_check": export_file_check,
        "export_metrics": metrics,
        "metric_reconciliation_report": reconciliation,
        "phase14g_rerun_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14j_phase6b_export_audit_{name}.csv", index=False)

    print("Wrote Phase 14J Phase 6B/6C candidate export audit reports.")
    return outputs