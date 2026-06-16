from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

PRICE_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]
PRICE_VALUE_COLUMNS = ["open", "high", "low", "close", "adj_close"]

RAW_COLUMN_MAP = {
    "Date": "date",
    "Datetime": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
    "Stock splits": "splits",
}


@dataclass(frozen=True)
class PriceValidationResult:
    normalised: pd.DataFrame
    completed: pd.DataFrame
    warnings: list[str]
    audit: dict[str, Any]


def _normalise_columns(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(column[0]) for column in frame.columns]
    frame = frame.rename(columns={key: value for key, value in RAW_COLUMN_MAP.items() if key in frame.columns})
    frame.columns = [str(column).strip().lower().replace(" ", "_") for column in frame.columns]
    if "adj_close" not in frame.columns and "adj_close_" in frame.columns:
        frame = frame.rename(columns={"adj_close_": "adj_close"})
    return frame


def normalise_price_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = _normalise_columns(raw)
    if "date" not in frame.columns and raw.index.name is not None:
        frame = frame.reset_index()
        frame = _normalise_columns(frame)
    missing = [column for column in PRICE_COLUMNS if column not in frame.columns]
    for column in missing:
        frame[column] = np.nan
    output = frame[PRICE_COLUMNS].copy()
    output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.tz_localize(None)
    for column in PRICE_VALUE_COLUMNS + ["volume"]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output


def corporate_action_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = _normalise_columns(raw)
    if "date" not in frame.columns and raw.index.name is not None:
        frame = frame.reset_index()
        frame = _normalise_columns(frame)
    if "date" not in frame.columns:
        return pd.DataFrame(columns=["date", "dividends", "splits"])
    if "dividends" not in frame.columns:
        frame["dividends"] = np.nan
    if "splits" not in frame.columns:
        frame["splits"] = np.nan
    actions = frame[["date", "dividends", "splits"]].copy()
    actions["date"] = pd.to_datetime(actions["date"], errors="coerce").dt.tz_localize(None)
    actions["dividends"] = pd.to_numeric(actions["dividends"], errors="coerce")
    actions["splits"] = pd.to_numeric(actions["splits"], errors="coerce")
    return actions


def longest_true_streak(values: pd.Series) -> int:
    longest = 0
    current = 0
    for value in values.fillna(False).astype(bool):
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _completed_history(frame: pd.DataFrame, retrieved_at_utc: str) -> tuple[pd.DataFrame, bool, bool]:
    if frame.empty:
        return frame.copy(), False, False
    working = frame.copy()
    required_complete = working[PRICE_COLUMNS].isna().any(axis=1)
    trailing_incomplete = bool(required_complete.iloc[-1])
    retrieved_date = pd.Timestamp(retrieved_at_utc).tz_convert(None).date()
    last_date = pd.Timestamp(working["date"].iloc[-1]).date()
    active_session = last_date >= retrieved_date
    if trailing_incomplete or active_session:
        return working.iloc[:-1].copy(), trailing_incomplete, active_session
    return working, trailing_incomplete, active_session


def completed_history(frame: pd.DataFrame, retrieved_at_utc: str) -> pd.DataFrame:
    completed, _, _ = _completed_history(frame, retrieved_at_utc)
    return completed


