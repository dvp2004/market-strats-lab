from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import math

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    clean = str(value).strip().lower()
    if clean in {"true", "1", "yes", "y"}:
        return True
    if clean in {"false", "0", "no", "n", "", "nan", "none"}:
        return False
    return bool(value)


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


def _section(config: dict[str, Any], key: str) -> dict[str, Any]:
    return config.get(key, {}) or {}


def _source_report_check(paths: dict[str, str]) -> pd.DataFrame:
    rows = []
    for report_key, path in paths.items():
        report_path = Path(str(path))
        frame = _read_csv_if_exists(report_path)
        rows.append(
            {
                "report_key": report_key,
                "path": str(report_path),
                "present": report_path.exists(),
                "rows": len(frame),
                "result": "Passed" if report_path.exists() else "Failed",
            }
        )
    return pd.DataFrame(rows)


def _phase_result_check(conclusion_path: str, gate_path: str, phase_name: str) -> pd.DataFrame:
    conclusion = _read_csv_if_exists(conclusion_path)
    gate = _read_csv_if_exists(gate_path)

    conclusion_passed = (
        not conclusion.empty
        and _bool_value(conclusion.iloc[0].get("all_gates_passed", False))
        and "passed" in str(conclusion.iloc[0].get("verdict", "")).lower()
    )
    gate_passed = (
        not gate.empty
        and "passed" in gate.columns
        and bool(gate["passed"].map(_bool_value).all())
    )

    out = pd.DataFrame(
        [
            {
                "check": f"{phase_name} conclusion passed",
                "passed": conclusion_passed,
                "detail": "conclusion",
            },
            {
                "check": f"{phase_name} gate report passed",
                "passed": gate_passed,
                "detail": "gate_report",
            },
        ]
    )
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _scope_check(section: dict[str, Any]) -> pd.DataFrame:
    keys = [
        "allow_live_trading",
        "allow_real_money_deployment",
        "allow_model_training",
        "allow_unregistered_ml",
        "allow_feature_importance",
        "allow_candidate_promotion",
        "allow_final_candidate_change",
        "allow_paper_trading_ready_claim",
    ]
    rows = []
    for key in keys:
        value = _bool_value(section.get(key, False))
        rows.append({"scope_item": key, "value": value, "passed": not value})
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _normalise_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for col in frame.columns:
        frame[col] = frame[col].apply(
            lambda value: "; ".join(map(str, value)) if isinstance(value, list) else value
        )
    return frame


def _policy_frame(section: dict[str, Any], key: str) -> pd.DataFrame:
    rows = []
    for policy_key, value in section.get(key, {}).items():
        rows.append(
            {
                "policy_key": policy_key,
                "policy_value": "; ".join(map(str, value)) if isinstance(value, list) else value,
            }
        )
    return pd.DataFrame(rows)


