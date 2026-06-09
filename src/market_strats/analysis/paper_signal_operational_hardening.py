from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PHASE18A_SECTION = "phase18a_paper_signal_operational_hardening"
DEFAULT_SYMBOLS = ["SPY", "QQQ", "GLD", "TLT", "BTC-USD"]
CRYPTO_SYMBOLS = {"BTC-USD"}
HASH_SCOPES = {
    "phase6b_6c_overlay_baseline": [
        "research_period",
        "start_date",
        "end_date",
        "initial_capital",
        "cash_ticker",
        "use_cash_yield",
        "slippage_bps",
        "phase14i_phase6b_candidate_daily_stream_export",
        "phase14j_phase6b_candidate_export_audit",
        "phase15s_phase6b_rule_replay_source_discovery",
        "phase15u_reusable_phase6b_rule_replay_engine",
    ],
    "phase15wxyz_fresh_extension": [
        "phase15wxyz_fresh_extension_pipeline",
        "phase15m_fresh_current_signal_generation",
        "phase15n_fresh_signal_audit_paper_dry_run_eligibility",
    ],
    "phase16_paper_signal": [
        "phase16a_paper_dry_run_preregistration",
        "phase16b_paper_dry_run_dashboard",
    ],
    "phase17_strategy_factory_watchlist": [
        "phase17a_strategy_factory",
        "phase17b_strategy_factory_robustness",
        "phase17c_strategy_factory_watchlist_dashboard",
    ],
}


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE18A_SECTION, {}) or {}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict | list | tuple | set):
        return False
    return bool(pd.isna(value))


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if _is_missing(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text_value(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _resolve_path(path_value: str | Path | None, fallback: Path) -> Path:
    if path_value is None or str(path_value).strip() == "":
        return fallback
    return Path(path_value)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    return pd.read_csv(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_date(frame: pd.DataFrame, column: str = "date") -> pd.Timestamp | pd.NaT:
    if frame.empty or column not in frame.columns:
        return pd.NaT
    dates = pd.to_datetime(frame[column], errors="coerce")
    if not dates.notna().any():
        return pd.NaT
    return dates.max()


def build_signal_date_policy_report(
    *,
    config: dict[str, Any],
    fresh_stream: pd.DataFrame,
) -> pd.DataFrame:
    section = _section(config)
    phase15m = config.get("phase15m_fresh_current_signal_generation", {}) or {}
    configured_audit_date = _text_value(phase15m.get("audit_current_date", ""))
    latest_fresh_date = _latest_date(fresh_stream)
    latest_available_if_absent = _bool_value(
        section.get("use_latest_available_when_audit_date_missing", True)
    )
    allow_override = _bool_value(section.get("allow_audit_date_override", False))

    configured_ts = pd.to_datetime(configured_audit_date, errors="coerce")
    warning = ""
    audit_capped = False
    override_applied = False

    if pd.notna(latest_fresh_date) and pd.notna(configured_ts):
        audit_capped = bool(configured_ts < latest_fresh_date)
        if audit_capped:
            warning = "configured_audit_date_older_than_latest_fresh_stream_date"
        selected = latest_fresh_date if audit_capped and allow_override else configured_ts
        override_applied = bool(audit_capped and allow_override)
    elif pd.notna(latest_fresh_date) and latest_available_if_absent:
        selected = latest_fresh_date
    elif pd.notna(configured_ts):
        selected = configured_ts
    else:
        selected = pd.NaT
        warning = "no_valid_signal_date_available"

    return pd.DataFrame(
        [
            {
                "configured_audit_date": (
                    configured_ts.strftime("%Y-%m-%d") if pd.notna(configured_ts) else ""
                ),
                "latest_fresh_stream_date": (
                    latest_fresh_date.strftime("%Y-%m-%d")
                    if pd.notna(latest_fresh_date)
                    else ""
                ),
                "selected_signal_date": (
                    selected.strftime("%Y-%m-%d") if pd.notna(selected) else ""
                ),
                "configured_audit_date_capped_run": audit_capped and not override_applied,
                "audit_date_override_allowed": allow_override,
                "audit_date_override_applied": override_applied,
                "latest_available_row_used_if_audit_date_absent": (
                    latest_available_if_absent and configured_audit_date == ""
                ),
                "warning": warning,
                "policy_explicit": pd.notna(selected),
            }
        ]
    )


def _price_column(frame: pd.DataFrame) -> str | None:
    for column in ["adj_close", "close", "price"]:
        if column in frame.columns:
            return column
    return None


def _asset_type(symbol: str) -> str:
    return "crypto" if symbol in CRYPTO_SYMBOLS else "etf"


def _daily_return_thresholds(
    *,
    symbol: str,
    quality_config: dict[str, Any],
) -> tuple[float, float]:
    legacy_warning = quality_config.get("max_abs_daily_return_warning_pct")
    legacy_block = quality_config.get("max_abs_daily_return_block_pct")
    if _asset_type(symbol) == "crypto":
        warning = quality_config.get(
            "btc_warning_abs_daily_return_pct",
            legacy_warning if legacy_warning is not None else 20,
        )
        block = quality_config.get(
            "btc_block_abs_daily_return_pct",
            legacy_block if legacy_block is not None else 40,
        )
    else:
        warning = quality_config.get(
            "etf_warning_abs_daily_return_pct",
            legacy_warning if legacy_warning is not None else 20,
        )
        block = quality_config.get(
            "etf_block_abs_daily_return_pct",
            legacy_block if legacy_block is not None else 40,
        )
    return float(warning), float(block)


def _check_latest_context_columns(
    *,
    frame: pd.DataFrame,
    latest_index: Any,
) -> tuple[bool, list[str]]:
    context_columns = [column for column in ["high", "low", "volume"] if column in frame.columns]
    if not context_columns:
        return True, []

    warnings: list[str] = []
    latest = frame.loc[latest_index]
    for column in context_columns:
        value = pd.to_numeric(pd.Series([latest[column]]), errors="coerce").iloc[0]
        if pd.isna(value):
            warnings.append(f"latest_{column}_null_when_available")
        elif column in {"high", "low"} and value <= 0:
            warnings.append(f"latest_{column}_non_positive_when_available")
        elif column == "volume" and value < 0:
            warnings.append("latest_volume_negative_when_available")
    return len(warnings) == 0, warnings


def inspect_fresh_data_quality(
    *,
    data_dir: str | Path,
    symbols: list[str] | None = None,
    quality_config: dict[str, Any] | None = None,
    current_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    qcfg = quality_config or {}
    selected = symbols or DEFAULT_SYMBOLS
    data_path = Path(data_dir)
    require_positive = _bool_value(qcfg.get("require_positive_prices", True))
    require_no_duplicates = _bool_value(qcfg.get("require_no_duplicate_dates", True))
    require_latest_non_null = _bool_value(qcfg.get("require_latest_row_non_null", True))
    require_context_when_available = _bool_value(
        qcfg.get("require_high_low_volume_when_available", False)
    )
    today = (current_date or pd.Timestamp.now(tz=timezone.utc)).date()

    report_rows: list[dict[str, Any]] = []
    latest_rows: list[dict[str, Any]] = []

    for symbol in selected:
        path = data_path / f"{symbol}.parquet"
        warnings: list[str] = []
        blocks: list[str] = []
        frame = pd.DataFrame()
        price_col = ""
        asset_type = _asset_type(symbol)
        warning_threshold, block_threshold = _daily_return_thresholds(
            symbol=symbol,
            quality_config=qcfg,
        )

        file_exists = path.exists()
        if file_exists:
            try:
                frame = pd.read_parquet(path)
            except Exception as exc:  # pragma: no cover - safety report path
                blocks.append(f"read_failed:{exc}")
        else:
            blocks.append("file_missing")

        required_columns_present = False
        rows = len(frame)
        latest_date = pd.NaT
        min_date = pd.NaT
        latest_price = pd.NA
        max_abs_return_pct = pd.NA
        latest_abs_return_pct = pd.NA
        latest_non_null = False
        positive_prices_pass = False
        duplicate_dates_pass = False
        latest_not_future = False
        weekend_rows = 0
        context_columns_pass = True

        if not frame.empty:
            price_col = _price_column(frame) or ""
            required_columns_present = bool("date" in frame.columns and price_col)
            if not required_columns_present:
                blocks.append("required_date_or_price_columns_missing")
            else:
                work = frame[["date", price_col]].copy()
                work["date"] = pd.to_datetime(work["date"], errors="coerce")
                work[price_col] = pd.to_numeric(work[price_col], errors="coerce")
                work = work.dropna(subset=["date"]).sort_values("date")
                if work.empty:
                    blocks.append("no_valid_dates")
                else:
                    min_date = work["date"].min()
                    latest_date = work["date"].max()
                    latest = work.iloc[-1]
                    latest_price = latest[price_col]
                    latest_source_index = latest.name
                    latest_non_null = bool(pd.notna(latest_price))
                    if require_latest_non_null and not latest_non_null:
                        blocks.append("latest_row_price_null")
                    context_columns_pass, context_failures = _check_latest_context_columns(
                        frame=frame,
                        latest_index=latest_source_index,
                    )
                    if require_context_when_available:
                        blocks.extend(context_failures)
                    positive_prices_pass = bool((work[price_col].dropna() > 0).all())
                    if require_positive and not positive_prices_pass:
                        blocks.append("non_positive_price_present")
                    duplicate_dates_pass = bool(not work["date"].duplicated().any())
                    if require_no_duplicates and not duplicate_dates_pass:
                        blocks.append("duplicate_dates_present")
                    latest_not_future = bool(latest_date.date() <= today)
                    if not latest_not_future:
                        blocks.append("latest_row_future_dated")
                    returns = work[price_col].pct_change().abs() * 100.0
                    if returns.notna().any():
                        max_abs_return_pct = round(float(returns.max()), 4)
                        latest_abs_return_pct = round(float(returns.dropna().iloc[-1]), 4)
                        if latest_abs_return_pct >= block_threshold:
                            blocks.append("daily_return_outlier_block")
                        elif latest_abs_return_pct >= warning_threshold:
                            warnings.append("daily_return_outlier_warning")
                    weekend_rows = int((work["date"].dt.dayofweek >= 5).sum())
                    if symbol == "BTC-USD":
                        if weekend_rows > 0:
                            warnings.append("btc_weekend_data_available_common_date_caveat")
                        else:
                            warnings.append("btc_weekend_rows_missing_common_date_caveat")
                    latest_rows.append(
                        {
                            "symbol": symbol,
                            "source_path": str(path),
                            "latest_date": latest_date.strftime("%Y-%m-%d"),
                            "price_column": price_col,
                            "latest_price": latest_price,
                        }
                    )
        elif file_exists:
            blocks.append("file_empty")

        report_rows.append(
            {
                "symbol": symbol,
                "source_path": str(path),
                "asset_type": asset_type,
                "file_exists": file_exists,
                "rows": rows,
                "required_columns_present": required_columns_present,
                "price_column": price_col,
                "warning_abs_daily_return_pct": warning_threshold,
                "block_abs_daily_return_pct": block_threshold,
                "min_date": min_date.strftime("%Y-%m-%d") if pd.notna(min_date) else "",
                "latest_date": latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else "",
                "latest_price": latest_price,
                "latest_row_price_non_null": latest_non_null,
                "high_low_volume_when_available_pass": context_columns_pass,
                "positive_prices_pass": positive_prices_pass,
                "duplicate_dates_pass": duplicate_dates_pass,
                "latest_row_not_future": latest_not_future,
                "max_abs_daily_return_pct": max_abs_return_pct,
                "latest_abs_daily_return_pct": latest_abs_return_pct,
                "outlier_warning": any("warning" in item for item in warnings),
                "outlier_block": any("block" in item for item in blocks),
                "btc_weekend_rows": weekend_rows if symbol == "BTC-USD" else pd.NA,
                "warnings": ";".join(sorted(set(warnings))),
                "blocking_failures": ";".join(sorted(set(blocks))),
                "quality_status": "blocked" if blocks else "warning" if warnings else "passed",
            }
        )

    return pd.DataFrame(report_rows), pd.DataFrame(latest_rows)


def build_config_hash_report(
    *,
    config: dict[str, Any],
    generated_at_utc: str | None = None,
) -> pd.DataFrame:
    generated_at = generated_at_utc or _generated_at()
    rows = []
    for scope, keys in HASH_SCOPES.items():
        payload = {key: config.get(key) for key in keys if key in config}
        encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        rows.append(
            {
                "hash_scope": scope,
                "hash_value": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                "included_config_keys": ",".join(payload.keys()),
                "generated_at_utc": generated_at,
                "notes": "deterministic_sha256_over_relevant_config_sections",
            }
        )
    return pd.DataFrame(rows)


def build_watchlist_paper_preview(
    *,
    config: dict[str, Any],
    watchlist_candidates: pd.DataFrame,
    latest_allocations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    section = _section(config)
    preview_cfg = section.get("watchlist_preview", {}) or {}
    include = [str(item) for item in preview_cfg.get("include_candidates", [])]
    notional = float(preview_cfg.get("paper_notional_usd", 10000))

    candidates = watchlist_candidates.copy()
    if not include and "candidate_id" in candidates.columns:
        include = candidates["candidate_id"].astype(str).tolist()
    if not candidates.empty and "candidate_id" in candidates.columns:
        candidates = candidates[candidates["candidate_id"].astype(str).isin(include)]

    allocations = latest_allocations.copy()
    if not allocations.empty:
        allocations["strategy_id"] = allocations["strategy_id"].astype(str)
        allocations["asset"] = allocations["asset"].astype(str)
        allocations["weight"] = pd.to_numeric(allocations["weight"], errors="coerce").fillna(0.0)
        allocations = allocations[allocations["strategy_id"].isin(include)]

    rows: list[dict[str, Any]] = []
    for candidate_id in include:
        candidate = candidates.loc[candidates.get("candidate_id", pd.Series(dtype=str)) == candidate_id]
        candidate_row = candidate.iloc[0] if not candidate.empty else pd.Series(dtype=object)
        role = _text_value(candidate_row.get("watchlist_role", "watchlist_candidate"))
        candidate_alloc = allocations[allocations["strategy_id"] == candidate_id]
        if candidate_alloc.empty:
            rows.append(
                _watchlist_preview_row(
                    candidate_id=candidate_id,
                    role=role,
                    paper_notional=notional,
                    asset="",
                    weight=0.0,
                    warning="latest_allocation_missing",
                    candidate_row=candidate_row,
                )
            )
            continue
        for alloc in candidate_alloc.to_dict(orient="records"):
            warning = ""
            if candidate_id == "sf_spy_qqq_btc_capped_offensive":
                warning = (
                    "btc_watchlist_candidate_caveat:btc_cap_dependency;"
                    "btc_weekend_gap_risk;not_represented_in_phase16_baseline_preview"
                )
            rows.append(
                _watchlist_preview_row(
                    candidate_id=candidate_id,
                    role=role,
                    paper_notional=notional,
                    asset=str(alloc["asset"]),
                    weight=float(alloc["weight"]),
                    warning=warning,
                    candidate_row=candidate_row,
                )
            )

    preview = pd.DataFrame(rows)
    if preview.empty:
        orders = preview.copy()
    else:
        orders = preview[preview["target_weight"].astype(float).abs() > 1e-10].copy()
    return preview, orders


def _watchlist_preview_row(
    *,
    candidate_id: str,
    role: str,
    paper_notional: float,
    asset: str,
    weight: float,
    warning: str,
    candidate_row: pd.Series,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_role": role,
        "paper_notional_usd": paper_notional,
        "asset": asset,
        "target_weight": weight,
        "target_notional_usd": round(paper_notional * weight, 2),
        "preview_action": "manual_watchlist_preview_only",
        "execution_instruction": "manual_watchlist_preview_only_no_order_placement",
        "paper_watchlist_only": True,
        "promotion_allowed": False,
        "paper_trading_ready": False,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
        "blocking_warnings": warning,
        "source_paper_watchlist_only": _bool_value(
            candidate_row.get("paper_watchlist_only", True)
        ),
        "source_promotion_allowed": _bool_value(candidate_row.get("promotion_allowed", False)),
    }


def build_manual_execution_journal_template(preview_orders: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in preview_orders.to_dict(orient="records"):
        rows.append(
            {
                "journal_date": "",
                "candidate_id": row.get("candidate_id", ""),
                "asset": row.get("asset", ""),
                "target_weight": row.get("target_weight", 0.0),
                "target_notional_usd": row.get("target_notional_usd", 0.0),
                "manual_execution_status": "not_entered",
                "paper_account_value": "",
                "paper_fill_price": "",
                "paper_fill_quantity": "",
                "deviation_from_preview": "",
                "notes": "",
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        )
    return pd.DataFrame(rows)


def _latest_signal_record(baseline_signal: pd.DataFrame) -> pd.Series:
    if baseline_signal.empty:
        return pd.Series(dtype=object)
    signal = baseline_signal.copy()
    for column in ["data_as_of_date", "signal_date"]:
        if column in signal.columns:
            signal[column] = pd.to_datetime(signal[column], errors="coerce")
    sort_column = "data_as_of_date" if "data_as_of_date" in signal.columns else "signal_date"
    if sort_column in signal.columns and signal[sort_column].notna().any():
        signal = signal.sort_values(sort_column)
    return signal.iloc[-1]


def _format_bool(value: Any) -> str:
    return "True" if _bool_value(value) else "False"


def _format_date_value(value: Any) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.notna(timestamp):
        return timestamp.strftime("%Y-%m-%d")
    return _text_value(value)


def _format_candidate_allocations(preview: pd.DataFrame) -> str:
    if preview.empty:
        return "not_available"
    allocations: list[str] = []
    for candidate_id, group in preview.groupby("candidate_id", sort=True):
        nonzero = group[pd.to_numeric(group["target_weight"], errors="coerce").fillna(0).abs() > 1e-10]
        if nonzero.empty:
            asset_text = "all target weights are zero"
        else:
            asset_text = ", ".join(
                f"{row.asset}={float(row.target_weight):.2%}"
                for row in nonzero.itertuples(index=False)
            )
        allocations.append(f"{candidate_id}: {asset_text}")
    return " | ".join(allocations)


def _format_preview_orders(preview_orders: pd.DataFrame) -> str:
    if preview_orders.empty:
        return "none"
    return " | ".join(
        (
            f"{row.candidate_id}: {row.asset} target_weight="
            f"{float(row.target_weight):.2%}, notional=${float(row.target_notional_usd):,.2f}"
        )
        for row in preview_orders.itertuples(index=False)
    )


def _candidate_list(frame: pd.DataFrame, column: str = "candidate_id") -> str:
    if frame.empty or column not in frame.columns:
        return "none"
    values = sorted({_text_value(value) for value in frame[column].dropna() if _text_value(value)})
    return ", ".join(values) if values else "none"


def _symbols_with_text(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame.columns:
        return "none"
    rows = frame[frame[column].astype(str).str.len() > 0]
    if rows.empty:
        return "none"
    return ", ".join(rows["symbol"].astype(str).tolist())


def _manual_journal_status(journal_template: pd.DataFrame) -> str:
    if journal_template.empty or "manual_execution_status" not in journal_template.columns:
        return "not_available"
    counts = journal_template["manual_execution_status"].astype(str).value_counts()
    return ", ".join(f"{status}:{count}" for status, count in counts.items())


def _data_quality_action(data_quality: pd.DataFrame) -> tuple[str, str]:
    if data_quality.empty:
        return "MANUAL REVIEW REQUIRED — HOLD CURRENT STATE", "blocked"
    has_blocks = data_quality["blocking_failures"].astype(str).str.len().gt(0).any()
    has_warnings = data_quality["warnings"].astype(str).str.len().gt(0).any()
    if has_blocks:
        return "MANUAL REVIEW REQUIRED — HOLD CURRENT STATE", "blocked"
    if has_warnings:
        return "WARNINGS PRESENT — MANUAL REVIEW BEFORE PAPER ENTRY", "warning"
    return "NO BLOCKING ISSUES — MANUAL PAPER PREVIEW ONLY", "passed"


def _tear_sheet_row(
    *,
    category: str,
    key: str,
    value: Any,
    status: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "category": category,
        "key": key,
        "value": value,
        "status": status,
        "notes": notes,
    }


def build_daily_execution_tear_sheet(
    *,
    signal_policy: pd.DataFrame,
    data_quality: pd.DataFrame,
    baseline_signal: pd.DataFrame,
    preview: pd.DataFrame,
    preview_orders: pd.DataFrame,
    journal_template: pd.DataFrame,
    recurring_paper_trading_ready: bool,
    live_trading_allowed: bool,
    real_money_allowed: bool,
    broker_api_integration_allowed: bool,
) -> tuple[pd.DataFrame, str]:
    policy = signal_policy.iloc[0] if not signal_policy.empty else pd.Series(dtype=object)
    baseline = _latest_signal_record(baseline_signal)
    final_action, quality_status = _data_quality_action(data_quality)

    warning_symbols = _symbols_with_text(data_quality, "warnings")
    blocked_symbols = _symbols_with_text(data_quality, "blocking_failures")
    if not preview.empty and {"candidate_id", "asset", "target_weight"}.issubset(
        preview.columns
    ):
        target_weight = pd.to_numeric(preview["target_weight"], errors="coerce").fillna(0.0)
        btc_candidates = preview[
            preview["candidate_id"].astype(str).str.contains("btc", case=False, na=False)
            | (preview["asset"].astype(str).eq("BTC-USD") & target_weight.gt(0))
        ]
    else:
        btc_candidates = pd.DataFrame()
    btc_caveats = (
        ";".join(
            sorted(
                {
                    _text_value(value)
                    for value in preview.get("blocking_warnings", pd.Series(dtype=str))
                    if "btc" in _text_value(value).lower()
                }
            )
        )
        if not preview.empty
        else ""
    )
    watchlist_only = (
        preview[preview["paper_watchlist_only"].map(_bool_value)]
        if not preview.empty and "paper_watchlist_only" in preview.columns
        else pd.DataFrame()
    )
    baseline_action = _text_value(baseline.get("target_action", ""))
    baseline_signal_text = (
        f"mode={_text_value(baseline.get('current_mode', ''))}; "
        f"exposure={_text_value(baseline.get('current_exposure', ''))}; "
        f"action={baseline_action}"
    )
    safety_all_false = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )

    rows = [
        _tear_sheet_row(
            category="execution_boundary",
            key="execution_status",
            value="MANUAL PAPER PREVIEW ONLY",
            status=final_action,
            notes="NO LIVE TRADING; NO REAL MONEY; NO BROKER/API",
        ),
        _tear_sheet_row(
            category="signal_date_policy",
            key="selected_signal_date",
            value=_text_value(policy.get("selected_signal_date", "")),
            status="policy_explicit",
        ),
        _tear_sheet_row(
            category="signal_date_policy",
            key="data_as_of_date",
            value=_text_value(policy.get("selected_signal_date", "")),
            notes="Phase 18A selected fresh-stream data-as-of date.",
        ),
        _tear_sheet_row(
            category="signal_date_policy",
            key="configured_audit_date",
            value=_text_value(policy.get("configured_audit_date", "")),
        ),
        _tear_sheet_row(
            category="signal_date_policy",
            key="configured_audit_date_capped_run",
            value=_format_bool(policy.get("configured_audit_date_capped_run", False)),
        ),
        _tear_sheet_row(
            category="signal_date_policy",
            key="stale_audit_date_warning_triggered",
            value=_format_bool(bool(_text_value(policy.get("warning", "")))),
            notes=_text_value(policy.get("warning", "")),
        ),
        _tear_sheet_row(
            category="signal_date_policy",
            key="latest_fresh_stream_date",
            value=_text_value(policy.get("latest_fresh_stream_date", "")),
        ),
        _tear_sheet_row(
            category="fresh_data_quality",
            key="fresh_data_quality_status",
            value=quality_status,
            status=final_action,
        ),
        _tear_sheet_row(
            category="fresh_data_quality",
            key="fresh_data_quality_passed",
            value=_format_bool(quality_status != "blocked"),
        ),
        _tear_sheet_row(
            category="fresh_data_quality",
            key="symbols_with_warnings",
            value=warning_symbols,
        ),
        _tear_sheet_row(
            category="fresh_data_quality",
            key="symbols_with_blocking_failures",
            value=blocked_symbols,
        ),
        _tear_sheet_row(
            category="baseline_phase6_signal",
            key="phase6_baseline_signal",
            value=baseline_signal_text,
            notes=(
                f"baseline_signal_date={_format_date_value(baseline.get('signal_date', ''))}; "
                f"baseline_data_as_of_date={_format_date_value(baseline.get('data_as_of_date', ''))}"
            ),
        ),
        _tear_sheet_row(
            category="baseline_phase6_signal",
            key="baseline_paper_action",
            value=baseline_action,
        ),
        _tear_sheet_row(
            category="watchlist_preview",
            key="strategy_factory_watchlist_target_allocations",
            value=_format_candidate_allocations(preview),
        ),
        _tear_sheet_row(
            category="watchlist_preview",
            key="nonzero_watchlist_preview_orders",
            value=_format_preview_orders(preview_orders),
        ),
        _tear_sheet_row(
            category="watchlist_preview",
            key="watchlist_only_candidates",
            value=_candidate_list(watchlist_only),
        ),
        _tear_sheet_row(
            category="watchlist_preview",
            key="candidate_includes_or_can_include_btc",
            value=_candidate_list(btc_candidates),
            notes="BTC candidate remains watchlist-only and is not represented in Phase 16 baseline execution.",
        ),
        _tear_sheet_row(
            category="watchlist_preview",
            key="btc_caveats",
            value=btc_caveats or "none",
        ),
        _tear_sheet_row(
            category="manual_journal",
            key="manual_journal_status",
            value=_manual_journal_status(journal_template),
        ),
        _tear_sheet_row(
            category="safety_flags",
            key="live_trading_allowed",
            value=_format_bool(live_trading_allowed),
        ),
        _tear_sheet_row(
            category="safety_flags",
            key="real_money_allowed",
            value=_format_bool(real_money_allowed),
        ),
        _tear_sheet_row(
            category="safety_flags",
            key="broker_api_integration_allowed",
            value=_format_bool(broker_api_integration_allowed),
        ),
        _tear_sheet_row(
            category="safety_flags",
            key="all_execution_safety_flags_false",
            value=_format_bool(safety_all_false),
        ),
        _tear_sheet_row(
            category="readiness",
            key="recurring_paper_trading_ready",
            value=_format_bool(recurring_paper_trading_ready),
        ),
        _tear_sheet_row(
            category="final_action",
            key="final_recommended_manual_action",
            value=final_action,
            status=final_action,
        ),
    ]
    tear_sheet = pd.DataFrame(rows)

    markdown = "\n".join(
        [
            "# Phase 18A Daily Execution Tear Sheet",
            "",
            "**NO LIVE TRADING**",
            "",
            "**NO REAL MONEY**",
            "",
            "**NO BROKER/API**",
            "",
            "**MANUAL PAPER PREVIEW ONLY**",
            "",
            "## Final Recommended Manual Action",
            "",
            f"**{final_action}**",
            "",
            "## Signal Date Policy",
            "",
            f"- Selected signal date: {_text_value(policy.get('selected_signal_date', ''))}",
            f"- Data-as-of date: {_text_value(policy.get('selected_signal_date', ''))}",
            f"- Configured audit date: {_text_value(policy.get('configured_audit_date', ''))}",
            (
                "- Configured audit date capped run: "
                f"{_format_bool(policy.get('configured_audit_date_capped_run', False))}"
            ),
            (
                "- Stale audit-date warning: "
                f"{_text_value(policy.get('warning', '')) or 'none'}"
            ),
            (
                "- Latest fresh stream date: "
                f"{_text_value(policy.get('latest_fresh_stream_date', ''))}"
            ),
            "",
            "## Fresh Data Quality",
            "",
            f"- Aggregate status: {quality_status}",
            f"- Symbols with warnings: {warning_symbols}",
            f"- Symbols with blocking failures: {blocked_symbols}",
            "",
            "## Baseline Phase6 Paper Signal",
            "",
            f"- {baseline_signal_text}",
            f"- Baseline paper action: {baseline_action or 'not_available'}",
            "",
            "## Strategy Factory Watchlist Preview",
            "",
            f"- Target allocations: {_format_candidate_allocations(preview)}",
            f"- Nonzero preview orders: {_format_preview_orders(preview_orders)}",
            f"- Watchlist-only candidates: {_candidate_list(watchlist_only)}",
            f"- Candidate includes or can include BTC: {_candidate_list(btc_candidates)}",
            f"- BTC caveats: {btc_caveats or 'none'}",
            "",
            "## Manual Journal",
            "",
            f"- Manual journal status: {_manual_journal_status(journal_template)}",
            "",
            "## Safety Flags",
            "",
            f"- Live trading allowed: {_format_bool(live_trading_allowed)}",
            f"- Real money allowed: {_format_bool(real_money_allowed)}",
            f"- Broker/API integration allowed: {_format_bool(broker_api_integration_allowed)}",
            f"- Recurring paper trading ready: {_format_bool(recurring_paper_trading_ready)}",
            "",
            "This tear sheet is a manual paper-preview summary only. It does not place orders.",
            "",
        ]
    )
    return tear_sheet, markdown


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def save_phase18a_paper_signal_operational_hardening(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _section(config)
    if not section.get("enabled", False):
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    output_dir = _resolve_path(
        section.get("output_dir"),
        reports_path / "paper_trading" / "operational_hardening",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    source_files = section.get("source_files", {}) or {}
    fresh_stream_path = _resolve_path(
        source_files.get("fresh_stream"),
        Path("data/fresh/phase15q_rule_generated_candidate_stream.csv"),
    )
    fresh_processed_dir = _resolve_path(
        source_files.get("fresh_processed_data_dir"),
        Path("data/fresh/processed"),
    )
    latest_signal_path = _resolve_path(
        source_files.get("baseline_latest_signal"),
        reports_path / "paper_trading" / "latest_signal.csv",
    )
    watchlist_path = _resolve_path(
        source_files.get("watchlist_candidates"),
        reports_path / "strategy_factory" / "watchlist" / "phase17c_watchlist_candidates.csv",
    )
    latest_allocations_path = _resolve_path(
        source_files.get("strategy_latest_allocations"),
        reports_path / "strategy_factory" / "transactions" / "strategy_latest_allocations.csv",
    )

    fresh_stream = _read_csv(fresh_stream_path)
    baseline_signal = _read_csv(latest_signal_path)
    watchlist_candidates = _read_csv(watchlist_path)
    latest_allocations = _read_csv(latest_allocations_path)
    generated_at_utc = _generated_at()

    signal_policy = build_signal_date_policy_report(config=config, fresh_stream=fresh_stream)
    data_quality, latest_rows = inspect_fresh_data_quality(
        data_dir=fresh_processed_dir,
        symbols=DEFAULT_SYMBOLS,
        quality_config=section.get("data_quality", {}) or {},
    )
    config_hash = build_config_hash_report(
        config=config,
        generated_at_utc=generated_at_utc,
    )
    preview, preview_orders = build_watchlist_paper_preview(
        config=config,
        watchlist_candidates=watchlist_candidates,
        latest_allocations=latest_allocations,
    )
    journal_template = build_manual_execution_journal_template(preview_orders)
    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    tear_sheet, tear_sheet_markdown = build_daily_execution_tear_sheet(
        signal_policy=signal_policy,
        data_quality=data_quality,
        baseline_signal=baseline_signal,
        preview=preview,
        preview_orders=preview_orders,
        journal_template=journal_template,
        recurring_paper_trading_ready=False,
        live_trading_allowed=live_trading_allowed,
        real_money_allowed=real_money_allowed,
        broker_api_integration_allowed=broker_api_integration_allowed,
    )
    tear_sheet_path = output_dir / "daily_execution_tear_sheet.csv"
    tear_sheet_md_path = output_dir / "daily_execution_tear_sheet.md"
    _write_csv(tear_sheet, tear_sheet_path)
    _write_text(tear_sheet_markdown, tear_sheet_md_path)
    daily_execution_tear_sheet_written = tear_sheet_path.exists() and not tear_sheet.empty
    daily_execution_tear_sheet_md_written = (
        tear_sheet_md_path.exists() and tear_sheet_md_path.stat().st_size > 0
    )
    final_manual_action = _text_value(
        tear_sheet.loc[
            tear_sheet["key"] == "final_recommended_manual_action",
            "value",
        ].iloc[0]
    )

    safety_failed = any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )
    data_quality_blocked = bool(
        not data_quality.empty
        and data_quality["blocking_failures"].astype(str).str.len().gt(0).any()
    )
    signal_policy_explicit = bool(
        not signal_policy.empty and _bool_value(signal_policy.iloc[0].get("policy_explicit", False))
    )
    baseline_signal_exists = not baseline_signal.empty
    watchlist_preview_written = not preview.empty
    hashes_written = not config_hash.empty

    gates = pd.DataFrame(
        [
            _gate_row("fresh_data_quality_no_blocking_failures", not data_quality_blocked),
            _gate_row("signal_date_policy_explicit", signal_policy_explicit),
            _gate_row("config_hashes_written", hashes_written),
            _gate_row("baseline_phase16_paper_signal_exists", baseline_signal_exists),
            _gate_row("watchlist_preview_written", watchlist_preview_written),
            _gate_row(
                "daily_execution_tear_sheet_written",
                daily_execution_tear_sheet_written,
            ),
            _gate_row(
                "daily_execution_tear_sheet_md_written",
                daily_execution_tear_sheet_md_written,
            ),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row(
                "broker_api_integration_disabled",
                not broker_api_integration_allowed,
            ),
            _gate_row("no_safety_flags_true", not safety_failed),
        ]
    )
    all_gates_passed = bool(gates["passed"].all())
    gates["all_gates_passed"] = all_gates_passed
    failed_gates = ";".join(gates.loc[~gates["passed"], "gate_id"].astype(str).tolist())

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 18A",
                "decision": (
                    "paper_signal_operational_hardening_completed_manual_preview_only"
                    if all_gates_passed
                    else "paper_signal_operational_hardening_failed_closed"
                ),
                "all_gates_passed": all_gates_passed,
                "recurring_paper_trading_ready": False,
                "manual_preview_only": True,
                "fresh_symbols_checked": len(data_quality),
                "fresh_symbols_blocked": int(
                    data_quality["blocking_failures"].astype(str).str.len().gt(0).sum()
                )
                if not data_quality.empty
                else 0,
                "configured_audit_date": signal_policy.iloc[0].get("configured_audit_date", "")
                if not signal_policy.empty
                else "",
                "latest_fresh_stream_date": signal_policy.iloc[0].get(
                    "latest_fresh_stream_date",
                    "",
                )
                if not signal_policy.empty
                else "",
                "selected_signal_date": signal_policy.iloc[0].get("selected_signal_date", "")
                if not signal_policy.empty
                else "",
                "watchlist_preview_rows": len(preview),
                "watchlist_preview_order_rows": len(preview_orders),
                "daily_execution_tear_sheet_written": daily_execution_tear_sheet_written,
                "daily_execution_tear_sheet_md_written": (
                    daily_execution_tear_sheet_md_written
                ),
                "final_manual_action": final_manual_action,
                "config_hash_rows": len(config_hash),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "generated_at_utc": generated_at_utc,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 18A",
                "diagnostic": "Recurring paper-signal hardening and watchlist paper-preview integration",
                "decision": summary.iloc[0]["decision"],
                "all_gates_passed": all_gates_passed,
                "recurring_paper_trading_ready": False,
                "paper_trading_ready": False,
                "manual_preview_only": True,
                "paper_watchlist_preview_written": watchlist_preview_written,
                "daily_execution_tear_sheet_written": daily_execution_tear_sheet_written,
                "daily_execution_tear_sheet_md_written": (
                    daily_execution_tear_sheet_md_written
                ),
                "final_manual_action": final_manual_action,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
            }
        ]
    )
    dashboard_status = summary[
        [
            "phase",
            "decision",
            "all_gates_passed",
            "recurring_paper_trading_ready",
            "manual_preview_only",
            "fresh_symbols_checked",
            "fresh_symbols_blocked",
            "selected_signal_date",
            "watchlist_preview_rows",
            "daily_execution_tear_sheet_written",
            "daily_execution_tear_sheet_md_written",
            "final_manual_action",
            "failure_reason",
        ]
    ].copy()

    outputs = {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "fresh_data_quality_report": data_quality,
        "fresh_data_latest_rows": latest_rows,
        "signal_date_policy_report": signal_policy,
        "config_hash_report": config_hash,
        "watchlist_paper_preview": preview,
        "watchlist_paper_preview_orders": preview_orders,
        "manual_execution_journal_template": journal_template,
        "daily_execution_tear_sheet": tear_sheet,
        "operational_hardening_status": dashboard_status,
    }

    _write_csv(summary, output_dir / "phase18a_summary.csv")
    _write_csv(gates, output_dir / "phase18a_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase18a_conclusion.csv")
    _write_csv(data_quality, output_dir / "fresh_data_quality_report.csv")
    _write_csv(latest_rows, output_dir / "fresh_data_latest_rows.csv")
    _write_csv(signal_policy, output_dir / "signal_date_policy_report.csv")
    _write_csv(config_hash, output_dir / "config_hash_report.csv")
    _write_csv(preview, output_dir / "watchlist_paper_preview.csv")
    _write_csv(preview_orders, output_dir / "watchlist_paper_preview_orders.csv")
    _write_csv(journal_template, output_dir / "manual_execution_journal_template.csv")
    _write_csv(tear_sheet, tear_sheet_path)
    _write_text(tear_sheet_markdown, tear_sheet_md_path)
    _write_csv(dashboard_status, dashboard_dir / "operational_hardening_status.csv")

    print("Wrote Phase 18A paper-signal operational hardening reports.")
    return outputs
