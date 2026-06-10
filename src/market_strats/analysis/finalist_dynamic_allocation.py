from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PHASE20B_SECTION = "phase20b_finalist_dynamic_allocation"
PRICE_COLUMNS = ["adj_close", "Adj Close", "close", "Close", "price"]
DEFAULT_TEAR_SHEET = Path("reports/paper_trading/operational_hardening/daily_execution_tear_sheet.csv")


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE20B_SECTION, {}) or {}


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


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tear_sheet_values(tear_sheet: pd.DataFrame) -> dict[str, str]:
    if tear_sheet.empty or not {"key", "value"}.issubset(tear_sheet.columns):
        return {}
    return {
        _text_value(row["key"]): _text_value(row["value"])
        for row in tear_sheet.to_dict(orient="records")
    }


def _price_column(frame: pd.DataFrame) -> str | None:
    for column in PRICE_COLUMNS:
        if column in frame.columns:
            return column
    lower_map = {str(column).lower(): str(column) for column in frame.columns}
    for column in PRICE_COLUMNS:
        if column.lower() in lower_map:
            return lower_map[column.lower()]
    return None


def _load_price_series(
    *,
    data_dir: Path,
    asset: str,
) -> tuple[pd.Series, str, str]:
    path = data_dir / f"{asset}.parquet"
    if not path.exists():
        return pd.Series(dtype=float), "", "file_missing"
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - defensive report path
        return pd.Series(dtype=float), "", f"read_failed:{exc}"
    if frame.empty:
        return pd.Series(dtype=float), "", "file_empty"
    if "date" not in frame.columns:
        return pd.Series(dtype=float), "", "date_column_missing"
    price_column = _price_column(frame)
    if price_column is None:
        return pd.Series(dtype=float), "", "price_column_missing"

    work = frame[["date", price_column]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work[price_column] = pd.to_numeric(work[price_column], errors="coerce")
    work = work.dropna(subset=["date"]).sort_values("date")
    if work.empty:
        return pd.Series(dtype=float), price_column, "no_valid_dates"
    if work["date"].duplicated().any():
        return pd.Series(dtype=float), price_column, "duplicate_dates_present"
    latest_price = work[price_column].iloc[-1]
    if pd.isna(latest_price):
        return pd.Series(dtype=float), price_column, "latest_price_null"
    if latest_price <= 0:
        return pd.Series(dtype=float), price_column, "latest_price_non_positive"
    if (work[price_column].dropna() <= 0).any():
        return pd.Series(dtype=float), price_column, "non_positive_price_present"
    series = work.set_index("date")[price_column].rename(asset)
    return series, price_column, ""


def _apply_caps(
    raw_weights: pd.Series,
    caps: dict[str, float],
    *,
    tolerance: float = 1e-10,
) -> tuple[pd.Series, list[str], str]:
    if sum(caps.values()) < 1.0 - tolerance:
        return pd.Series(dtype=float), [], "caps_sum_less_than_one"

    raw = raw_weights.astype(float).copy()
    if raw.sum() <= 0 or raw.isna().any():
        return pd.Series(dtype=float), [], "invalid_raw_weights"
    raw = raw / raw.sum()
    final = pd.Series(0.0, index=raw.index, dtype=float)
    remaining = set(raw.index)
    bound: list[str] = []
    remaining_weight = 1.0

    while remaining:
        remaining_raw = raw.loc[list(remaining)]
        raw_sum = float(remaining_raw.sum())
        if raw_sum <= tolerance:
            return pd.Series(dtype=float), bound, "raw_weight_exhausted"
        proposed = remaining_raw / raw_sum * remaining_weight
        violators = [
            asset for asset, weight in proposed.items() if weight > caps[asset] + tolerance
        ]
        if not violators:
            final.loc[list(remaining)] = proposed
            break
        for asset in violators:
            final.loc[asset] = caps[asset]
            remaining.remove(asset)
            if asset not in bound:
                bound.append(asset)
        remaining_weight = 1.0 - float(final.sum())
        if remaining_weight < -tolerance:
            return pd.Series(dtype=float), bound, "cap_redistribution_failed"
        if not remaining and abs(remaining_weight) > 1e-6:
            return pd.Series(dtype=float), bound, "caps_infeasible"

    final = final.clip(lower=0.0)
    total = float(final.sum())
    if not np.isfinite(total) or abs(total - 1.0) > 1e-6:
        return pd.Series(dtype=float), bound, "weights_cannot_be_normalised"
    if any(final[asset] > caps[asset] + 1e-6 for asset in final.index):
        return pd.Series(dtype=float), bound, "cap_violation_after_redistribution"
    return final, sorted(bound), ""


def compute_inverse_vol_allocation(
    *,
    data_dir: str | Path,
    candidate_id: str,
    candidate_config: dict[str, Any],
    selected_signal_date: str,
    paper_notional_usd: float,
    generated_at_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    data_path = Path(data_dir)
    assets = [str(asset) for asset in candidate_config.get("assets", [])]
    lookback_days = int(candidate_config.get("lookback_days", 63))
    max_asset_weight = float(candidate_config.get("max_asset_weight", 0.50))
    btc_max_weight = float(candidate_config.get("btc_max_weight", 0.05))
    require_all_assets = _bool_value(candidate_config.get("require_all_assets", True))
    generated_at = generated_at_utc or _generated_at()

    series_by_asset: dict[str, pd.Series] = {}
    missing_assets: list[str] = []
    load_failures: list[str] = []
    for asset in assets:
        series, _price_col, failure = _load_price_series(data_dir=data_path, asset=asset)
        if failure:
            missing_assets.append(asset)
            load_failures.append(f"{asset}:{failure}")
            continue
        series_by_asset[asset] = series

    if require_all_assets and missing_assets:
        return _blocked_allocation(
            candidate_id=candidate_id,
            assets=assets,
            selected_signal_date=selected_signal_date,
            generated_at_utc=generated_at,
            lookback_days=lookback_days,
            paper_notional_usd=paper_notional_usd,
            max_asset_weight=max_asset_weight,
            btc_max_weight=btc_max_weight,
            assets_loaded=list(series_by_asset),
            missing_assets=missing_assets,
            blocking_reason=";".join(load_failures),
        )

    prices = pd.concat(series_by_asset.values(), axis=1, join="inner").dropna()
    if prices.empty:
        return _blocked_allocation(
            candidate_id=candidate_id,
            assets=assets,
            selected_signal_date=selected_signal_date,
            generated_at_utc=generated_at,
            lookback_days=lookback_days,
            paper_notional_usd=paper_notional_usd,
            max_asset_weight=max_asset_weight,
            btc_max_weight=btc_max_weight,
            assets_loaded=list(series_by_asset),
            missing_assets=missing_assets,
            blocking_reason="no_common_price_dates",
        )

    returns = prices.pct_change().dropna()
    rows_available = len(returns)
    latest_common_date = prices.index.max()
    if rows_available < lookback_days:
        return _blocked_allocation(
            candidate_id=candidate_id,
            assets=assets,
            selected_signal_date=selected_signal_date,
            generated_at_utc=generated_at,
            lookback_days=lookback_days,
            paper_notional_usd=paper_notional_usd,
            max_asset_weight=max_asset_weight,
            btc_max_weight=btc_max_weight,
            assets_loaded=list(series_by_asset),
            missing_assets=missing_assets,
            latest_common_date=latest_common_date,
            rows_available=rows_available,
            blocking_reason="insufficient_lookback_rows",
        )

    lookback_returns = returns.tail(lookback_days)
    volatility = lookback_returns.std(ddof=0)
    if volatility.isna().any() or (volatility <= 0).any():
        return _blocked_allocation(
            candidate_id=candidate_id,
            assets=assets,
            selected_signal_date=selected_signal_date,
            generated_at_utc=generated_at,
            lookback_days=lookback_days,
            paper_notional_usd=paper_notional_usd,
            max_asset_weight=max_asset_weight,
            btc_max_weight=btc_max_weight,
            assets_loaded=list(series_by_asset),
            missing_assets=missing_assets,
            latest_common_date=latest_common_date,
            rows_available=rows_available,
            blocking_reason="invalid_realised_volatility",
        )

    inverse_vol = 1.0 / volatility
    raw_weights = inverse_vol / inverse_vol.sum()
    caps = {
        asset: min(max_asset_weight, btc_max_weight) if asset == "BTC-USD" else max_asset_weight
        for asset in raw_weights.index
    }
    capped_weights, cap_binding_assets, cap_failure = _apply_caps(raw_weights, caps)
    if cap_failure:
        return _blocked_allocation(
            candidate_id=candidate_id,
            assets=assets,
            selected_signal_date=selected_signal_date,
            generated_at_utc=generated_at,
            lookback_days=lookback_days,
            paper_notional_usd=paper_notional_usd,
            max_asset_weight=max_asset_weight,
            btc_max_weight=btc_max_weight,
            assets_loaded=list(series_by_asset),
            missing_assets=missing_assets,
            latest_common_date=latest_common_date,
            rows_available=rows_available,
            blocking_reason=cap_failure,
        )

    rows = []
    for asset in assets:
        final_weight = float(capped_weights.get(asset, 0.0))
        rows.append(
            {
                "generated_at_utc": generated_at,
                "selected_signal_date": selected_signal_date or latest_common_date.strftime("%Y-%m-%d"),
                "canonical_candidate_id": candidate_id,
                "asset": asset,
                "target_weight": round(final_weight, 10),
                "target_notional_usd": round(paper_notional_usd * final_weight, 2),
                "lookback_days": lookback_days,
                "realised_volatility": round(float(volatility.get(asset, np.nan)), 10),
                "raw_inverse_vol_weight": round(float(raw_weights.get(asset, np.nan)), 10),
                "post_cap_weight": round(final_weight, 10),
                "final_weight": round(final_weight, 10),
                "allocation_status": "dynamic_allocation_resolved",
                "allocation_source": "phase20b_inverse_vol_dynamic_allocation",
                "paper_preview_allowed": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "candidate_caveats": "BTC weekend/gap risk; BTC allocation caveat"
                if asset == "BTC-USD" or "BTC-USD" in assets
                else "",
            }
        )
    weights_sum = round(float(capped_weights.sum()), 10)
    btc_weight = round(float(capped_weights.get("BTC-USD", 0.0)), 10)
    diagnostics = pd.DataFrame(
        [
            {
                "canonical_candidate_id": candidate_id,
                "latest_common_date": latest_common_date.strftime("%Y-%m-%d"),
                "lookback_days": lookback_days,
                "rows_available": rows_available,
                "assets_requested": ",".join(assets),
                "assets_loaded": ",".join(series_by_asset),
                "missing_assets": ",".join(missing_assets),
                "weights_sum": weights_sum,
                "max_asset_weight": max_asset_weight,
                "btc_max_weight": btc_max_weight,
                "btc_weight": btc_weight,
                "cap_binding_assets": ",".join(cap_binding_assets),
                "allocation_status": "dynamic_allocation_resolved",
                "blocking_reason": "",
                "warnings": "BTC persistent caveat: weekend/gap risk"
                if "BTC-USD" in assets
                else "",
            }
        ]
    )
    return pd.DataFrame(rows), diagnostics


def _blocked_allocation(
    *,
    candidate_id: str,
    assets: list[str],
    selected_signal_date: str,
    generated_at_utc: str,
    lookback_days: int,
    paper_notional_usd: float,
    max_asset_weight: float,
    btc_max_weight: float,
    assets_loaded: list[str],
    missing_assets: list[str],
    blocking_reason: str,
    latest_common_date: pd.Timestamp | None = None,
    rows_available: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = [
        {
            "generated_at_utc": generated_at_utc,
            "selected_signal_date": selected_signal_date,
            "canonical_candidate_id": candidate_id,
            "asset": asset,
            "target_weight": pd.NA,
            "target_notional_usd": pd.NA,
            "lookback_days": lookback_days,
            "realised_volatility": pd.NA,
            "raw_inverse_vol_weight": pd.NA,
            "post_cap_weight": pd.NA,
            "final_weight": pd.NA,
            "allocation_status": "dynamic_allocation_blocked",
            "allocation_source": "phase20b_inverse_vol_dynamic_allocation",
            "paper_preview_allowed": False,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "candidate_caveats": "BTC weekend/gap risk; BTC allocation caveat"
            if asset == "BTC-USD" or "BTC-USD" in assets
            else "",
        }
        for asset in assets
    ]
    latest_common_text = (
        latest_common_date.strftime("%Y-%m-%d")
        if latest_common_date is not None and pd.notna(latest_common_date)
        else ""
    )
    diagnostics = pd.DataFrame(
        [
            {
                "canonical_candidate_id": candidate_id,
                "latest_common_date": latest_common_text,
                "lookback_days": lookback_days,
                "rows_available": rows_available,
                "assets_requested": ",".join(assets),
                "assets_loaded": ",".join(assets_loaded),
                "missing_assets": ",".join(missing_assets),
                "weights_sum": pd.NA,
                "max_asset_weight": max_asset_weight,
                "btc_max_weight": btc_max_weight,
                "btc_weight": pd.NA,
                "cap_binding_assets": "",
                "allocation_status": "dynamic_allocation_blocked",
                "blocking_reason": blocking_reason,
                "warnings": "",
            }
        ]
    )
    return pd.DataFrame(rows), diagnostics


def save_phase20b_finalist_dynamic_allocation(
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
        reports_path / "paper_trading" / "finalist_tracking",
    )
    dashboard_dir = _resolve_path(
        section.get("dashboard_dir"),
        reports_path / "paper_trading" / "dashboard",
    )
    fresh_processed_dir = _resolve_path(
        section.get("source_fresh_processed_dir"),
        Path("data/fresh/processed"),
    )
    tear_sheet_path = _resolve_path(
        section.get("source_daily_execution_tear_sheet"),
        DEFAULT_TEAR_SHEET,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    tear_values = _tear_sheet_values(_read_csv(tear_sheet_path))
    selected_signal_date = tear_values.get("selected_signal_date", "")
    paper_notional_usd = float(section.get("paper_notional_usd", 10000))
    generated_at = _generated_at()
    candidate_configs = section.get("inverse_vol_candidates", {}) or {}

    allocation_frames: list[pd.DataFrame] = []
    diagnostic_frames: list[pd.DataFrame] = []
    for candidate_id, candidate_config in candidate_configs.items():
        allocations, diagnostics = compute_inverse_vol_allocation(
            data_dir=fresh_processed_dir,
            candidate_id=str(candidate_id),
            candidate_config=candidate_config or {},
            selected_signal_date=selected_signal_date,
            paper_notional_usd=paper_notional_usd,
            generated_at_utc=generated_at,
        )
        allocation_frames.append(allocations)
        diagnostic_frames.append(diagnostics)

    allocations = (
        pd.concat(allocation_frames, ignore_index=True)
        if allocation_frames
        else pd.DataFrame()
    )
    diagnostics = (
        pd.concat(diagnostic_frames, ignore_index=True)
        if diagnostic_frames
        else pd.DataFrame()
    )
    allocation_path = output_dir / "finalist_dynamic_allocations.csv"
    diagnostics_path = output_dir / "finalist_dynamic_allocation_diagnostics.csv"
    _write_csv(allocations, allocation_path)
    _write_csv(diagnostics, diagnostics_path)

    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    safety_flags_clear = not any(
        [live_trading_allowed, real_money_allowed, broker_api_integration_allowed]
    )
    resolved = bool(
        not diagnostics.empty
        and diagnostics["allocation_status"].astype(str).eq("dynamic_allocation_resolved").all()
    )
    reports_written = allocation_path.exists() and diagnostics_path.exists()
    gates = pd.DataFrame(
        [
            {
                "gate_id": "dynamic_allocation_file_written",
                "passed": allocation_path.exists() and not allocations.empty,
            },
            {
                "gate_id": "dynamic_allocation_diagnostics_written",
                "passed": diagnostics_path.exists() and not diagnostics.empty,
            },
            {
                "gate_id": "candidate_resolved_or_fail_closed",
                "passed": not diagnostics.empty
                and diagnostics["allocation_status"]
                .astype(str)
                .isin(["dynamic_allocation_resolved", "dynamic_allocation_blocked"])
                .all(),
            },
            {"gate_id": "live_trading_disabled", "passed": not live_trading_allowed},
            {"gate_id": "real_money_disabled", "passed": not real_money_allowed},
            {
                "gate_id": "broker_api_integration_disabled",
                "passed": not broker_api_integration_allowed,
            },
            {"gate_id": "no_safety_flags_true", "passed": safety_flags_clear},
        ]
    )
    gates["result"] = np.where(gates["passed"], "Passed", "Failed")
    all_gates_passed = bool(gates["passed"].all())
    if all_gates_passed and resolved:
        decision = "finalist_dynamic_allocation_completed_manual_preview_only"
    elif reports_written and all_gates_passed:
        decision = "finalist_dynamic_allocation_written_but_candidate_blocked"
    else:
        decision = "finalist_dynamic_allocation_failed_closed"
    failed_gates = ";".join(gates.loc[~gates["passed"], "gate_id"].astype(str).tolist())
    blocking_reasons = (
        ";".join(diagnostics["blocking_reason"].dropna().astype(str).loc[lambda s: s != ""])
        if not diagnostics.empty and "blocking_reason" in diagnostics.columns
        else ""
    )

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 20B",
                "phase20b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "selected_signal_date": selected_signal_date,
                "candidate_count": len(candidate_configs),
                "resolved_candidate_count": int(
                    diagnostics["allocation_status"].astype(str).eq(
                        "dynamic_allocation_resolved"
                    ).sum()
                )
                if not diagnostics.empty
                else 0,
                "blocked_candidate_count": int(
                    diagnostics["allocation_status"].astype(str).eq(
                        "dynamic_allocation_blocked"
                    ).sum()
                )
                if not diagnostics.empty
                else 0,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "failure_reason": failed_gates,
                "blocking_reasons": blocking_reasons,
                "generated_at_utc": generated_at,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 20B",
                "diagnostic": "Dynamic inverse-vol finalist allocation extraction",
                "phase20b_decision": decision,
                "all_gates_passed": all_gates_passed,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "notes": "Manual paper-preview allocation source only. No order placement.",
                "failure_reason": failed_gates,
            }
        ]
    )
    dashboard = summary[
        [
            "phase",
            "phase20b_decision",
            "all_gates_passed",
            "selected_signal_date",
            "candidate_count",
            "resolved_candidate_count",
            "blocked_candidate_count",
            "blocking_reasons",
        ]
    ].copy()

    _write_csv(summary, output_dir / "phase20b_summary.csv")
    _write_csv(gates, output_dir / "phase20b_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase20b_conclusion.csv")
    _write_csv(dashboard, dashboard_dir / "finalist_dynamic_allocation_status.csv")

    outputs = {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "finalist_dynamic_allocations": allocations,
        "finalist_dynamic_allocation_diagnostics": diagnostics,
        "finalist_dynamic_allocation_status": dashboard,
    }
    print("Wrote Phase 20B finalist dynamic allocation reports.")
    return outputs