def _flatten_policy(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "policy_key" not in frame.columns or "policy_value" not in frame.columns:
        return {}
    return {str(row["policy_key"]): row["policy_value"] for _, row in frame.iterrows()}


def _split_policy_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return [str(item) for item in _as_list(value)]


def _boundary_check(section: dict[str, Any], keys: list[str]) -> pd.DataFrame:
    rows = []
    for key in keys:
        boundary = section.get(key, {})
        allowed = str(
            boundary.get("allowed_next_step", boundary.get("allowed_future_step", ""))
        ).lower()
        forbidden = str(
            boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", ""))
        ).lower()

        rows.append(
            {
                "boundary": key,
                "allowed": boundary.get("allowed_next_step", boundary.get("allowed_future_step", "")),
                "forbidden": boundary.get("forbidden_next_step", boundary.get("forbidden_future_step", "")),
                "passed": bool(
                    ("readiness" in allowed or "execution" in allowed or "audit" in allowed or "interpretation" in allowed)
                    and "live trading" in forbidden
                    and "real-money" in forbidden
                    and "feature importance" in forbidden
                    and "candidate promotion" in forbidden
                ),
            }
        )
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def save_phase14a_non_ml_visual_backtest_preregistration(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14a_non_ml_visual_backtest_preregistration")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    source_reports = section.get("source_reports", {})
    source_check = _source_report_check(source_reports)
    phase13aw_check = _phase_result_check(
        source_reports["phase13aw_conclusion"],
        source_reports["phase13aw_gate_report"],
        "Phase 13AW",
    )
    route = _read_csv_if_exists(source_reports["phase13aw_route_selection_report"])

    selected_non_ml = (
        not route.empty
        and str(route.iloc[0].get("selected_route_id", ""))
        == section.get("candidate_route_id")
        and str(route.iloc[0].get("candidate_system_id", ""))
        == section.get("candidate_system_id")
    )

    artefact_registry = _normalise_rows(section.get("artefact_registry", []))
    visual_source_policy = _policy_frame(section, "visual_source_policy")
    signal_policy = _policy_frame(section, "signal_mapping_preview_policy")
    boundary = _boundary_check(section, ["phase14b_boundary", "phase14c_boundary"])
    scope = _scope_check(section)

    summary = pd.DataFrame(
        [
            {
                "spec_role": section.get("spec_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "candidate_system_id": section.get("candidate_system_id", ""),
                "candidate_route_id": section.get("candidate_route_id", ""),
                "benchmark_id": section.get("benchmark_id", ""),
                "phase13aw_passed": bool(phase13aw_check["passed"].all()),
                "selected_route_is_non_ml_overlay": selected_non_ml,
                "artefact_registry_rows": len(artefact_registry),
                "visual_source_policy_rows": len(visual_source_policy),
                "signal_mapping_preview_policy_rows": len(signal_policy),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "model_training": False,
                "feature_importance": False,
                "candidate_promotion": False,
                "paper_trading_ready_claim": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 13AW passed", bool(summary.iloc[0]["phase13aw_passed"]), "phase13aw"),
            _gate_row("Selected route is non-ML overlay", selected_non_ml, str(section.get("candidate_route_id", ""))),
            _gate_row("Artefact registry exists", len(artefact_registry) >= 8, f"rows={len(artefact_registry)}"),
            _gate_row("Signal mapping preview policy exists", len(signal_policy) > 0, f"rows={len(signal_policy)}"),
            _gate_row("Boundaries passed", bool(boundary["passed"].all()), "phase14b/phase14c"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Spec role is correct",
                section.get("spec_role")
                == "Non-ML paper-trading candidate visual backtest and signal-mapping pre-registration only",
                section.get("spec_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14A",
                "diagnostic": "Non-ML visual backtest and signal-mapping pre-registration",
                "verdict": (
                    "Completed — non-ML visual backtest pre-registration passed"
                    if bool(gate_report["passed"].all())
                    else "Failed non-ML visual backtest pre-registration"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase13aw_result_check": phase13aw_check,
        "artefact_registry": artefact_registry,
        "visual_source_policy": visual_source_policy,
        "signal_mapping_preview_policy": signal_policy,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14a_visual_prereg_{name}.csv", index=False)

    print("Wrote Phase 14A visual backtest pre-registration reports.")
    return outputs


def _iter_dataframes(obj: Any, prefix: str = "") -> Iterable[tuple[str, pd.DataFrame]]:
    if isinstance(obj, pd.DataFrame):
        yield prefix or "dataframe", obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from _iter_dataframes(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(obj, (list, tuple)):
        for idx, value in enumerate(obj):
            yield from _iter_dataframes(value, f"{prefix}[{idx}]")


def _first_existing_col(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {str(col): col for col in frame.columns}
    for candidate in candidates:
        if candidate in cols:
            return str(cols[candidate])
    lower_map = {str(col).lower(): col for col in frame.columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return str(lower_map[candidate.lower()])
    return None


def _normalise_return_series(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if values.abs().quantile(0.99) > 2:
        values = values / 100.0
    return values


def _candidate_source_score(frame: pd.DataFrame, policy: dict[str, Any]) -> tuple[int, dict[str, str | None]]:
    date_col = _first_existing_col(frame, _split_policy_list(policy.get("date_columns", "")))
    candidate_return_col = _first_existing_col(frame, _split_policy_list(policy.get("candidate_return_columns", "")))
    benchmark_return_col = _first_existing_col(frame, _split_policy_list(policy.get("benchmark_return_columns", "")))
    candidate_equity_col = _first_existing_col(frame, _split_policy_list(policy.get("candidate_equity_columns", "")))
    benchmark_equity_col = _first_existing_col(frame, _split_policy_list(policy.get("benchmark_equity_columns", "")))
    price_col = _first_existing_col(frame, _split_policy_list(policy.get("price_columns", "")))
    exposure_col = _first_existing_col(frame, _split_policy_list(policy.get("exposure_columns", "")))
    mode_col = _first_existing_col(frame, _split_policy_list(policy.get("mode_columns", "")))

    has_candidate = bool(candidate_return_col or candidate_equity_col)
    has_benchmark = bool(benchmark_return_col or benchmark_equity_col or price_col)

    score = 0
    score += 5 if date_col else 0
    score += 5 if has_candidate else 0
    score += 5 if has_benchmark else 0
    score += 2 if exposure_col else 0
    score += 2 if mode_col else 0
    score += min(len(frame) // 500, 5)

    return score, {
        "date_col": date_col,
        "candidate_return_col": candidate_return_col,
        "benchmark_return_col": benchmark_return_col,
        "candidate_equity_col": candidate_equity_col,
        "benchmark_equity_col": benchmark_equity_col,
        "price_col": price_col,
        "exposure_col": exposure_col,
        "mode_col": mode_col,
    }


def _resolve_visual_source(
    *,
    reports_dir: str | Path,
    policy: dict[str, Any],
    relative_momentum_outputs: Any = None,
    ticker_outputs: Any = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates: list[tuple[str, pd.DataFrame, int, dict[str, str | None]]] = []

    for name, frame in _iter_dataframes(relative_momentum_outputs, "relative_momentum_outputs"):
        score, cols = _candidate_source_score(frame, policy)
        if score >= 15:
            candidates.append((name, frame.copy(), score, cols))

    for name, frame in _iter_dataframes(ticker_outputs, "ticker_outputs"):
        score, cols = _candidate_source_score(frame, policy)
        if score >= 15:
            candidates.append((name, frame.copy(), score, cols))

    reports_path = Path(reports_dir)
    for pattern in ["*phase6b*loose*relief*.csv", "*loose*relief*.csv", "*final*candidate*.csv", "*relative*momentum*.csv"]:
        for path in reports_path.glob(pattern):
            frame = _read_csv_if_exists(path)
            score, cols = _candidate_source_score(frame, policy)
            if score >= 15:
                candidates.append((str(path), frame, score, cols))

    if not candidates:
        return pd.DataFrame(), pd.DataFrame(
            [
                {
                    "source_name": "",
                    "resolved": False,
                    "reason": "No candidate source with date, candidate return/equity, and benchmark return/equity/price was found.",
                }
            ]
        )

    candidates = sorted(candidates, key=lambda item: item[2], reverse=True)
    source_name, frame, score, cols = candidates[0]
    normalised = _normalise_visual_source(frame, cols)

    source_report = pd.DataFrame(
        [
            {
                "source_name": source_name,
                "resolved": not normalised.empty,
                "score": score,
                "rows": len(normalised),
                **cols,
            }
        ]
    )
    return normalised, source_report


def _normalise_visual_source(frame: pd.DataFrame, cols: dict[str, str | None]) -> pd.DataFrame:
    date_col = cols["date_col"]
    if date_col is None:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["decision_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    out = out[out["decision_date"].notna()].copy()

    frame = frame.loc[out.index].copy()

    if cols["candidate_return_col"]:
        out["candidate_return"] = _normalise_return_series(frame[cols["candidate_return_col"]])
    elif cols["candidate_equity_col"]:
        equity = pd.to_numeric(frame[cols["candidate_equity_col"]], errors="coerce")
        out["candidate_return"] = equity.pct_change().fillna(0.0)
    else:
        return pd.DataFrame()

    if cols["benchmark_return_col"]:
        out["benchmark_return"] = _normalise_return_series(frame[cols["benchmark_return_col"]])
    elif cols["benchmark_equity_col"]:
        equity = pd.to_numeric(frame[cols["benchmark_equity_col"]], errors="coerce")
        out["benchmark_return"] = equity.pct_change().fillna(0.0)
    elif cols["price_col"]:
        price = pd.to_numeric(frame[cols["price_col"]], errors="coerce")
        out["benchmark_return"] = price.pct_change().fillna(0.0)
    else:
        return pd.DataFrame()

    if cols["exposure_col"]:
        exposure = pd.to_numeric(frame[cols["exposure_col"]], errors="coerce")
        out["exposure"] = exposure.ffill().fillna(0.0).clip(-1.0, 1.5)
    else:
        out["exposure"] = 1.0

    if cols["mode_col"]:
        out["mode"] = frame[cols["mode_col"]].astype(str).replace({"nan": "unknown"})
    else:
        out["mode"] = np.where(out["exposure"] > 0.5, "risk_on", "risk_off")

    out = out.sort_values("decision_date").drop_duplicates("decision_date").reset_index(drop=True)
    out["candidate_return"] = out["candidate_return"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    out["benchmark_return"] = out["benchmark_return"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
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


def save_phase14b_non_ml_visual_backtest_readiness_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: Any = None,
    ticker_outputs: Any = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14b_non_ml_visual_backtest_readiness_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    reports = section.get("phase14a_reports", {})
    inventory = _source_report_check(reports)
    phase14a_check = _phase_result_check(reports["conclusion"], reports["gate_report"], "Phase 14A")

    visual_source_policy = _flatten_policy(_read_csv_if_exists(reports["visual_source_policy"]))
    artefacts = _read_csv_if_exists(reports["artefact_registry"])
    source, source_resolution = _resolve_visual_source(
        reports_dir=reports_dir,
        policy=visual_source_policy,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    thresholds = section.get("readiness_thresholds", {})
    min_rows = int(thresholds.get("min_rows", 1000))
    source_resolved = not source.empty
    candidate_and_benchmark_returns = (
        source_resolved
        and {"candidate_return", "benchmark_return"}.issubset(source.columns)
        and source["candidate_return"].notna().any()
        and source["benchmark_return"].notna().any()
    )
    source_min_rows = len(source) >= min_rows
    artefact_complete = not artefacts.empty and artefacts["required"].map(_bool_value).all()
    boundary = _boundary_check(section, ["phase14c_boundary"])
    scope = _scope_check(section)

    readiness = pd.DataFrame(
        [
            {
                "candidate_source_resolved": source_resolved,
                "source_rows": len(source),
                "min_rows": min_rows,
                "candidate_and_benchmark_returns": candidate_and_benchmark_returns,
                "has_exposure": source_resolved and "exposure" in source.columns,
                "has_mode": source_resolved and "mode" in source.columns,
                "first_decision_date": source["decision_date"].min() if source_resolved else "",
                "last_decision_date": source["decision_date"].max() if source_resolved else "",
            }
        ]
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14a_passed": bool(phase14a_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "phase14a_reports_present": bool(inventory["present"].all()) if not inventory.empty else False,
                "candidate_source_resolved": source_resolved,
                "candidate_source_min_rows": source_min_rows,
                "candidate_and_benchmark_returns": candidate_and_benchmark_returns,
                "artefact_registry_complete": artefact_complete,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "model_training": False,
                "feature_importance": False,
                "candidate_promotion": False,
                "paper_trading_ready_claim": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14A passed", bool(summary.iloc[0]["phase14a_passed"]), "phase14a"),
            _gate_row("Config flags clean", bool(summary.iloc[0]["config_flags_clean"]), "runtime flags"),
            _gate_row("Phase 14A reports present", bool(summary.iloc[0]["phase14a_reports_present"]), "inventory"),
            _gate_row("Candidate source resolved", source_resolved, "visual source"),
            _gate_row("Candidate source has enough rows", source_min_rows, f"rows={len(source)}; min_rows={min_rows}"),
            _gate_row("Candidate and benchmark returns available", candidate_and_benchmark_returns, "returns"),
            _gate_row("Artefact registry complete", artefact_complete, f"rows={len(artefacts)}"),
            _gate_row("Phase 14C boundary is execution-only", bool(boundary["passed"].all()), "phase14c"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Non-ML visual backtest readiness audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14B",
                "diagnostic": "Non-ML visual backtest readiness audit",
                "verdict": (
                    "Completed — non-ML visual backtest readiness audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed non-ML visual backtest readiness audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "config_flag_check": flags,
        "report_inventory_check": inventory,
        "phase14a_result_check": phase14a_check,
        "candidate_source_resolution_report": source_resolution,
        "candidate_source_preview": source.head(50),
        "readiness_check": readiness,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14b_visual_readiness_{name}.csv", index=False)

    print("Wrote Phase 14B visual backtest readiness reports.")
    return outputs


def _equity_curve(source: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    out = source.copy()
    out["candidate_equity"] = initial_capital * (1.0 + out["candidate_return"]).cumprod()
    out["benchmark_equity"] = initial_capital * (1.0 + out["benchmark_return"]).cumprod()
    out["candidate_pnl"] = out["candidate_equity"] - initial_capital
    out["benchmark_pnl"] = out["benchmark_equity"] - initial_capital
    out["relative_equity"] = out["candidate_equity"] - out["benchmark_equity"]
    return out[
        [
            "decision_date",
            "candidate_return",
            "benchmark_return",
            "candidate_equity",
            "benchmark_equity",
            "candidate_pnl",
            "benchmark_pnl",
            "relative_equity",
            "exposure",
            "mode",
        ]
    ]


def _drawdown_curve(equity: pd.DataFrame) -> pd.DataFrame:
    out = equity[["decision_date", "candidate_equity", "benchmark_equity"]].copy()
    out["candidate_peak"] = out["candidate_equity"].cummax()
    out["benchmark_peak"] = out["benchmark_equity"].cummax()
    out["candidate_drawdown"] = out["candidate_equity"] / out["candidate_peak"] - 1.0
    out["benchmark_drawdown"] = out["benchmark_equity"] / out["benchmark_peak"] - 1.0
    return out


def _rolling_relative(equity: pd.DataFrame, window: int) -> pd.DataFrame:
    out = equity[["decision_date", "candidate_equity", "benchmark_equity"]].copy()
    out["candidate_rolling_return"] = out["candidate_equity"].pct_change(window)
    out["benchmark_rolling_return"] = out["benchmark_equity"].pct_change(window)
    out["rolling_relative_return"] = out["candidate_rolling_return"] - out["benchmark_rolling_return"]
    return out.fillna(0.0)


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _cagr(equity: pd.Series, annualisation_days: int) -> float:
    if len(equity) <= 1:
        return 0.0
    years = len(equity) / annualisation_days
    if years <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def _benchmark_comparison(equity: pd.DataFrame, annualisation_days: int) -> pd.DataFrame:
    rows = []
    for label, equity_col, return_col in [
        ("candidate", "candidate_equity", "candidate_return"),
        ("benchmark_spy_buy_hold", "benchmark_equity", "benchmark_return"),
    ]:
        returns = pd.to_numeric(equity[return_col], errors="coerce").fillna(0.0)
        cagr = _cagr(equity[equity_col], annualisation_days)
        max_dd = _max_drawdown(equity[equity_col])
        vol = float(returns.std() * math.sqrt(annualisation_days))
        sharpe = float((returns.mean() / returns.std()) * math.sqrt(annualisation_days)) if returns.std() else 0.0
        rows.append(
            {
                "series": label,
                "start_value": float(equity[equity_col].iloc[0]),
                "end_value": float(equity[equity_col].iloc[-1]),
                "total_return": float(equity[equity_col].iloc[-1] / equity[equity_col].iloc[0] - 1.0),
                "cagr": cagr,
                "annualised_volatility": vol,
                "sharpe_zero_rf": sharpe,
                "max_drawdown": max_dd,
                "calmar": cagr / abs(max_dd) if max_dd else 0.0,
            }
        )
    diff = rows[0]["end_value"] - rows[1]["end_value"]
    rows.append(
        {
            "series": "candidate_minus_benchmark",
            "start_value": 0.0,
            "end_value": diff,
            "total_return": rows[0]["total_return"] - rows[1]["total_return"],
            "cagr": rows[0]["cagr"] - rows[1]["cagr"],
            "annualised_volatility": rows[0]["annualised_volatility"] - rows[1]["annualised_volatility"],
            "sharpe_zero_rf": rows[0]["sharpe_zero_rf"] - rows[1]["sharpe_zero_rf"],
            "max_drawdown": rows[0]["max_drawdown"] - rows[1]["max_drawdown"],
            "calmar": rows[0]["calmar"] - rows[1]["calmar"],
        }
    )
    return pd.DataFrame(rows)


def _switch_log(equity: pd.DataFrame) -> pd.DataFrame:
    frame = equity[["decision_date", "exposure", "mode", "candidate_equity", "benchmark_equity"]].copy()
    previous_exposure = frame["exposure"].shift(1)
    previous_mode = frame["mode"].shift(1)
    switches = frame[
        (frame["exposure"].ne(previous_exposure)) | (frame["mode"].ne(previous_mode))
    ].copy()
    switches = switches.iloc[1:].copy() if len(switches) > 1 else switches.iloc[0:0].copy()
    switches["from_exposure"] = previous_exposure.loc[switches.index].to_numpy()
    switches["to_exposure"] = switches["exposure"]
    switches["from_mode"] = previous_mode.loc[switches.index].to_numpy()
    switches["to_mode"] = switches["mode"]
    switches["switch_event_id"] = range(1, len(switches) + 1)
    switches["paper_trading_action"] = np.where(
        switches["to_exposure"] > switches["from_exposure"],
        "risk_on_preview",
        np.where(switches["to_exposure"] < switches["from_exposure"], "risk_off_preview", "mode_change_preview"),
    )
    return switches[
        [
            "switch_event_id",
            "decision_date",
            "from_mode",
            "to_mode",
            "from_exposure",
            "to_exposure",
            "paper_trading_action",
            "candidate_equity",
            "benchmark_equity",
        ]
    ]


def _trade_log(equity: pd.DataFrame) -> pd.DataFrame:
    frame = equity.copy()
    change = frame["mode"].ne(frame["mode"].shift(1)) | frame["exposure"].ne(frame["exposure"].shift(1))
    frame["segment_id"] = change.cumsum()

    rows = []
    for segment_id, group in frame.groupby("segment_id"):
        rows.append(
            {
                "trade_segment_id": int(segment_id),
                "entry_date": group["decision_date"].iloc[0],
                "exit_date": group["decision_date"].iloc[-1],
                "calendar_rows": len(group),
                "mode": group["mode"].iloc[0],
                "exposure": float(group["exposure"].iloc[0]),
                "entry_candidate_equity": float(group["candidate_equity"].iloc[0]),
                "exit_candidate_equity": float(group["candidate_equity"].iloc[-1]),
                "candidate_pnl": float(group["candidate_equity"].iloc[-1] - group["candidate_equity"].iloc[0]),
                "benchmark_pnl": float(group["benchmark_equity"].iloc[-1] - group["benchmark_equity"].iloc[0]),
                "candidate_segment_return": float(group["candidate_equity"].iloc[-1] / group["candidate_equity"].iloc[0] - 1.0) if group["candidate_equity"].iloc[0] else 0.0,
                "benchmark_segment_return": float(group["benchmark_equity"].iloc[-1] / group["benchmark_equity"].iloc[0] - 1.0) if group["benchmark_equity"].iloc[0] else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _money_made_lost(equity: pd.DataFrame, trade_log: pd.DataFrame) -> pd.DataFrame:
    candidate_end = float(equity["candidate_equity"].iloc[-1])
    benchmark_end = float(equity["benchmark_equity"].iloc[-1])
    candidate_start = float(equity["candidate_equity"].iloc[0])
    benchmark_start = float(equity["benchmark_equity"].iloc[0])

    return pd.DataFrame(
        [
            {
                "metric": "candidate_total_pnl",
                "value": candidate_end - candidate_start,
            },
            {
                "metric": "benchmark_total_pnl",
                "value": benchmark_end - benchmark_start,
            },
            {
                "metric": "candidate_minus_benchmark_pnl",
                "value": candidate_end - benchmark_end,
            },
            {
                "metric": "winning_trade_segments",
                "value": int((trade_log["candidate_pnl"] > 0).sum()) if not trade_log.empty else 0,
            },
            {
                "metric": "losing_trade_segments",
                "value": int((trade_log["candidate_pnl"] < 0).sum()) if not trade_log.empty else 0,
            },
            {
                "metric": "best_trade_segment_pnl",
                "value": float(trade_log["candidate_pnl"].max()) if not trade_log.empty else 0.0,
            },
            {
                "metric": "worst_trade_segment_pnl",
                "value": float(trade_log["candidate_pnl"].min()) if not trade_log.empty else 0.0,
            },
        ]
    )


def _signal_template_preview(equity: pd.DataFrame, rows: int) -> pd.DataFrame:
    preview = equity.tail(rows).copy()
    preview["paper_trading_status"] = "preview_only_not_deployment"
    preview["signal_source"] = "non_ml_overlay_mode_and_exposure"
    preview["action_template"] = np.where(
        preview["exposure"] >= 0.75,
        "risk_on_preview",
        np.where(preview["exposure"] <= 0.25, "cash_or_defensive_preview", "partial_risk_preview"),
    )
    preview["live_trading_allowed"] = False
    preview["real_money_allowed"] = False
    preview["candidate_promotion_made"] = False
    preview["paper_readiness_claim_made"] = False
    return preview[
        [
            "decision_date",
            "mode",
            "exposure",
            "action_template",
            "candidate_equity",
            "benchmark_equity",
            "paper_trading_status",
            "signal_source",
            "live_trading_allowed",
            "real_money_allowed",
            "candidate_promotion_made",
            "paper_readiness_claim_made",
        ]
    ]


def _save_line_chart(frame: pd.DataFrame, x_col: str, y_cols: list[str], path: str | Path, title: str, width: float, height: float, dpi: int) -> None:
    fig, ax = plt.subplots(figsize=(width, height))
    for y_col in y_cols:
        ax.plot(pd.to_datetime(frame[x_col]), frame[y_col], label=y_col)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def _write_visual_outputs(
    *,
    source: pd.DataFrame,
    reports_path: Path,
    section: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    policy = section.get("report_policy", {})
    initial_capital = float(policy.get("initial_capital", 10000.0))
    rolling_window = int(policy.get("rolling_window_days", 63))
    annualisation_days = int(policy.get("annualisation_days", 252))
    preview_rows = int(policy.get("preview_signal_rows", 25))
    chart_dpi = int(policy.get("chart_dpi", 140))
    chart_width = float(policy.get("chart_width", 10))
    chart_height = float(policy.get("chart_height", 5))

    equity = _equity_curve(source, initial_capital)
    drawdown = _drawdown_curve(equity)
    exposure = equity[["decision_date", "exposure", "mode"]].copy()
    switch_log = _switch_log(equity)
    trade_log = _trade_log(equity)
    money = _money_made_lost(equity, trade_log)
    benchmark = _benchmark_comparison(equity, annualisation_days)
    rolling = _rolling_relative(equity, rolling_window)
    signal_preview = _signal_template_preview(equity, preview_rows)

    outputs = {
        "equity_curve": equity,
        "drawdown_curve": drawdown,
        "exposure_timeline": exposure,
        "trade_log": trade_log,
        "switch_event_log": switch_log,
        "money_made_lost_table": money,
        "benchmark_comparison": benchmark,
        "rolling_relative_performance": rolling,
        "signal_template_preview": signal_preview,
    }

    equity.to_csv(reports_path / "phase14c_visual_backtest_equity_curve.csv", index=False)
    drawdown.to_csv(reports_path / "phase14c_visual_backtest_drawdown_curve.csv", index=False)
    exposure.to_csv(reports_path / "phase14c_visual_backtest_exposure_timeline.csv", index=False)
    trade_log.to_csv(reports_path / "phase14c_visual_backtest_trade_log.csv", index=False)
    switch_log.to_csv(reports_path / "phase14c_visual_backtest_switch_event_log.csv", index=False)
    money.to_csv(reports_path / "phase14c_visual_backtest_money_made_lost_table.csv", index=False)
    benchmark.to_csv(reports_path / "phase14c_visual_backtest_benchmark_comparison.csv", index=False)
    rolling.to_csv(reports_path / "phase14c_visual_backtest_rolling_relative_performance.csv", index=False)
    signal_preview.to_csv(reports_path / "phase14c_visual_backtest_signal_template_preview.csv", index=False)

    _save_line_chart(
        equity,
        "decision_date",
        ["candidate_equity", "benchmark_equity"],
        reports_path / "phase14c_visual_backtest_equity_curve.png",
        "Candidate Equity vs SPY Buy & Hold",
        chart_width,
        chart_height,
        chart_dpi,
    )
    _save_line_chart(
        drawdown,
        "decision_date",
        ["candidate_drawdown", "benchmark_drawdown"],
        reports_path / "phase14c_visual_backtest_drawdown_curve.png",
        "Candidate Drawdown vs SPY Buy & Hold",
        chart_width,
        chart_height,
        chart_dpi,
    )
    _save_line_chart(
        exposure,
        "decision_date",
        ["exposure"],
        reports_path / "phase14c_visual_backtest_exposure_timeline.png",
        "Exposure Timeline",
        chart_width,
        chart_height,
        chart_dpi,
    )
    _save_line_chart(
        rolling,
        "decision_date",
        ["rolling_relative_return"],
        reports_path / "phase14c_visual_backtest_rolling_relative_performance.png",
        f"{rolling_window}D Rolling Relative Performance",
        chart_width,
        chart_height,
        chart_dpi,
    )

    return outputs


def save_phase14c_non_ml_visual_backtest_report_execution(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: Any = None,
    ticker_outputs: Any = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14c_non_ml_visual_backtest_report_execution")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = section.get("source_reports", {})
    phase14b_check = _phase_result_check(reports["phase14b_conclusion"], reports["phase14b_gate_report"], "Phase 14B")
    visual_source_policy = _flatten_policy(_read_csv_if_exists(reports["visual_source_policy"]))
    source, source_resolution = _resolve_visual_source(
        reports_dir=reports_dir,
        policy=visual_source_policy,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    visual_outputs = _write_visual_outputs(source=source, reports_path=reports_path, section=section) if not source.empty else {}
    boundary = _boundary_check(section, ["phase14d_boundary"])
    scope = _scope_check(section)

    chart_paths = [
        reports_path / "phase14c_visual_backtest_equity_curve.png",
        reports_path / "phase14c_visual_backtest_drawdown_curve.png",
        reports_path / "phase14c_visual_backtest_exposure_timeline.png",
        reports_path / "phase14c_visual_backtest_rolling_relative_performance.png",
    ]
    chart_files_present = all(path.exists() and path.stat().st_size > 0 for path in chart_paths)

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14b_passed": bool(phase14b_check["passed"].all()),
                "source_resolved": not source.empty,
                "source_rows": len(source),
                "equity_curve_rows": len(visual_outputs.get("equity_curve", pd.DataFrame())),
                "drawdown_curve_rows": len(visual_outputs.get("drawdown_curve", pd.DataFrame())),
                "trade_log_rows": len(visual_outputs.get("trade_log", pd.DataFrame())),
                "switch_event_log_rows": len(visual_outputs.get("switch_event_log", pd.DataFrame())),
                "signal_preview_rows": len(visual_outputs.get("signal_template_preview", pd.DataFrame())),
                "chart_files_present": chart_files_present,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "model_training": False,
                "feature_importance": False,
                "candidate_promotion": False,
                "paper_trading_ready_claim": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14B passed", bool(summary.iloc[0]["phase14b_passed"]), "phase14b"),
            _gate_row("Equity curve exists", "equity_curve" in visual_outputs and len(visual_outputs["equity_curve"]) > 0, "equity"),
            _gate_row("Drawdown curve exists", "drawdown_curve" in visual_outputs and len(visual_outputs["drawdown_curve"]) > 0, "drawdown"),
            _gate_row("Exposure timeline exists", "exposure_timeline" in visual_outputs and len(visual_outputs["exposure_timeline"]) > 0, "exposure"),
            _gate_row("Trade log exists", "trade_log" in visual_outputs and len(visual_outputs["trade_log"]) > 0, "trade log"),
            _gate_row("Switch event log exists", "switch_event_log" in visual_outputs, "switch events"),
            _gate_row("Money made/lost table exists", "money_made_lost_table" in visual_outputs and len(visual_outputs["money_made_lost_table"]) > 0, "money"),
            _gate_row("Benchmark comparison exists", "benchmark_comparison" in visual_outputs and len(visual_outputs["benchmark_comparison"]) > 0, "benchmark"),
            _gate_row("Rolling relative performance exists", "rolling_relative_performance" in visual_outputs and len(visual_outputs["rolling_relative_performance"]) > 0, "rolling"),
            _gate_row("Signal template preview exists", "signal_template_preview" in visual_outputs and len(visual_outputs["signal_template_preview"]) > 0, "preview"),
            _gate_row("Chart files exist", chart_files_present, "png charts"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role") == "Non-ML visual backtest report execution only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14C",
                "diagnostic": "Non-ML visual backtest report execution",
                "verdict": (
                    "Completed — non-ML visual backtest report execution passed"
                    if bool(gate_report["passed"].all())
                    else "Failed non-ML visual backtest report execution"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "phase14b_result_check": phase14b_check,
        "candidate_source_resolution_report": source_resolution,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
        **visual_outputs,
    }

    for name, frame in {
        "candidate_source_resolution_report": source_resolution,
        "phase14b_result_check": phase14b_check,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }.items():
        frame.to_csv(reports_path / f"phase14c_visual_backtest_{name}.csv", index=False)

    print("Wrote Phase 14C visual backtest reports.")
    return outputs


def _report_inventory(paths: dict[str, str]) -> pd.DataFrame:
    rows = []
    for key, path in paths.items():
        p = Path(path)
        frame = _read_csv_if_exists(p)
        rows.append(
            {
                "report_key": key,
                "path": str(p),
                "present": p.exists(),
                "rows": len(frame),
                "passed": p.exists() and len(frame) > 0,
            }
        )
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _chart_inventory(paths: list[str]) -> pd.DataFrame:
    rows = []
    for path in paths:
        p = Path(path)
        rows.append(
            {
                "path": str(p),
                "present": p.exists(),
                "size_bytes": p.stat().st_size if p.exists() else 0,
                "passed": p.exists() and p.stat().st_size > 0,
            }
        )
    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _forbidden_claim_check(paths: dict[str, str], claims: list[str]) -> pd.DataFrame:
    rows = []

    for claim in claims:
        claim_clean = claim.lower()
        matched = []

        for report_key, path in paths.items():
            p = Path(path)
            if not p.exists():
                continue

            try:
                frame = pd.read_csv(p, dtype=str)
            except Exception:
                text = p.read_text(encoding="utf-8", errors="ignore").lower()
                if claim_clean in text:
                    matched.append(f"{report_key}:{p}")
                continue

            # Important: scan cell values only, not column names.
            # Column names may deliberately contain boundary/audit schema labels.
            for col in frame.columns:
                values = frame[col].dropna().astype(str).str.lower()

                if values.str.contains(claim_clean, regex=False).any():
                    matched.append(f"{report_key}:{p}")
                    break

        rows.append(
            {
                "forbidden_claim": claim,
                "matched_paths": "; ".join(matched),
                "passed": len(matched) == 0,
                "result": "Passed" if len(matched) == 0 else "Failed",
            }
        )

    return pd.DataFrame(rows)


def save_phase14d_non_ml_visual_backtest_result_audit(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14d_non_ml_visual_backtest_result_audit")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = section.get("phase14c_reports", {})
    inventory = _report_inventory(reports)
    phase14c_check = _phase_result_check(reports["conclusion"], reports["gate_report"], "Phase 14C")
    charts = _chart_inventory(section.get("chart_files", []))
    forbidden = _forbidden_claim_check(reports, section.get("forbidden_claims", []))
    boundary = _boundary_check(section, ["phase14e_boundary"])
    scope = _scope_check(section)

    signal_preview = _read_csv_if_exists(reports["signal_template_preview"])
    live_permission_col = (
        "live_trading_allowed"
        if "live_trading_allowed" in signal_preview.columns
        else "live_trading_permission"
    )
    real_money_permission_col = (
        "real_money_allowed"
        if "real_money_allowed" in signal_preview.columns
        else "real_money_permission"
    )

    preview_only = (
        not signal_preview.empty
        and "paper_trading_status" in signal_preview.columns
        and signal_preview["paper_trading_status"].astype(str).eq("preview_only_not_deployment").all()
        and not signal_preview.get(live_permission_col, pd.Series([False])).map(_bool_value).any()
        and not signal_preview.get(real_money_permission_col, pd.Series([False])).map(_bool_value).any()
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14c_passed": bool(phase14c_check["passed"].all()),
                "all_required_reports_present": bool(inventory["present"].all()) if not inventory.empty else False,
                "report_rows_non_empty": bool(inventory["passed"].all()) if not inventory.empty else False,
                "chart_files_present": bool(charts["passed"].all()) if not charts.empty else False,
                "signal_template_preview_is_preview_only": preview_only,
                "forbidden_claims_absent": bool(forbidden["passed"].all()) if not forbidden.empty else True,
                "phase14e_boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "model_training": False,
                "feature_importance": False,
                "candidate_promotion": False,
                "paper_trading_ready_claim": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14C passed", bool(summary.iloc[0]["phase14c_passed"]), "phase14c"),
            _gate_row("All required reports present", bool(summary.iloc[0]["all_required_reports_present"]), "reports"),
            _gate_row("Chart files present", bool(summary.iloc[0]["chart_files_present"]), "charts"),
            _gate_row("Report rows non-empty", bool(summary.iloc[0]["report_rows_non_empty"]), "row counts"),
            _gate_row("Signal preview is preview-only", preview_only, "signal preview"),
            _gate_row("Forbidden claims absent", bool(summary.iloc[0]["forbidden_claims_absent"]), "claims"),
            _gate_row("Phase 14E boundary is interpretation-only", bool(boundary["passed"].all()), "phase14e"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role") == "Non-ML visual backtest result audit only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14D",
                "diagnostic": "Non-ML visual backtest result audit",
                "verdict": (
                    "Completed — non-ML visual backtest result audit passed"
                    if bool(gate_report["passed"].all())
                    else "Failed non-ML visual backtest result audit"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "report_inventory_check": inventory,
        "phase14c_result_check": phase14c_check,
        "chart_inventory_check": charts,
        "forbidden_claim_check": forbidden,
        "signal_preview_boundary_check": pd.DataFrame(
            [
                {
                    "check": "signal_template_preview_is_preview_only",
                    "passed": preview_only,
                    "result": "Passed" if preview_only else "Failed",
                }
            ]
        ),
        "phase14e_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14d_visual_audit_{name}.csv", index=False)

    print("Wrote Phase 14D visual backtest audit reports.")
    return outputs