def validate_price_frame(
    *,
    raw: pd.DataFrame,
    instrument_id: str,
    retrieved_at_utc: str,
    stale_price_threshold_days: int,
    minimum_history_observations: int,
) -> PriceValidationResult:
    normalised = normalise_price_frame(raw)
    warnings: list[str] = []
    duplicate_dates = bool(normalised["date"].duplicated().any())
    duplicate_date_count = int(normalised["date"].duplicated().sum())
    out_of_order_dates = bool(not normalised["date"].dropna().is_monotonic_increasing)
    normalised_sorted = normalised.sort_values("date").reset_index(drop=True)
    completed, trailing_incomplete, active_session = _completed_history(
        normalised_sorted,
        retrieved_at_utc,
    )
    incomplete_rows = normalised_sorted[PRICE_COLUMNS].isna().any(axis=1)
    interior_incomplete = bool(incomplete_rows.iloc[:-1].any()) if len(incomplete_rows) > 1 else False

    non_positive_prices = bool(
        completed[PRICE_VALUE_COLUMNS].le(0).any().any()
    ) if not completed.empty else False
    negative_volume = bool(completed["volume"].lt(0).any()) if "volume" in completed else False
    zero_volume = completed["volume"].eq(0) if "volume" in completed else pd.Series(dtype=bool)
    stale_close = completed["close"].eq(completed["close"].shift(1)) if "close" in completed else pd.Series(dtype=bool)

    missing_raw_open = bool(completed["open"].isna().any()) if "open" in completed else True
    missing_adjusted_close = bool(completed["adj_close"].isna().any()) if "adj_close" in completed else True
    valid_raw_open = completed.loc[completed["open"].notna() & completed["open"].gt(0), "date"]
    valid_adjusted_close = completed.loc[
        completed["adj_close"].notna() & completed["adj_close"].gt(0),
        "date",
    ]
    row_count = int(len(completed))
    first_observation = completed["date"].min() if row_count else pd.NaT
    last_observation = completed["date"].max() if row_count else pd.NaT
    large_ratio_changes = 0
    if row_count and completed["close"].gt(0).all() and completed["adj_close"].gt(0).all():
        ratio = completed["adj_close"] / completed["close"]
        large_ratio_changes = int(ratio.pct_change().abs().gt(0.2).sum())

    for condition, warning in [
        (duplicate_dates, "duplicate_dates"),
        (out_of_order_dates, "out_of_order_dates"),
        (interior_incomplete, "missing_interior_ohlcv"),
        (trailing_incomplete, "missing_trailing_incomplete_data"),
        (active_session, "final_row_excluded_as_incomplete_active_session"),
        (non_positive_prices, "non_positive_prices"),
        (negative_volume, "negative_volume"),
        (missing_raw_open, "unavailable_raw_open"),
        (missing_adjusted_close, "unavailable_adjusted_close"),
        (row_count < minimum_history_observations, "insufficient_history"),
        (large_ratio_changes > 0, "large_raw_adjusted_ratio_changes"),
    ]:
        if condition:
            warnings.append(warning)

    audit = {
        "instrument_id": instrument_id,
        "row_count": row_count,
        "first_observation_date": first_observation.date().isoformat() if pd.notna(first_observation) else "",
        "last_observation_date": last_observation.date().isoformat() if pd.notna(last_observation) else "",
        "duplicate_dates": duplicate_dates,
        "duplicate_date_count": duplicate_date_count,
        "out_of_order_dates": out_of_order_dates,
        "missing_interior_data": interior_incomplete,
        "missing_interior_row_status": "missing_interior_ohlcv" if interior_incomplete else "none",
        "trailing_incomplete_rows": trailing_incomplete,
        "provider_final_date": normalised_sorted["date"].max().date().isoformat()
        if normalised_sorted["date"].notna().any()
        else "",
        "final_row_incomplete_active_session": active_session,
        "final_row_excluded_from_completed_history": bool(trailing_incomplete or active_session),
        "non_positive_prices": non_positive_prices,
        "negative_volume": negative_volume,
        "zero_volume_day_count": int(zero_volume.sum()) if not zero_volume.empty else 0,
        "longest_zero_volume_streak": longest_true_streak(zero_volume),
        "stale_close_day_count": int(stale_close.sum()) if not stale_close.empty else 0,
        "longest_stale_close_streak": longest_true_streak(stale_close),
        "stale_price_threshold_days": stale_price_threshold_days,
        "stale_threshold_exceeded": longest_true_streak(stale_close) >= stale_price_threshold_days,
        "large_raw_adjusted_ratio_change_count": large_ratio_changes,
        "unavailable_raw_open": missing_raw_open,
        "unavailable_adjusted_close": missing_adjusted_close,
        "first_valid_raw_open_date": valid_raw_open.min().date().isoformat()
        if not valid_raw_open.empty
        else "",
        "first_valid_adjusted_close_date": valid_adjusted_close.min().date().isoformat()
        if not valid_adjusted_close.empty
        else "",
        "warnings": ";".join(warnings),
        "validation_status": "warning" if warnings else "passed",
    }
    return PriceValidationResult(
        normalised=normalised_sorted,
        completed=completed.reset_index(drop=True),
        warnings=warnings,
        audit=audit,
    )


def corporate_action_audit(raw: pd.DataFrame, instrument_id: str) -> dict[str, Any]:
    actions = corporate_action_frame(raw)
    capability_available = not actions.empty and {"dividends", "splits"}.issubset(actions.columns)
    dividends = actions.loc[actions["dividends"].fillna(0.0).ne(0.0)] if capability_available else pd.DataFrame()
    splits = actions.loc[actions["splits"].fillna(0.0).ne(0.0)] if capability_available else pd.DataFrame()
    warnings = []
    if not capability_available:
        warnings.append("source_capability_unavailable")
    elif dividends.empty and splits.empty:
        warnings.append("no_events_returned")
    return {
        "instrument_id": instrument_id,
        "dividend_data_available": capability_available,
        "split_data_available": capability_available,
        "first_dividend_date": dividends["date"].min().date().isoformat() if not dividends.empty else "",
        "last_dividend_date": dividends["date"].max().date().isoformat() if not dividends.empty else "",
        "dividend_event_count": int(len(dividends)),
        "first_split_date": splits["date"].min().date().isoformat() if not splits.empty else "",
        "last_split_date": splits["date"].max().date().isoformat() if not splits.empty else "",
        "split_event_count": int(len(splits)),
        "action_warnings": ";".join(warnings),
    }


def liquidity_audit(completed: pd.DataFrame, instrument_id: str) -> dict[str, Any]:
    if completed.empty:
        return {
            "instrument_id": instrument_id,
            "median_close": np.nan,
            "median_daily_volume": np.nan,
            "median_daily_dollar_volume": np.nan,
            "minimum_daily_dollar_volume": np.nan,
            "zero_volume_day_count": 0,
            "longest_zero_volume_streak": 0,
            "stale_close_day_count": 0,
            "longest_stale_close_streak": 0,
        }
    dollar_volume = completed["close"] * completed["volume"]
    zero_volume = completed["volume"].eq(0)
    stale_close = completed["close"].eq(completed["close"].shift(1))
    return {
        "instrument_id": instrument_id,
        "median_close": float(completed["close"].median()),
        "median_daily_volume": float(completed["volume"].median()),
        "median_daily_dollar_volume": float(dollar_volume.median()),
        "minimum_daily_dollar_volume": float(dollar_volume.min()),
        "zero_volume_day_count": int(zero_volume.sum()),
        "longest_zero_volume_streak": longest_true_streak(zero_volume),
        "stale_close_day_count": int(stale_close.sum()),
        "longest_stale_close_streak": longest_true_streak(stale_close),
    }
