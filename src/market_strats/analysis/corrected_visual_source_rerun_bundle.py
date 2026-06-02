from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import math

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd


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


def _phase_result_check(
    conclusion_path: str,
    gate_path: str,
    phase_name: str,
) -> pd.DataFrame:
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
        "allow_paper_trading_deployment",
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
        rows.append({"scope_item": key, "value": value, "passed": not value})

    out = pd.DataFrame(rows)
    out["result"] = out["passed"].map({True: "Passed", False: "Failed"})
    return out


def _boundary_check(section: dict[str, Any], key: str) -> pd.DataFrame:
    boundary = section.get(key, {})
    allowed = str(
        boundary.get("allowed_next_step", boundary.get("allowed_next_step_if_passed", ""))
    ).lower()
    allowed_failed = str(boundary.get("allowed_next_step_if_failed", "")).lower()
    forbidden = str(boundary.get("forbidden_next_step", "")).lower()

    rows = [
        {
            "check": f"{key}_allows_audit_or_conditional_next_step",
            "passed": (
                "audit" in allowed
                or "pre-registration" in allowed
                or "preregistration" in allowed
                or "correction" in allowed_failed
                or "route pause" in allowed_failed
            ),
            "detail": boundary.get(
                "allowed_next_step",
                boundary.get("allowed_next_step_if_passed", ""),
            ),
        },
        {
            "check": f"{key}_blocks_forbidden_actions",
            "passed": bool(
                "live trading" in forbidden
                and "real-money" in forbidden
                and "paper-trading deployment" in forbidden
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


def _split_policy_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    return [str(item) for item in _as_list(value)]


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


def _source_columns(
    frame: pd.DataFrame,
    policy: dict[str, Any],
) -> dict[str, str | None]:
    return {
        "date_col": _first_existing_col(frame, _as_list(policy.get("date_columns", []))),
        "candidate_return_col": _first_existing_col(
            frame,
            _as_list(policy.get("candidate_return_columns", [])),
        ),
        "benchmark_return_col": _first_existing_col(
            frame,
            _as_list(policy.get("benchmark_return_columns", [])),
        ),
        "candidate_equity_col": _first_existing_col(
            frame,
            _as_list(policy.get("candidate_equity_columns", [])),
        ),
        "benchmark_equity_col": _first_existing_col(
            frame,
            _as_list(policy.get("benchmark_equity_columns", [])),
        ),
        "price_col": _first_existing_col(frame, _as_list(policy.get("price_columns", []))),
        "exposure_col": _first_existing_col(
            frame,
            _as_list(policy.get("exposure_columns", [])),
        ),
        "mode_col": _first_existing_col(frame, _as_list(policy.get("mode_columns", []))),
    }


def _candidate_has_required_columns(cols: dict[str, str | None]) -> bool:
    return bool(
        cols["date_col"]
        and (cols["candidate_return_col"] or cols["candidate_equity_col"])
        and (
            cols["benchmark_return_col"]
            or cols["benchmark_equity_col"]
            or cols["price_col"]
        )
    )


def _source_name_passes_strict_policy(
    source_name: str,
    policy: dict[str, Any],
) -> tuple[bool, bool, bool]:
    source_lower = source_name.lower()

    required = [
        str(fragment).lower()
        for fragment in _as_list(policy.get("required_source_name_fragments"))
    ]
    suspicious = [
        str(fragment).lower()
        for fragment in _as_list(policy.get("suspicious_raw_allocator_fragments"))
    ]

    required_present = all(fragment in source_lower for fragment in required)
    suspicious_present = any(fragment in source_lower for fragment in suspicious)

    rejected_suspicious = bool(suspicious_present and not required_present)
    passed = bool(required_present and not rejected_suspicious)

    return passed, required_present, rejected_suspicious


def _normalise_visual_source(
    frame: pd.DataFrame,
    cols: dict[str, str | None],
) -> pd.DataFrame:
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

    out = (
        out.sort_values("decision_date")
        .drop_duplicates("decision_date")
        .reset_index(drop=True)
    )
    out["candidate_return"] = out["candidate_return"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    out["benchmark_return"] = out["benchmark_return"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return out


def _strict_source_resolution(
    *,
    reports_dir: str | Path,
    policy: dict[str, Any],
    visual_policy: dict[str, Any],
    relative_momentum_outputs: Any = None,
    ticker_outputs: Any = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    candidates: list[tuple[str, pd.DataFrame]] = []

    for name, frame in _iter_dataframes(relative_momentum_outputs, "relative_momentum_outputs"):
        candidates.append((name, frame.copy()))

    for name, frame in _iter_dataframes(ticker_outputs, "ticker_outputs"):
        candidates.append((name, frame.copy()))

    reports_path = Path(reports_dir)
    for pattern in [
        "*phase6b*loose*relief*execution*realistic*.csv",
        "*phase6b*loose*relief*.csv",
        "*loose*relief*execution*realistic*.csv",
    ]:
        for path in reports_path.glob(pattern):
            candidates.append((str(path), _read_csv_if_exists(path)))

    for source_name, frame in candidates:
        if frame.empty:
            continue

        strict_name_passed, required_present, rejected_suspicious = (
            _source_name_passes_strict_policy(source_name, policy)
        )
        cols = _source_columns(frame, visual_policy)
        required_cols_present = _candidate_has_required_columns(cols)

        row = {
            "source_name": source_name,
            "rows": len(frame),
            "strict_name_passed": strict_name_passed,
            "required_fragments_present": required_present,
            "rejected_suspicious_allocator": rejected_suspicious,
            "required_columns_present": required_cols_present,
            **cols,
        }

        if strict_name_passed and required_cols_present:
            accepted.append(row)
        else:
            row["rejection_reason"] = _rejection_reason(
                strict_name_passed,
                required_present,
                rejected_suspicious,
                required_cols_present,
            )
            rejected.append(row)

    if not accepted:
        source_resolution = pd.DataFrame(
            [
                {
                    "corrected_source_resolved": False,
                    "source_name": "",
                    "rows": 0,
                    "corrected_source_identity_passed": False,
                    "reason": "No strict source matched required Phase 6B loose relief execution realistic fragments and required return/date columns.",
                }
            ]
        )
        return pd.DataFrame(), source_resolution, pd.DataFrame(rejected)

    selected = sorted(accepted, key=lambda row: row["rows"], reverse=True)[0]
    source_frame = next(frame for name, frame in candidates if name == selected["source_name"])
    normalised = _normalise_visual_source(source_frame, selected)

    source_resolution = pd.DataFrame(
        [
            {
                "corrected_source_resolved": not normalised.empty,
                "source_name": selected["source_name"],
                "rows": len(normalised),
                "corrected_source_identity_passed": not normalised.empty,
                "reason": "Strict source matched required candidate fragments and required return/date columns.",
                **{key: selected.get(key) for key in selected if key.endswith("_col")},
            }
        ]
    )

    return normalised, source_resolution, pd.DataFrame(rejected)


def _rejection_reason(
    strict_name_passed: bool,
    required_present: bool,
    rejected_suspicious: bool,
    required_cols_present: bool,
) -> str:
    reasons = []

    if not required_present:
        reasons.append("required source fragments missing")

    if rejected_suspicious:
        reasons.append("suspicious raw allocator source")

    if not strict_name_passed:
        reasons.append("strict source-name policy failed")

    if not required_cols_present:
        reasons.append("required date/candidate/benchmark columns missing")

    return "; ".join(reasons)


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
    out["rolling_relative_return"] = (
        out["candidate_rolling_return"] - out["benchmark_rolling_return"]
    )
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
        ("corrected_candidate", "candidate_equity", "candidate_return"),
        ("benchmark_spy_buy_hold", "benchmark_equity", "benchmark_return"),
    ]:
        returns = pd.to_numeric(equity[return_col], errors="coerce").fillna(0.0)
        cagr = _cagr(equity[equity_col], annualisation_days)
        max_dd = _max_drawdown(equity[equity_col])
        vol = float(returns.std() * math.sqrt(annualisation_days))
        sharpe = (
            float((returns.mean() / returns.std()) * math.sqrt(annualisation_days))
            if returns.std()
            else 0.0
        )

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

    rows.append(
        {
            "series": "corrected_candidate_minus_benchmark",
            "start_value": 0.0,
            "end_value": rows[0]["end_value"] - rows[1]["end_value"],
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
    frame = equity[
        ["decision_date", "exposure", "mode", "candidate_equity", "benchmark_equity"]
    ].copy()
    previous_exposure = frame["exposure"].shift(1)
    previous_mode = frame["mode"].shift(1)
    switches = frame[
        (frame["exposure"].ne(previous_exposure))
        | (frame["mode"].ne(previous_mode))
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
        np.where(
            switches["to_exposure"] < switches["from_exposure"],
            "risk_off_preview",
            "mode_change_preview",
        ),
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
    change = frame["mode"].ne(frame["mode"].shift(1)) | frame["exposure"].ne(
        frame["exposure"].shift(1)
    )
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
                "candidate_pnl": float(
                    group["candidate_equity"].iloc[-1]
                    - group["candidate_equity"].iloc[0]
                ),
                "benchmark_pnl": float(
                    group["benchmark_equity"].iloc[-1]
                    - group["benchmark_equity"].iloc[0]
                ),
                "candidate_segment_return": float(
                    group["candidate_equity"].iloc[-1]
                    / group["candidate_equity"].iloc[0]
                    - 1.0
                )
                if group["candidate_equity"].iloc[0]
                else 0.0,
                "benchmark_segment_return": float(
                    group["benchmark_equity"].iloc[-1]
                    / group["benchmark_equity"].iloc[0]
                    - 1.0
                )
                if group["benchmark_equity"].iloc[0]
                else 0.0,
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
            {"metric": "corrected_candidate_total_pnl", "value": candidate_end - candidate_start},
            {"metric": "benchmark_total_pnl", "value": benchmark_end - benchmark_start},
            {"metric": "corrected_candidate_minus_benchmark_pnl", "value": candidate_end - benchmark_end},
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
    preview["signal_source"] = "corrected_non_ml_overlay_mode_and_exposure"
    preview["action_template"] = np.where(
        preview["exposure"] >= 0.75,
        "risk_on_preview",
        np.where(
            preview["exposure"] <= 0.25,
            "cash_or_defensive_preview",
            "partial_risk_preview",
        ),
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


def _current_signal_state(signal_preview: pd.DataFrame) -> pd.DataFrame:
    if signal_preview.empty:
        return pd.DataFrame(
            [
                {
                    "signal_determined": False,
                    "warning": "Corrected signal preview missing.",
                    "paper_trading_allowed": False,
                }
            ]
        )

    preview = signal_preview.copy()
    preview["decision_date"] = pd.to_datetime(preview["decision_date"], errors="coerce")
    latest = preview.sort_values("decision_date").tail(1)

    if latest.empty:
        return pd.DataFrame(
            [
                {
                    "signal_determined": False,
                    "warning": "Corrected latest signal row could not be determined.",
                    "paper_trading_allowed": False,
                }
            ]
        )

    row = latest.iloc[0]

    return pd.DataFrame(
        [
            {
                "signal_determined": True,
                "latest_decision_date": row.get("decision_date", ""),
                "current_mode": row.get("mode", ""),
                "current_exposure": row.get("exposure", ""),
                "current_candidate_action": row.get("action_template", ""),
                "preview_only": str(row.get("paper_trading_status", "")).lower()
                == "preview_only_not_deployment",
                "paper_trading_allowed": False,
                "live_trading_allowed": _bool_value(row.get("live_trading_allowed", False)),
                "real_money_allowed": _bool_value(row.get("real_money_allowed", False)),
                "data_timestamp_source": "phase14g_corrected_visual_signal_template_preview.csv",
                "warning": "",
            }
        ]
    )


def _save_line_chart(
    frame: pd.DataFrame,
    x_col: str,
    y_cols: list[str],
    path: str | Path,
    title: str,
    width: float,
    height: float,
    dpi: int,
) -> None:
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


def _write_corrected_visual_outputs(
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
    switch_event_log = _switch_log(equity)
    trade_log = _trade_log(equity)
    money = _money_made_lost(equity, trade_log)
    benchmark = _benchmark_comparison(equity, annualisation_days)
    rolling = _rolling_relative(equity, rolling_window)
    signal_preview = _signal_template_preview(equity, preview_rows)
    current_signal = _current_signal_state(signal_preview)

    equity.to_csv(reports_path / "phase14g_corrected_visual_equity_curve.csv", index=False)
    drawdown.to_csv(reports_path / "phase14g_corrected_visual_drawdown_curve.csv", index=False)
    exposure.to_csv(reports_path / "phase14g_corrected_visual_exposure_timeline.csv", index=False)
    trade_log.to_csv(reports_path / "phase14g_corrected_visual_trade_log.csv", index=False)
    switch_event_log.to_csv(reports_path / "phase14g_corrected_visual_switch_event_log.csv", index=False)
    money.to_csv(reports_path / "phase14g_corrected_visual_money_made_lost_table.csv", index=False)
    benchmark.to_csv(reports_path / "phase14g_corrected_visual_benchmark_comparison.csv", index=False)
    rolling.to_csv(reports_path / "phase14g_corrected_visual_rolling_relative_performance.csv", index=False)
    signal_preview.to_csv(reports_path / "phase14g_corrected_visual_signal_template_preview.csv", index=False)
    current_signal.to_csv(reports_path / "phase14g_corrected_visual_current_signal_state_report.csv", index=False)

    _save_line_chart(
        equity,
        "decision_date",
        ["candidate_equity", "benchmark_equity"],
        reports_path / "phase14g_corrected_visual_equity_curve.png",
        "Corrected Candidate Equity vs SPY Buy & Hold",
        chart_width,
        chart_height,
        chart_dpi,
    )
    _save_line_chart(
        drawdown,
        "decision_date",
        ["candidate_drawdown", "benchmark_drawdown"],
        reports_path / "phase14g_corrected_visual_drawdown_curve.png",
        "Corrected Candidate Drawdown vs SPY Buy & Hold",
        chart_width,
        chart_height,
        chart_dpi,
    )
    _save_line_chart(
        exposure,
        "decision_date",
        ["exposure"],
        reports_path / "phase14g_corrected_visual_exposure_timeline.png",
        "Corrected Exposure Timeline",
        chart_width,
        chart_height,
        chart_dpi,
    )
    _save_line_chart(
        rolling,
        "decision_date",
        ["rolling_relative_return"],
        reports_path / "phase14g_corrected_visual_rolling_relative_performance.png",
        f"{rolling_window}D Corrected Rolling Relative Performance",
        chart_width,
        chart_height,
        chart_dpi,
    )

    return {
        "equity_curve": equity,
        "drawdown_curve": drawdown,
        "exposure_timeline": exposure,
        "trade_log": trade_log,
        "switch_event_log": switch_event_log,
        "money_made_lost_table": money,
        "benchmark_comparison": benchmark,
        "rolling_relative_performance": rolling,
        "signal_template_preview": signal_preview,
        "current_signal_state_report": current_signal,
    }


def _candidate_metric_row(benchmark: pd.DataFrame) -> pd.Series | None:
    if benchmark.empty or "series" not in benchmark.columns:
        return None

    candidate = benchmark[
        benchmark["series"].astype(str).str.lower().eq("corrected_candidate")
    ]

    if candidate.empty:
        return None

    return candidate.iloc[0]


def _metric_reconciliation_report(
    *,
    benchmark: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    reconciliation = section.get("canonical_metric_reconciliation", {})
    tolerance = reconciliation.get("tolerance", {})
    cagr_tol = float(tolerance.get("cagr_abs_tolerance", 0.005))
    calmar_tol = float(tolerance.get("calmar_abs_tolerance", 0.025))
    dd_tol = float(tolerance.get("max_drawdown_abs_tolerance", 0.025))
    final_value_tol = float(tolerance.get("final_value_relative_tolerance", 0.05))

    candidate = _candidate_metric_row(benchmark)
    rows = []

    for system in reconciliation.get("canonical_systems", []):
        compare_to_candidate = _bool_value(system.get("compare_to_corrected_candidate", False))
        expected_cagr = float(system.get("expected_cagr", 0.0))
        expected_calmar = float(system.get("expected_calmar", 0.0))
        expected_max_dd = float(system.get("expected_max_drawdown", 0.0))
        expected_final_value = system.get("expected_final_value", None)

        observed_cagr = None
        observed_calmar = None
        observed_max_dd = None
        observed_final_value = None

        if compare_to_candidate and candidate is not None:
            observed_cagr = float(candidate.get("cagr", 0.0))
            observed_calmar = float(candidate.get("calmar", 0.0))
            observed_max_dd = float(candidate.get("max_drawdown", 0.0))
            observed_final_value = float(candidate.get("end_value", 0.0))

        cagr_pass = True
        calmar_pass = True
        dd_pass = True
        final_value_pass = True
        candidate_missing = bool(compare_to_candidate and candidate is None)

        if candidate_missing:
            cagr_pass = False
            calmar_pass = False
            dd_pass = False
            final_value_pass = False

        elif compare_to_candidate and candidate is not None:
            observed_cagr = float(candidate.get("cagr", 0.0))
            observed_calmar = float(candidate.get("calmar", 0.0))
            observed_max_dd = float(candidate.get("max_drawdown", 0.0))
            observed_final_value = float(candidate.get("end_value", 0.0))

            cagr_pass = abs(observed_cagr - expected_cagr) <= cagr_tol
            calmar_pass = abs(observed_calmar - expected_calmar) <= calmar_tol
            dd_pass = abs(observed_max_dd - expected_max_dd) <= dd_tol

            if expected_final_value is not None:
                expected_final_value = float(expected_final_value)
                final_value_pass = (
                    abs(observed_final_value - expected_final_value) / expected_final_value
                    <= final_value_tol
                )

        rows.append(
            {
                "system_id": system.get("system_id", ""),
                "label": system.get("label", ""),
                "required_in_side_by_side": _bool_value(system.get("required_in_side_by_side", False)),
                "compare_to_corrected_candidate": compare_to_candidate,
                "expected_cagr": expected_cagr,
                "observed_cagr": observed_cagr,
                "cagr_reconciled": cagr_pass,
                "candidate_missing": candidate_missing,
                "expected_calmar": expected_calmar,
                "observed_calmar": observed_calmar,
                "calmar_reconciled": calmar_pass,
                "expected_max_drawdown": expected_max_dd,
                "observed_max_drawdown": observed_max_dd,
                "max_drawdown_reconciled": dd_pass,
                "expected_final_value": expected_final_value,
                "observed_final_value": observed_final_value,
                "final_value_reconciled": final_value_pass,
                "metric_reconciliation_passed": bool(
                    cagr_pass and calmar_pass and dd_pass and final_value_pass
                ),
            }
        )

    return pd.DataFrame(rows)


def _side_by_side_comparison(
    *,
    metric_reconciliation: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, row in metric_reconciliation.iterrows():
        rows.append(
            {
                "system_id": row["system_id"],
                "label": row["label"],
                "source": "canonical_checkpoint",
                "cagr": row["expected_cagr"],
                "calmar": row["expected_calmar"],
                "max_drawdown": row["expected_max_drawdown"],
                "final_value": row.get("expected_final_value", None),
                "required_for_phase14h": row["required_in_side_by_side"],
            }
        )

    candidate = _candidate_metric_row(benchmark)
    if candidate is not None:
        rows.append(
            {
                "system_id": "phase14g_corrected_visual_candidate",
                "label": "Phase 14G corrected visual candidate",
                "source": "phase14g_corrected_visual_backtest",
                "cagr": float(candidate.get("cagr", 0.0)),
                "calmar": float(candidate.get("calmar", 0.0)),
                "max_drawdown": float(candidate.get("max_drawdown", 0.0)),
                "final_value": float(candidate.get("end_value", 0.0)),
                "required_for_phase14h": True,
            }
        )
    else:
        rows.append(
            {
                "system_id": "phase14g_corrected_visual_candidate",
                "label": "Phase 14G corrected visual candidate",
                "source": "missing_corrected_source",
                "cagr": None,
                "calmar": None,
                "max_drawdown": None,
                "final_value": None,
                "required_for_phase14h": True,
            }
        )

    return pd.DataFrame(rows)


def save_phase14g_candidate_source_correction_visual_rerun(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    relative_momentum_outputs: Any = None,
    ticker_outputs: Any = None,
) -> dict[str, pd.DataFrame]:
    section = _section(config, "phase14g_candidate_source_correction_visual_rerun")
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    reports = section.get("source_reports", {})
    source_check = _source_report_check(reports)
    phase14f_check = _phase_result_check(
        reports["phase14f_conclusion"],
        reports["phase14f_gate_report"],
        "Phase 14F",
    )
    correction_spec = _read_csv_if_exists(reports["phase14f_correction_spec_report"])
    correction_required = (
        _bool_value(correction_spec.iloc[0].get("correction_required", False))
        if not correction_spec.empty
        else False
    )

    source, source_resolution, rejected_sources = _strict_source_resolution(
        reports_dir=reports_dir,
        policy=section.get("strict_source_resolution_policy", {}),
        visual_policy=section.get("visual_source_policy", {}),
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    visual_outputs = (
        _write_corrected_visual_outputs(
            source=source,
            reports_path=reports_path,
            section=section,
        )
        if not source.empty
        else {}
    )

    benchmark = visual_outputs.get("benchmark_comparison", pd.DataFrame())
    metric_reconciliation = _metric_reconciliation_report(
        benchmark=benchmark,
        section=section,
    )
    side_by_side = _side_by_side_comparison(
        metric_reconciliation=metric_reconciliation,
        benchmark=benchmark,
    )
    current_signal = visual_outputs.get("current_signal_state_report", pd.DataFrame())
    boundary = _boundary_check(section, "phase14h_boundary")
    scope = _scope_check(section)

    metric_reconciliation.to_csv(
        reports_path / "phase14g_corrected_visual_metric_reconciliation_report.csv",
        index=False,
    )
    side_by_side.to_csv(
        reports_path / "phase14g_corrected_visual_side_by_side_comparison_report.csv",
        index=False,
    )
    source_resolution.to_csv(
        reports_path / "phase14g_corrected_visual_strict_source_resolution_report.csv",
        index=False,
    )
    rejected_sources.to_csv(
        reports_path / "phase14g_corrected_visual_rejected_source_report.csv",
        index=False,
    )

    corrected_source_passed = (
        not source_resolution.empty
        and _bool_value(source_resolution.iloc[0].get("corrected_source_identity_passed", False))
    )
    required_non_empty_visual_outputs = [
        "equity_curve",
        "drawdown_curve",
        "exposure_timeline",
        "trade_log",
        "money_made_lost_table",
        "benchmark_comparison",
        "rolling_relative_performance",
        "signal_template_preview",
        "current_signal_state_report",
    ]

    optional_empty_visual_outputs = [
        "switch_event_log",
    ]

    required_outputs_present_and_non_empty = bool(
        visual_outputs
        and all(
            key in visual_outputs and len(visual_outputs[key]) > 0
            for key in required_non_empty_visual_outputs
        )
    )

    optional_outputs_present = bool(
        visual_outputs
        and all(key in visual_outputs for key in optional_empty_visual_outputs)
    )

    corrected_visual_reports_generated = bool(
        required_outputs_present_and_non_empty and optional_outputs_present
    )
    visual_output_inventory = pd.DataFrame(
        [
            {
                "report_key": key,
                "rows": len(frame),
                "required_non_empty": key in required_non_empty_visual_outputs,
                "optional_empty_allowed": key in optional_empty_visual_outputs,
                "passed": (
                    (key in required_non_empty_visual_outputs and len(frame) > 0)
                    or key in optional_empty_visual_outputs
                ),
            }
            for key, frame in visual_outputs.items()
        ]
    )
    visual_output_inventory["result"] = visual_output_inventory["passed"].map(
        {True: "Passed", False: "Failed"}
    )
    current_signal_generated = not current_signal.empty

    summary = pd.DataFrame(
        [
            {
                "execution_role": section.get("execution_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14f_passed": bool(phase14f_check["passed"].all()),
                "source_reports_present": bool(source_check["present"].all()) if not source_check.empty else False,
                "correction_required_from_phase14f": correction_required,
                "corrected_source_identity_passed": corrected_source_passed,
                "corrected_visual_reports_generated": corrected_visual_reports_generated,
                "current_signal_state_report_generated": current_signal_generated,
                "metric_reconciliation_passed": bool(metric_reconciliation["metric_reconciliation_passed"].all())
                if not metric_reconciliation.empty
                else False,
                "side_by_side_rows": len(side_by_side),
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "paper_workflow_preregistration": False,
                "live_trading": False,
                "real_money_deployment": False,
                "paper_trading_ready_claim": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
                "visual_output_inventory": visual_output_inventory,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14F passed", bool(summary.iloc[0]["phase14f_passed"]), "phase14f"),
            _gate_row("Correction required from Phase 14F", correction_required, "correction_required"),
            _gate_row("Strict source resolution report exists", len(source_resolution) == 1, "source resolution"),
            _gate_row("Corrected source identity passed", corrected_source_passed, "strict source"),
            _gate_row(
                "Corrected visual reports generated",
                corrected_visual_reports_generated,
                "visual outputs",
            ),
            _gate_row("Current signal state report exists", current_signal_generated, "current signal"),
            _gate_row("Side-by-side comparison report exists", len(side_by_side) >= 5, f"rows={len(side_by_side)}"),
            _gate_row("Phase 14H boundary is audit-only", bool(boundary["passed"].all()), "phase14h"),
            _gate_row(
                "No paper workflow/live trading/promotion",
                bool(
                    not summary.iloc[0]["paper_workflow_preregistration"]
                    and not summary.iloc[0]["live_trading"]
                    and not summary.iloc[0]["candidate_promotion"]
                ),
                "scope",
            ),
            _gate_row(
                "Execution role is correct",
                section.get("execution_role")
                == "Candidate source correction implementation and corrected visual backtest re-run only",
                section.get("execution_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14G",
                "diagnostic": "Candidate source correction implementation and corrected visual backtest re-run",
                "verdict": (
                    "Completed — corrected visual backtest re-run passed"
                    if bool(gate_report["passed"].all())
                    else "Failed corrected visual backtest re-run"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "corrected_source_identity_passed": corrected_source_passed,
                "metric_reconciliation_passed": bool(summary.iloc[0]["metric_reconciliation_passed"]),
                "paper_trading_ready": False,
                "strategy_promotion": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )

    outputs = {
        "source_report_check": source_check,
        "phase14f_result_check": phase14f_check,
        "correction_spec_input_check": correction_spec,
        "strict_source_resolution_report": source_resolution,
        "rejected_source_report": rejected_sources,
        "metric_reconciliation_report": metric_reconciliation,
        "side_by_side_comparison_report": side_by_side,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
        **visual_outputs,
    }

    for name, frame in {
        "source_report_check": source_check,
        "phase14f_result_check": phase14f_check,
        "correction_spec_input_check": correction_spec,
        "visual_output_inventory": visual_output_inventory,
        "boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }.items():
        frame.to_csv(reports_path / f"phase14g_corrected_visual_{name}.csv", index=False)

    print("Wrote Phase 14G corrected visual backtest reports.")
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


def _reconciliation_decision_report(
    *,
    phase14g_conclusion: pd.DataFrame,
    source_resolution: pd.DataFrame,
    metric_reconciliation: pd.DataFrame,
    current_signal: pd.DataFrame,
    section: dict[str, Any],
) -> pd.DataFrame:
    corrected_source_identity_passed = (
        not source_resolution.empty
        and _bool_value(source_resolution.iloc[0].get("corrected_source_identity_passed", False))
    )
    metric_reconciliation_passed = (
        not metric_reconciliation.empty
        and bool(metric_reconciliation["metric_reconciliation_passed"].all())
    )
    current_signal_state_determined = (
        not current_signal.empty
        and _bool_value(current_signal.iloc[0].get("signal_determined", False))
    )
    phase14g_passed = (
        not phase14g_conclusion.empty
        and _bool_value(phase14g_conclusion.iloc[0].get("all_gates_passed", False))
    )

    paper_workflow_allowed = bool(
        phase14g_passed
        and corrected_source_identity_passed
        and metric_reconciliation_passed
        and current_signal_state_determined
    )

    policy = section.get("decision_policy", {})

    decision = (
        policy.get("decision_if_passed", "allow_paper_workflow_preregistration_next")
        if paper_workflow_allowed
        else policy.get("decision_if_failed", "block_paper_workflow_and_continue_source_correction")
    )

    return pd.DataFrame(
        [
            {
                "decision": decision,
                "corrected_source_identity_passed": corrected_source_identity_passed,
                "metric_reconciliation_passed": metric_reconciliation_passed,
                "current_signal_state_determined": current_signal_state_determined,
                "paper_workflow_preregistration_allowed": paper_workflow_allowed,
                "paper_trading_deployment_allowed": False,
                "paper_trading_ready": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "candidate_promotion": False,
                "final_candidate_changed": False,
            }
        ]
    )


def save_phase14h_corrected_visual_backtest_audit_reconciliation_decision(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(
        config,
        "phase14h_corrected_visual_backtest_audit_reconciliation_decision",
    )
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    flags = _config_flag_check(config, section.get("expected_runtime_flags", {}))
    reports = section.get("phase14g_reports", {})
    inventory = _report_inventory(reports)
    phase14g_check = _phase_result_check(
        reports["conclusion"],
        reports["gate_report"],
        "Phase 14G",
    )
    charts = _chart_inventory(section.get("chart_files", []))

    phase14g_conclusion = _read_csv_if_exists(reports["conclusion"])
    source_resolution = _read_csv_if_exists(reports["strict_source_resolution_report"])
    metric_reconciliation = _read_csv_if_exists(reports["metric_reconciliation_report"])
    current_signal = _read_csv_if_exists(reports["current_signal_state_report"])

    decision = _reconciliation_decision_report(
        phase14g_conclusion=phase14g_conclusion,
        source_resolution=source_resolution,
        metric_reconciliation=metric_reconciliation,
        current_signal=current_signal,
        section=section,
    )
    boundary = _boundary_check(section, "phase14i_boundary")
    scope = _scope_check(section)

    corrected_source_identity_passed = _bool_value(
        decision.iloc[0]["corrected_source_identity_passed"]
    )
    metric_reconciliation_passed = _bool_value(
        decision.iloc[0]["metric_reconciliation_passed"]
    )
    no_paper_workflow_if_failed = not (
        (not corrected_source_identity_passed or not metric_reconciliation_passed)
        and _bool_value(decision.iloc[0]["paper_workflow_preregistration_allowed"])
    )

    summary = pd.DataFrame(
        [
            {
                "audit_role": section.get("audit_role", ""),
                "implementation_classification": section.get("implementation_classification", ""),
                "phase14g_passed": bool(phase14g_check["passed"].all()),
                "config_flags_clean": bool(flags["passed"].all()),
                "all_corrected_reports_present": bool(inventory["present"].all()) if not inventory.empty else False,
                "corrected_report_rows_non_empty": bool(inventory["passed"].all()) if not inventory.empty else False,
                "chart_files_present": bool(charts["passed"].all()) if not charts.empty else False,
                "corrected_source_identity_passed": corrected_source_identity_passed,
                "metric_reconciliation_passed": metric_reconciliation_passed,
                "paper_workflow_preregistration_allowed": _bool_value(
                    decision.iloc[0]["paper_workflow_preregistration_allowed"]
                ),
                "no_paper_workflow_if_failed": no_paper_workflow_if_failed,
                "boundary_passed": bool(boundary["passed"].all()),
                "scope_passed": bool(scope["passed"].all()),
                "live_trading": False,
                "real_money_deployment": False,
                "paper_trading_ready_claim": False,
                "candidate_promotion": False,
                "final_candidate_change": False,
            }
        ]
    )

    gate_report = pd.DataFrame(
        [
            _gate_row("Phase 14G passed", bool(summary.iloc[0]["phase14g_passed"]), "phase14g"),
            _gate_row("Config flags clean", bool(summary.iloc[0]["config_flags_clean"]), "runtime flags"),
            _gate_row("All corrected reports present", bool(summary.iloc[0]["all_corrected_reports_present"]), "reports"),
            _gate_row("Chart files present", bool(summary.iloc[0]["chart_files_present"]), "charts"),
            _gate_row("Corrected source identity passed", corrected_source_identity_passed, "source identity"),
            _gate_row("Metric reconciliation report exists", len(metric_reconciliation) > 0, "metrics"),
            _gate_row("Reconciliation decision report exists", len(decision) == 1, str(decision.iloc[0]["decision"])),
            _gate_row("Current signal state report exists", len(current_signal) == 1, "signal state"),
            _gate_row("No paper workflow if failed", no_paper_workflow_if_failed, "paper workflow gate"),
            _gate_row("Phase 14I boundary is conditional-only", bool(boundary["passed"].all()), "phase14i"),
            _gate_row("Scope blocks forbidden actions", bool(scope["passed"].all()), "scope"),
            _gate_row(
                "Audit role is correct",
                section.get("audit_role")
                == "Corrected visual backtest audit and reconciliation decision only",
                section.get("audit_role", ""),
            ),
        ]
    )
    gate_report["all_gates_passed"] = bool(gate_report["passed"].all())

    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 14H",
                "diagnostic": "Corrected visual backtest audit and reconciliation decision",
                "verdict": (
                    "Completed — corrected visual backtest audit/reconciliation passed"
                    if bool(gate_report["passed"].all())
                    else "Failed corrected visual backtest audit/reconciliation"
                ),
                "all_gates_passed": bool(gate_report["passed"].all()),
                "corrected_source_identity_passed": corrected_source_identity_passed,
                "metric_reconciliation_passed": metric_reconciliation_passed,
                "paper_workflow_preregistration_allowed": _bool_value(
                    decision.iloc[0]["paper_workflow_preregistration_allowed"]
                ),
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
        "phase14g_result_check": phase14g_check,
        "chart_inventory_check": charts,
        "reconciliation_decision_report": decision,
        "phase14i_boundary_check": boundary,
        "scope_boundary_check": scope,
        "summary": summary,
        "gate_report": gate_report,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(reports_path / f"phase14h_corrected_visual_audit_{name}.csv", index=False)

    print("Wrote Phase 14H corrected visual audit/reconciliation reports.")
    return outputs