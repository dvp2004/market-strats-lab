from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Any, Callable

import numpy as np
import pandas as pd

from market_strats.analysis.frozen_cost_aware_portfolio import (
    DEFAULT_PHASE23I_CONFIG,
    DEFAULT_PHASE23I_SHADOW_CONFIG,
    RIDGE_MODEL,
    _portfolio_spec,
    build_phase23i_targets_for_signal,
)
from market_strats.analysis.interpretable_stock_ranker import (
    _prepare_joined_panel,
    _preprocess_train_test,
    _ridge_fit,
)
from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
    DEFAULT_PHASE23F_CONFIG,
    build_pilot_panel_and_targets,
)
from market_strats.analysis.pilot_individual_equity_input_bootstrap import (
    _default_yfinance_download,
)


PHASE23J_SECTION = "phase23j_post_endpoint_individual_equity_extension"
NONCANONICAL_WARNING = (
    "POST-ENDPOINT NONCANONICAL PILOT SHADOW DATA - RESEARCH ONLY - "
    "NOT INVESTABLE PERFORMANCE"
)

DEFAULT_PHASE23J_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23j_post_endpoint_individual_equity_extension"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23j_post_endpoint_individual_equity_extension_status.csv"
    ),
    "historical_input_dir": "data/individual_equity_pilot",
    "extension_input_dir": "data/individual_equity_post_endpoint",
    "combined_input_dir": "data/individual_equity_post_endpoint/combined",
    "source_phase23f_dir": (
        "reports/individual_equity_decision_system/"
        "phase23f_pilot_feature_calculation"
    ),
    "source_phase23g_dir": (
        "reports/individual_equity_decision_system/"
        "phase23g_interpretable_stock_ranker"
    ),
    "source_phase23i_dir": (
        "reports/individual_equity_decision_system/"
        "phase23i_frozen_cost_aware_portfolio"
    ),
    "canonical_research_endpoint": "2026-05-01",
    "overlap_start_date": "2026-03-30",
    "minimum_overlap_rows": 21,
    "as_of_date": "",
    "minimum_post_endpoint_rows": 5,
    "minimum_security_count": 12,
    "retry_attempts": 3,
    "retry_delay_seconds": 2.0,
    "inter_symbol_delay_seconds": 0.25,
    "overlap_price_relative_tolerance": 1e-8,
    "overlap_volume_absolute_tolerance": 0.0,
    "allow_network_download": True,
    "refresh_existing_extension": True,
    "starting_cash": 100000.0,
    "portfolio_id": "ridge_top5_equal_weight",
    "paper_only": True,
    "research_pilot_only": True,
    "membership_canonical": False,
    "market_data_canonical": False,
    "generalization_claim_allowed": False,
    "investable_performance_claim_allowed": False,
    "automated_broker_paper_trading_allowed": False,
    "paper_trading_allowed": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}

DownloadFn = Callable[[str, str, str], pd.DataFrame]

CURRENT_FEATURE_COLUMNS = [
    "panel_row_id",
    "decision_timestamp_utc",
    "signal_date",
    "execution_date",
    "universe_id",
    "permanent_security_id",
    "permanent_company_id",
    "ticker",
    "ticker_asof",
    "sector_asof",
    "industry_asof",
    "membership_known_timestamp_utc",
    "membership_effective_date",
    "membership_active",
    "model_cutoff_timestamp_utc",
    "technical_available_timestamp_utc",
    "fundamental_available_timestamp_utc",
    "sentiment_available_timestamp_utc",
    "macro_available_timestamp_utc",
    "cross_asset_available_timestamp_utc",
    "market_stress_available_timestamp_utc",
    "liquidity_available_timestamp_utc",
    "event_available_timestamp_utc",
    "feature_max_available_timestamp_utc",
    "feature_set_version",
    "source_snapshot_id",
    "split_label",
    "training_eligible",
    *CORE_FEATURE_COLUMNS,
    "feature_missing_count",
    "oldest_feature_age_days",
]

CURRENT_RANKING_COLUMNS = [
    "decision_timestamp_utc",
    "signal_date",
    "panel_row_id",
    "universe_id",
    "permanent_security_id",
    "ticker",
    "sector_asof",
    "model_version",
    "training_cutoff",
    "purge_boundary_signal_date",
    "training_rows",
    "training_decision_dates",
    "predicted_20d_excess_return_or_ranking_score",
    "predicted_rank",
    "prediction_is_prospective",
    "prediction_is_out_of_sample",
    "noncanonical_pilot_warning",
    "reference_price",
    "reference_price_date",
]

CURRENT_TARGET_COLUMNS = [
    "selected_signal_date",
    "planned_execution_date",
    "expected_execution_date",
    "observed_execution_date",
    "portfolio_id",
    "ticker",
    "target_weight",
    "target_notional",
    "reference_price",
    "reference_price_date",
    "execution_open_price",
    "execution_price_available",
    "estimated_target_shares",
    "signal_estimated_target_shares",
    "execution_target_shares",
    "execution_open_status",
    "target_status",
    "paper_order_allowed",
    "order_blocking_reason",
    "noncanonical_label",
]

PROSPECTIVE_COEFFICIENT_COLUMNS = [
    "feature_name",
    "coefficient",
    "ridge_alpha",
    "training_rows",
    "training_decision_dates",
    "model_fit_timestamp_utc",
    "preprocessing_metadata",
]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_PHASE23J_CONFIG, config.get(PHASE23J_SECTION, {}))


def _resolve_reports_path(
    *, configured_path: str | Path, reports_dir: str | Path
) -> Path:
    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def _resolve_project_path(
    *, configured_path: str | Path, reports_dir: str | Path
) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return Path(reports_dir).parent / path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_of_date(section: dict[str, Any]) -> pd.Timestamp:
    configured = str(section.get("as_of_date", "")).strip()
    if configured:
        return pd.Timestamp(configured).normalize()
    return pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()


def _observed_us_market_holiday(year: int, month: int, day: int) -> pd.Timestamp:
    date = pd.Timestamp(year=year, month=month, day=day)
    if date.weekday() == 5:
        return date - pd.Timedelta(days=1)
    if date.weekday() == 6:
        return date + pd.Timedelta(days=1)
    return date


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (weekday - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> pd.Timestamp:
    last = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    offset = (last.weekday() - weekday) % 7
    return last - pd.Timedelta(days=offset)


def _us_equity_market_holidays(year: int) -> set[pd.Timestamp]:
    return {
        _observed_us_market_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        pd.Timestamp(year=year, month=4, day=3)
        if year == 2026
        else pd.NaT,
        _last_weekday(year, 5, 0),
        _observed_us_market_holiday(year, 6, 19),
        _observed_us_market_holiday(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_us_market_holiday(year, 12, 25),
    } - {pd.NaT}


def next_us_equity_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    candidate = pd.Timestamp(date).normalize() + pd.Timedelta(days=1)
    while (
        candidate.weekday() >= 5
        or candidate.normalize() in _us_equity_market_holidays(candidate.year)
    ):
        candidate += pd.Timedelta(days=1)
    return candidate.normalize()


def count_us_equity_trading_sessions(
    start_date: str | pd.Timestamp, end_date: str | pd.Timestamp
) -> int:
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if pd.isna(start) or pd.isna(end) or start > end:
        return 0
    count = 0
    candidate = start
    while candidate <= end:
        if (
            candidate.weekday() < 5
            and candidate.normalize() not in _us_equity_market_holidays(candidate.year)
        ):
            count += 1
        candidate += pd.Timedelta(days=1)
    return count


def _end_exclusive(as_of_date: pd.Timestamp) -> str:
    return (as_of_date + pd.Timedelta(days=1)).date().isoformat()


def _normalise_local_price(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce").dt.normalize()
    numeric = [
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "dividends",
        "stock_splits",
    ]
    for column in numeric:
        if column not in working.columns:
            working[column] = 0.0 if column in {"dividends", "stock_splits"} else np.nan
        working[column] = pd.to_numeric(working[column], errors="coerce")
    return (
        working.sort_values("date")
        .dropna(subset=["date"])
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def _flatten_phase23j_yfinance_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame.copy()
    if frame.columns.nlevels != 2:
        raise ValueError(f"Unsupported yfinance column levels: {frame.columns.nlevels}")
    known = {
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume",
        "Dividends",
        "Stock Splits",
    }
    first = [str(value) for value in frame.columns.get_level_values(0)]
    second = [str(value) for value in frame.columns.get_level_values(1)]
    working = frame.copy()
    if set(first) & known:
        working.columns = frame.columns.get_level_values(0)
        return working
    if set(second) & known:
        working.columns = frame.columns.get_level_values(1)
        return working
    raise ValueError("Unable to identify yfinance field level")


def _normalise_phase23j_download_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError("Downloaded price frame is empty")
    working = _flatten_phase23j_yfinance_columns(frame)
    if (
        "Date" not in working.columns
        and "date" not in working.columns
        and isinstance(working.index, pd.DatetimeIndex)
    ):
        working = working.reset_index()
        first_column = working.columns[0]
        if first_column not in {"Date", "Datetime", "date"}:
            working = working.rename(columns={first_column: "date"})
    rename = {
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
        "Dividends": "dividends",
        "Stock Splits": "stock_splits",
    }
    working = working.rename(columns=rename)
    required = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    missing = sorted(set(required) - set(working.columns))
    if missing:
        raise ValueError("Downloaded frame missing columns: " + ";".join(missing))
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    for column in ["dividends", "stock_splits"]:
        if column not in working.columns:
            working[column] = 0.0
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0.0)
    working["date"] = pd.to_datetime(working["date"], errors="coerce", utc=True)
    working["date"] = working["date"].dt.tz_convert(None).dt.normalize()
    working = working.sort_values("date").drop_duplicates("date", keep="last")

    full_bar_required = ["open", "high", "low", "close", "adj_close", "volume"]
    incomplete = working[full_bar_required].isna().any(axis=1)
    if incomplete.any():
        complete_positions = [
            position for position, value in enumerate(incomplete) if not value
        ]
        last_complete_position = max(complete_positions) if complete_positions else -1
        interior_mask = pd.Series(
            [
                bool(value) and position < last_complete_position
                for position, value in enumerate(incomplete)
            ],
            index=working.index,
        )
        if interior_mask.any():
            bad_dates = (
                working.loc[interior_mask, "date"].dt.strftime("%Y-%m-%d").tolist()
            )
            raise ValueError(
                "Downloaded frame has incomplete non-trailing rows: "
                + ";".join(bad_dates)
            )
    return working[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "dividends",
            "stock_splits",
        ]
    ].reset_index(drop=True)


def _complete_research_bar_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    working = _normalise_local_price(frame)
    required = ["open", "high", "low", "close", "adj_close", "volume"]
    complete = working[required].notna().all(axis=1)
    positive = (working[["open", "high", "low", "close", "adj_close"]] > 0).all(axis=1)
    volume_ok = working["volume"].ge(0)
    ohlc_ok = (
        working["high"].ge(working[["open", "close", "low"]].max(axis=1))
        & working["low"].le(working[["open", "close", "high"]].min(axis=1))
    )
    return working.loc[complete & positive & volume_ok & ohlc_ok].copy()


def _finite_positive(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(numeric) and numeric > 0)


def _valid_execution_open(row: pd.Series) -> tuple[bool, float, str]:
    open_price = pd.to_numeric(row.get("open", np.nan), errors="coerce")
    high = pd.to_numeric(row.get("high", np.nan), errors="coerce")
    low = pd.to_numeric(row.get("low", np.nan), errors="coerce")
    volume = pd.to_numeric(row.get("volume", np.nan), errors="coerce")
    if not (_finite_positive(open_price) and _finite_positive(high) and _finite_positive(low)):
        return False, np.nan, "execution_open_ohl_missing_or_nonpositive"
    if float(high) < float(low):
        return False, np.nan, "execution_open_high_below_low"
    if not (float(low) <= float(open_price) <= float(high)):
        return False, np.nan, "execution_open_outside_ohl_range"
    if pd.notna(volume) and (not np.isfinite(float(volume)) or float(volume) < 0):
        return False, np.nan, "execution_open_volume_invalid"
    return True, float(open_price), "execution_open_available"


def _execution_open_for_date(
    frame: pd.DataFrame, expected_execution_date: pd.Timestamp
) -> tuple[bool, float, str]:
    if frame.empty or pd.isna(expected_execution_date):
        return False, np.nan, "execution_open_price_pending"
    working = _normalise_local_price(frame)
    rows = working.loc[
        pd.to_datetime(working["date"], errors="coerce").eq(expected_execution_date)
    ]
    if rows.empty:
        return False, np.nan, "execution_open_price_pending"
    return _valid_execution_open(rows.iloc[0])


def validate_extension_against_history(
    *,
    historical: pd.DataFrame,
    extension: pd.DataFrame,
    endpoint: pd.Timestamp,
    minimum_overlap_rows: int = 21,
    minimum_post_endpoint_rows: int,
    price_relative_tolerance: float,
    volume_absolute_tolerance: float,
) -> pd.DataFrame:
    history = _normalise_local_price(historical)
    extra = _normalise_local_price(extension)
    rows: list[dict[str, Any]] = []
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    missing = sorted(required - set(extra.columns))
    rows.append(_gate("required_columns_present", not missing, "missing=" + ";".join(missing)))
    if missing:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    overlap = history.loc[history["date"].le(endpoint)].merge(
        extra.loc[extra["date"].le(endpoint)],
        on="date",
        how="inner",
        suffixes=("_historical", "_extension"),
    )
    rows.append(_gate("overlap_rows_present", not overlap.empty, f"rows={len(overlap)}"))
    rows.append(
        _gate(
            "minimum_overlap_rows",
            len(overlap) >= int(minimum_overlap_rows),
            f"rows={len(overlap)};required={minimum_overlap_rows}",
        )
    )
    overlap_ok = not overlap.empty
    mismatch_details: list[str] = []
    if not overlap.empty:
        for column in ["open", "high", "low", "close"]:
            left = pd.to_numeric(overlap[f"{column}_historical"], errors="coerce")
            right = pd.to_numeric(overlap[f"{column}_extension"], errors="coerce")
            close = np.isclose(
                left,
                right,
                rtol=float(price_relative_tolerance),
                atol=1e-10,
                equal_nan=False,
            )
            if not bool(close.all()):
                overlap_ok = False
                mismatch_details.append(f"{column}:{int((~close).sum())}")
        left_volume = pd.to_numeric(overlap["volume_historical"], errors="coerce")
        right_volume = pd.to_numeric(overlap["volume_extension"], errors="coerce")
        volume_ok = (left_volume - right_volume).abs().le(
            float(volume_absolute_tolerance)
        )
        if not bool(volume_ok.all()):
            overlap_ok = False
            mismatch_details.append(f"volume:{int((~volume_ok).sum())}")
    rows.append(
        _gate(
            "historical_overlap_matches",
            overlap_ok,
            "mismatches=" + ";".join(mismatch_details),
        )
    )
    post = extra.loc[extra["date"].gt(endpoint)].copy()
    rows.append(
        _gate(
            "minimum_post_endpoint_rows",
            len(post) >= int(minimum_post_endpoint_rows),
            f"rows={len(post)};required={minimum_post_endpoint_rows}",
        )
    )
    rows.append(
        _gate(
            "post_endpoint_dates_strictly_after_endpoint",
            not post.empty and bool(post["date"].gt(endpoint).all()),
            f"endpoint={endpoint.date().isoformat()}",
        )
    )
    complete_bar_available = post[["close", "adj_close"]].notna().all(axis=1)
    incomplete_close_bar = ~complete_bar_available
    complete_bar_valid = (
        complete_bar_available
        & post[["open", "high", "low", "close", "adj_close"]].notna().all(axis=1)
        & (post[["open", "high", "low", "close", "adj_close"]] > 0).all(axis=1)
        & post["volume"].notna()
        & post["volume"].ge(0)
        & post["high"].ge(post[["open", "close", "low"]].max(axis=1))
        & post["low"].le(post[["open", "close", "high"]].min(axis=1))
    )
    partial_execution_open_valid = (
        post[["open", "high", "low"]].notna().all(axis=1)
        & (post[["open", "high", "low"]] > 0).all(axis=1)
        & post["high"].ge(post["low"])
        & post["open"].between(post["low"], post["high"])
        & (post["volume"].isna() | post["volume"].ge(0))
    )
    rows.append(
        _gate(
            "post_endpoint_ohlc_valid",
            not post.empty and bool((complete_bar_valid | incomplete_close_bar).all()),
            f"rows={len(post)};partial_execution_open_rows={int((~complete_bar_valid & partial_execution_open_valid).sum())}",
        )
    )
    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def merge_historical_and_extension(
    *, historical: pd.DataFrame, extension: pd.DataFrame, endpoint: pd.Timestamp
) -> pd.DataFrame:
    history = _normalise_local_price(historical)
    extra = _normalise_local_price(extension)
    combined = pd.concat(
        [history.loc[history["date"].le(endpoint)], extra.loc[extra["date"].gt(endpoint)]],
        ignore_index=True,
    )
    return combined.sort_values("date").drop_duplicates("date", keep="first").reset_index(drop=True)


def _download_with_retries(
    *,
    ticker: str,
    start: str,
    end_exclusive: str,
    download_fn: DownloadFn,
    attempts: int,
    retry_delay_seconds: float,
) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, max(int(attempts), 1) + 1):
        try:
            return _normalise_phase23j_download_frame(
                download_fn(ticker, start, end_exclusive)
            )
        except Exception as exc:  # pragma: no cover - exercised by injected tests
            last_error = exc
            if attempt < max(int(attempts), 1):
                sleep(float(retry_delay_seconds))
    raise RuntimeError(f"Download failed for {ticker}: {last_error}")


def _frozen_model_status(
    *, source_phase23i_dir: Path
) -> tuple[pd.DataFrame, bool, str]:
    freeze = _read_csv(source_phase23i_dir / "phase23i_model_freeze.csv")
    hashes = _read_csv(source_phase23i_dir / "phase23i_model_freeze_hashes.csv")
    expected = str(freeze.iloc[0].get("phase23i_freeze_hash", "")) if not freeze.empty else ""
    observed = expected
    if (
        not hashes.empty
        and "hash_name" in hashes.columns
        and hashes["hash_name"].astype(str).eq("phase23i_freeze_hash").any()
    ):
        observed = str(
            hashes.loc[
                hashes["hash_name"].astype(str).eq("phase23i_freeze_hash"),
                "hash_value",
            ].iloc[0]
        )
    matches = bool(expected and expected == observed)
    return freeze, matches, observed


def fit_frozen_model_and_score(
    *,
    historical_panel: pd.DataFrame,
    historical_targets: pd.DataFrame,
    prospective_panel: pd.DataFrame,
    freeze: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if historical_panel.empty or historical_targets.empty or prospective_panel.empty or freeze.empty:
        return pd.DataFrame(), pd.DataFrame()
    freeze_row = freeze.iloc[0]
    features = [
        item.strip()
        for item in str(freeze_row.get("ordered_feature_list", "")).split(";")
        if item.strip()
    ]
    if not features:
        features = [feature for feature in CORE_FEATURE_COLUMNS if feature in prospective_panel.columns]
    if any(feature not in prospective_panel.columns for feature in features):
        return pd.DataFrame(), pd.DataFrame()
    primary_target = str(
        freeze_row.get("primary_target", "forward_20d_excess_return_vs_universe")
    )
    joined = _prepare_joined_panel(
        historical_panel,
        historical_targets,
        primary_target=primary_target,
    )
    if joined.empty:
        return pd.DataFrame(), pd.DataFrame()
    test = prospective_panel.copy()
    test["decision_timestamp_utc"] = pd.to_datetime(
        test["decision_timestamp_utc"], utc=True
    )
    latest_timestamp = test["decision_timestamp_utc"].max()
    latest_signal = pd.to_datetime(test["signal_date"]).max().normalize()
    purge_days = int(freeze_row.get("purge_window_trading_days", 63))
    purge_boundary = latest_signal - pd.offsets.BDay(purge_days)
    joined["signal_date"] = pd.to_datetime(joined["signal_date"])
    joined["target_available_timestamp_utc"] = pd.to_datetime(
        joined["target_available_timestamp_utc"], utc=True
    )
    train = joined.loc[
        joined["training_eligible"].map(_bool_value)
        & joined["signal_date"].le(purge_boundary)
        & joined["target_available_timestamp_utc"].le(latest_timestamp)
    ].copy()
    if train.empty:
        return pd.DataFrame(), pd.DataFrame()
    x_train, y_train, x_test, preprocessing = _preprocess_train_test(
        train,
        test,
        features,
    )
    alpha = float(freeze_row.get("ridge_alpha", 1.0))
    intercept, coefficients = _ridge_fit(x_train, y_train, alpha)
    scores = intercept + x_test @ coefficients
    ranking = test[
        [
            "decision_timestamp_utc",
            "signal_date",
            "panel_row_id",
            "universe_id",
            "permanent_security_id",
            "ticker",
            "sector_asof",
        ]
    ].copy()
    ranking["model_version"] = str(freeze_row.get("model_identifier", RIDGE_MODEL))
    ranking["training_cutoff"] = latest_timestamp.isoformat()
    ranking["purge_boundary_signal_date"] = purge_boundary.date().isoformat()
    ranking["training_rows"] = len(train)
    ranking["training_decision_dates"] = int(
        train["decision_timestamp_utc"].nunique()
    )
    ranking["predicted_20d_excess_return_or_ranking_score"] = scores
    ranking["predicted_rank"] = pd.Series(scores, index=ranking.index).rank(
        ascending=False, method="first"
    ).astype(int)
    ranking["prediction_is_prospective"] = True
    ranking["prediction_is_out_of_sample"] = True
    ranking["noncanonical_pilot_warning"] = NONCANONICAL_WARNING
    coefficient_rows = [
        {
            "feature_name": "__intercept__",
            "coefficient": intercept,
            "ridge_alpha": alpha,
            "training_rows": len(train),
            "training_decision_dates": int(train["decision_timestamp_utc"].nunique()),
            "model_fit_timestamp_utc": latest_timestamp.isoformat(),
            "preprocessing_metadata": "{}",
        }
    ]
    for feature, coefficient in zip(features, coefficients, strict=False):
        coefficient_rows.append(
            {
                "feature_name": feature,
                "coefficient": float(coefficient),
                "ridge_alpha": alpha,
                "training_rows": len(train),
                "training_decision_dates": int(
                    train["decision_timestamp_utc"].nunique()
                ),
                "model_fit_timestamp_utc": latest_timestamp.isoformat(),
                "preprocessing_metadata": str(preprocessing.get(feature, {})),
            }
        )
    return ranking.sort_values("predicted_rank").reset_index(drop=True), pd.DataFrame(
        coefficient_rows
    )


def _blocked_outputs(
    *,
    output_dir: Path,
    dashboard_path: Path,
    decision: str,
    reasons: list[str],
    gate_rows: list[dict[str, Any]] | None = None,
) -> dict[str, pd.DataFrame]:
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23J",
                "phase23j_decision": decision,
                "phase_execution_gates_passed": False,
                "post_endpoint_data_ready": False,
                "prospective_features_generated": False,
                "prospective_ranking_generated": False,
                "shadow_activation_ready": False,
                "blocking_reasons": ";".join(reasons),
                "research_pilot_only": True,
                "membership_canonical": False,
                "market_data_canonical": False,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        ]
    )
    gates = pd.DataFrame(
        (gate_rows or []) + [_gate("phase23j_blocked", False, ";".join(reasons))]
    )
    gates["all_gates_passed"] = False
    conclusion = pd.DataFrame(
        [
            {
                "phase23j_decision": decision,
                "verdict": "Phase23J blocked: " + ";".join(reasons),
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    current_features = pd.DataFrame(columns=CURRENT_FEATURE_COLUMNS)
    current_ranking = pd.DataFrame(columns=CURRENT_RANKING_COLUMNS)
    current_target = pd.DataFrame(columns=CURRENT_TARGET_COLUMNS)
    coefficients = pd.DataFrame(columns=PROSPECTIVE_COEFFICIENT_COLUMNS)
    download_status = pd.DataFrame(columns=["ticker", "role", "status", "error"])
    source_inventory = pd.DataFrame(columns=["ticker", "role", "source_path"])
    extension_validation = pd.DataFrame(
        columns=["ticker", "role", "gate", "passed", "result", "detail", "all_gates_passed"]
    )
    data_freshness = pd.DataFrame(
        columns=[
            "canonical_research_endpoint",
            "as_of_date",
            "latest_common_signal_date",
            "validated_security_count",
            "benchmark_ready",
            "canonical_historical_files_unchanged",
            "post_endpoint_data_ready",
            "data_namespace",
            "source_metadata_retained",
            "checksums_retained",
        ]
    )
    constraint_audit = pd.DataFrame(columns=["signal_date", "ticker", "action", "reason"])
    _write_csv(summary, output_dir / "phase23j_summary.csv")
    _write_csv(gates, output_dir / "phase23j_gate_report.csv")
    _write_csv(conclusion, output_dir / "phase23j_conclusion.csv")
    _write_csv(download_status, output_dir / "phase23j_download_status.csv")
    _write_csv(source_inventory, output_dir / "phase23j_source_inventory.csv")
    _write_csv(extension_validation, output_dir / "phase23j_extension_validation.csv")
    _write_csv(data_freshness, output_dir / "phase23j_data_freshness.csv")
    _write_csv(current_features, output_dir / "phase23j_current_features.csv")
    _write_csv(current_features, output_dir / "phase23j_prospective_feature_panel.csv")
    _write_csv(current_ranking, output_dir / "phase23j_current_ranking.csv")
    _write_csv(current_target, output_dir / "phase23j_current_target_portfolio.csv")
    _write_csv(coefficients, output_dir / "phase23j_prospective_model_coefficients.csv")
    _write_csv(constraint_audit, output_dir / "phase23j_constraint_audit.csv")
    _write_csv(summary.assign(dashboard_status="phase23j_status_written"), dashboard_path)
    return {
        "summary": summary,
        "gate_report": gates,
        "conclusion": conclusion,
        "download_status": download_status,
        "source_inventory": source_inventory,
        "extension_validation": extension_validation,
        "data_freshness": data_freshness,
        "current_features": current_features,
        "prospective_feature_panel": current_features,
        "current_ranking": current_ranking,
        "current_target_portfolio": current_target,
        "prospective_model_coefficients": coefficients,
        "constraint_audit": constraint_audit,
    }


def save_phase23j_post_endpoint_individual_equity_extension(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    download_fn: DownloadFn | None = None,
) -> dict[str, pd.DataFrame]:
    section = _phase_config(config)
    if not section["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    reports_path = Path(reports_dir)
    output_dir = _resolve_reports_path(
        configured_path=section["output_dir"], reports_dir=reports_path
    )
    dashboard_path = _resolve_reports_path(
        configured_path=section["dashboard_status_path"], reports_dir=reports_path
    )
    historical_dir = _resolve_project_path(
        configured_path=section["historical_input_dir"], reports_dir=reports_path
    )
    extension_dir = _resolve_project_path(
        configured_path=section["extension_input_dir"], reports_dir=reports_path
    )
    combined_dir = _resolve_project_path(
        configured_path=section["combined_input_dir"], reports_dir=reports_path
    )
    phase23f_dir = _resolve_reports_path(
        configured_path=section["source_phase23f_dir"], reports_dir=reports_path
    )
    phase23i_dir = _resolve_reports_path(
        configured_path=section["source_phase23i_dir"], reports_dir=reports_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    extension_dir.mkdir(parents=True, exist_ok=True)
    combined_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = historical_dir / "pilot_membership_manifest.csv"
    manifest = _read_csv(manifest_path)
    historical_panel = _read_csv(phase23f_dir / "phase23f_pilot_feature_panel.csv")
    historical_targets = _read_csv(phase23f_dir / "phase23f_pilot_targets.csv")
    freeze, freeze_matches, observed_freeze_hash = _frozen_model_status(
        source_phase23i_dir=phase23i_dir
    )
    required_inputs = {
        "membership_manifest": manifest_path.exists() and not manifest.empty,
        "historical_panel": not historical_panel.empty,
        "historical_targets": not historical_targets.empty,
        "model_freeze": not freeze.empty and freeze_matches,
    }
    missing = [name for name, ready in required_inputs.items() if not ready]
    if missing:
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23j_blocked_required_source_missing",
            reasons=missing,
        )

    endpoint = pd.Timestamp(section["canonical_research_endpoint"]).normalize()
    as_of = _as_of_date(section)
    if as_of <= endpoint:
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23j_blocked_as_of_not_after_endpoint",
            reasons=["as_of_date_not_after_canonical_endpoint"],
        )
    available_overlap_sessions = count_us_equity_trading_sessions(
        section["overlap_start_date"],
        endpoint,
    )
    required_overlap_sessions = int(section["minimum_overlap_rows"])
    if available_overlap_sessions < required_overlap_sessions:
        detail = (
            "overlap_configuration_insufficient;"
            f"available_overlap_sessions={available_overlap_sessions};"
            f"required_overlap_sessions={required_overlap_sessions}"
        )
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23j_blocked_overlap_configuration_insufficient",
            reasons=[detail],
            gate_rows=[
                _gate(
                    "overlap_configuration_sufficient",
                    False,
                    detail,
                )
            ],
        )
    configured_download = download_fn or _default_yfinance_download
    if not section["allow_network_download"] and download_fn is None:
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23j_blocked_network_download_disabled",
            reasons=["network_download_disabled"],
        )

    symbols: list[tuple[str, str, Path]] = [("SPY", "benchmark", historical_dir / "benchmark_SPY.csv")]
    for row in manifest.itertuples(index=False):
        symbols.append((str(row.ticker), "pilot_security", historical_dir / str(row.price_file)))

    historical_hashes_before = {
        str(path): _file_sha256(path) for _ticker, _role, path in symbols if path.exists()
    }
    status_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    validation_frames: list[pd.DataFrame] = []
    combined_prices_by_security: dict[str, pd.DataFrame] = {}
    benchmark_combined = pd.DataFrame()
    failures: list[str] = []
    for index, (ticker, role, historical_path) in enumerate(symbols):
        extension_filename = "benchmark_SPY.csv" if role == "benchmark" else f"{ticker}.csv"
        extension_path = extension_dir / extension_filename
        combined_path = combined_dir / extension_filename
        try:
            historical = _read_csv(historical_path)
            if historical.empty:
                raise ValueError("historical_file_missing_or_empty")
            if extension_path.exists() and not section["refresh_existing_extension"]:
                extension = _normalise_local_price(_read_csv(extension_path))
                status = "reused_existing_extension"
            else:
                extension = _download_with_retries(
                    ticker=ticker,
                    start=str(section["overlap_start_date"]),
                    end_exclusive=_end_exclusive(as_of),
                    download_fn=configured_download,
                    attempts=int(section["retry_attempts"]),
                    retry_delay_seconds=float(section["retry_delay_seconds"]),
                )
                _write_csv(extension, extension_path)
                status = "downloaded_and_validated"
            validation = validate_extension_against_history(
                historical=historical,
                extension=extension,
                endpoint=endpoint,
                minimum_overlap_rows=int(section["minimum_overlap_rows"]),
                minimum_post_endpoint_rows=int(section["minimum_post_endpoint_rows"]),
                price_relative_tolerance=float(section["overlap_price_relative_tolerance"]),
                volume_absolute_tolerance=float(section["overlap_volume_absolute_tolerance"]),
            )
            validation.insert(0, "ticker", ticker)
            validation.insert(1, "role", role)
            validation_frames.append(validation)
            passed = bool(validation["passed"].all())
            if not passed:
                raise ValueError("extension_validation_failed")
            combined = merge_historical_and_extension(
                historical=historical,
                extension=extension,
                endpoint=endpoint,
            )
            _write_csv(combined, combined_path)
            if role == "benchmark":
                benchmark_combined = combined
            else:
                security_row = manifest.loc[manifest["ticker"].astype(str).eq(ticker)].iloc[0]
                combined_prices_by_security[str(security_row["permanent_security_id"])] = combined
            post_rows = combined.loc[pd.to_datetime(combined["date"]).gt(endpoint)]
            status_rows.append(
                {
                    "ticker": ticker,
                    "role": role,
                    "status": status,
                    "validation_passed": True,
                    "post_endpoint_rows": len(post_rows),
                    "first_post_endpoint_date": post_rows["date"].min(),
                    "latest_post_endpoint_date": post_rows["date"].max(),
                    "error": "",
                }
            )
            inventory_rows.append(
                {
                    "ticker": ticker,
                    "role": role,
                    "historical_path": str(historical_path),
                    "historical_sha256": historical_hashes_before[str(historical_path)],
                    "extension_path": str(extension_path),
                    "extension_sha256": _file_sha256(extension_path),
                    "combined_path": str(combined_path),
                    "combined_sha256": _file_sha256(combined_path),
                    "post_endpoint_rows": len(post_rows),
                    "latest_date": combined["date"].max(),
                    "source_provider": "Yahoo Finance via yfinance",
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "canonical_history_unchanged": True,
                    "research_pilot_only": True,
                }
            )
        except Exception as exc:
            failures.append(ticker)
            status_rows.append(
                {
                    "ticker": ticker,
                    "role": role,
                    "status": "failed",
                    "validation_passed": False,
                    "post_endpoint_rows": 0,
                    "first_post_endpoint_date": "",
                    "latest_post_endpoint_date": "",
                    "error": str(exc),
                }
            )
        if index < len(symbols) - 1:
            sleep(float(section["inter_symbol_delay_seconds"]))

    historical_hashes_after = {
        str(path): _file_sha256(path) for _ticker, _role, path in symbols if path.exists()
    }
    canonical_unchanged = historical_hashes_before == historical_hashes_after
    download_status = pd.DataFrame(status_rows)
    inventory = pd.DataFrame(inventory_rows)
    extension_validation = (
        pd.concat(validation_frames, ignore_index=True)
        if validation_frames
        else pd.DataFrame()
    )
    validated_security_count = int(
        download_status.loc[
            download_status["role"].eq("pilot_security")
            & download_status["validation_passed"].map(_bool_value)
        ].shape[0]
    )
    all_inputs_ready = (
        not failures
        and canonical_unchanged
        and validated_security_count >= int(section["minimum_security_count"])
        and not benchmark_combined.empty
    )
    if not all_inputs_ready:
        reasons = []
        if failures:
            reasons.append("failed_symbols:" + ";".join(failures))
        if not canonical_unchanged:
            reasons.append("canonical_historical_files_changed")
        if validated_security_count < int(section["minimum_security_count"]):
            reasons.append("insufficient_validated_securities")
        _write_csv(download_status, output_dir / "phase23j_download_status.csv")
        _write_csv(inventory, output_dir / "phase23j_source_inventory.csv")
        _write_csv(extension_validation, output_dir / "phase23j_extension_validation.csv")
        return _blocked_outputs(
            output_dir=output_dir,
            dashboard_path=dashboard_path,
            decision="phase23j_post_endpoint_extension_incomplete",
            reasons=reasons,
        )

    prospective_config = _deep_merge(
        DEFAULT_PHASE23F_CONFIG,
        {
            "pilot_start_date": (endpoint + pd.Timedelta(days=1)).date().isoformat(),
            "pilot_end_date": as_of.date().isoformat(),
            "minimum_securities": int(section["minimum_security_count"]),
            "minimum_price_rows": 320,
            "allow_model_training": False,
            "allow_backtest": False,
            "allow_paper_orders": False,
        },
    )
    research_prices_by_security = {
        security_id: _complete_research_bar_rows(frame)
        for security_id, frame in combined_prices_by_security.items()
    }
    research_benchmark = _complete_research_bar_rows(benchmark_combined)
    prospective_panel, _prospective_targets, _source_inventory = build_pilot_panel_and_targets(
        manifest=manifest,
        price_frames=research_prices_by_security,
        benchmark=research_benchmark,
        phase_config=prospective_config,
    )
    if not prospective_panel.empty:
        signal_dates = pd.to_datetime(prospective_panel["signal_date"])
        completed_weekly = prospective_panel.loc[signal_dates.dt.weekday.eq(4)].copy()
        if not completed_weekly.empty:
            prospective_panel = completed_weekly
            signal_dates = pd.to_datetime(prospective_panel["signal_date"])
        latest_signal = signal_dates.max()
        prospective_panel = prospective_panel.loc[
            pd.to_datetime(prospective_panel["signal_date"]).eq(latest_signal)
        ].copy()
    ranking, prospective_coefficients = fit_frozen_model_and_score(
        historical_panel=historical_panel,
        historical_targets=historical_targets,
        prospective_panel=prospective_panel,
        freeze=freeze,
    )
    phase23i_config = _deep_merge(
        DEFAULT_PHASE23I_CONFIG,
        config.get("phase23i_frozen_cost_aware_portfolio", {}),
    )
    shadow_config = _deep_merge(
        DEFAULT_PHASE23I_SHADOW_CONFIG,
        config.get("phase23i_prospective_shadow_runner", {}),
    )
    target_weights: dict[str, float] = {}
    constraint_rows: list[dict[str, Any]] = []
    if not ranking.empty:
        target_weights, constraint_rows = build_phase23i_targets_for_signal(
            predictions=ranking,
            membership=manifest,
            signal_date=pd.to_datetime(ranking["signal_date"]).max(),
            spec=_portfolio_spec(str(section["portfolio_id"])),
            config=phase23i_config,
        )
    selected_signal_timestamp = (
        pd.to_datetime(ranking["signal_date"]).max().normalize()
        if not ranking.empty
        else pd.NaT
    )
    reference_prices: dict[str, float] = {}
    reference_price_dates: dict[str, str] = {}
    for row in manifest.itertuples(index=False):
        frame = combined_prices_by_security.get(str(row.permanent_security_id), pd.DataFrame())
        if frame.empty or pd.isna(selected_signal_timestamp):
            continue
        working = _complete_research_bar_rows(frame)
        signal_rows = working.loc[
            pd.to_datetime(working["date"], errors="coerce").eq(
                selected_signal_timestamp
            )
        ]
        if signal_rows.empty:
            continue
        signal_row = signal_rows.iloc[0]
        reference = pd.to_numeric(signal_row.get("close", np.nan), errors="coerce")
        if pd.notna(reference) and float(reference) > 0:
            reference_prices[str(row.ticker)] = float(reference)
            reference_price_dates[str(row.ticker)] = (
                selected_signal_timestamp.date().isoformat()
            )
    if not ranking.empty:
        ranking["reference_price"] = ranking["ticker"].map(reference_prices)
        ranking["reference_price_date"] = ranking["ticker"].map(reference_price_dates)
    expected_execution_date = pd.NaT
    observed_execution_date = pd.NaT
    if pd.notna(selected_signal_timestamp):
        expected_execution_date = next_us_equity_trading_day(selected_signal_timestamp)
    execution_open_prices: dict[str, float] = {}
    execution_open_available: dict[str, bool] = {}
    execution_open_status: dict[str, str] = {}
    for ticker in sorted(target_weights):
        security_row = manifest.loc[manifest["ticker"].astype(str).eq(ticker)]
        if security_row.empty:
            execution_open_prices[ticker] = np.nan
            execution_open_available[ticker] = False
            execution_open_status[ticker] = "execution_security_not_found"
            continue
        security_id = str(security_row.iloc[0]["permanent_security_id"])
        security_frame = combined_prices_by_security.get(security_id, pd.DataFrame())
        available, open_price, status = _execution_open_for_date(
            security_frame, expected_execution_date
        )
        execution_open_prices[ticker] = open_price
        execution_open_available[ticker] = available
        execution_open_status[ticker] = status
    all_execution_opens_ready = bool(target_weights) and all(
        execution_open_available.get(ticker, False) for ticker in target_weights
    )
    if all_execution_opens_ready:
        observed_execution_date = expected_execution_date
    target_rows = []
    for ticker, weight in sorted(target_weights.items()):
        reference = reference_prices.get(ticker, np.nan)
        target_notional = float(shadow_config["starting_cash"]) * float(weight)
        execution_open = execution_open_prices.get(ticker, np.nan)
        fill_ready = bool(execution_open_available.get(ticker, False))
        signal_estimated_target_shares = (
            int(np.floor(target_notional / reference))
            if pd.notna(reference) and reference > 0
            else 0
        )
        execution_target_shares = (
            int(np.floor(target_notional / execution_open))
            if fill_ready and pd.notna(execution_open) and execution_open > 0
            else 0
        )
        target_rows.append(
            {
                "selected_signal_date": ranking["signal_date"].iloc[0] if not ranking.empty else "",
                "planned_execution_date": ""
                if pd.isna(expected_execution_date)
                else expected_execution_date.date().isoformat(),
                "expected_execution_date": ""
                if pd.isna(expected_execution_date)
                else expected_execution_date.date().isoformat(),
                "observed_execution_date": ""
                if pd.isna(observed_execution_date)
                else observed_execution_date.date().isoformat(),
                "portfolio_id": str(section["portfolio_id"]),
                "ticker": ticker,
                "target_weight": float(weight),
                "target_notional": target_notional,
                "reference_price": reference,
                "reference_price_date": reference_price_dates.get(ticker, ""),
                "execution_open_price": execution_open,
                "execution_price_available": fill_ready,
                "estimated_target_shares": signal_estimated_target_shares,
                "signal_estimated_target_shares": signal_estimated_target_shares,
                "execution_target_shares": execution_target_shares,
                "execution_open_status": execution_open_status.get(
                    ticker, "execution_open_price_pending"
                ),
                "target_status": "prospective_frozen_model_target",
                "paper_order_allowed": all_execution_opens_ready,
                "order_blocking_reason": ""
                if all_execution_opens_ready
                else "execution_open_price_pending",
                "noncanonical_label": NONCANONICAL_WARNING,
            }
        )
    current_target = pd.DataFrame(target_rows)
    data_freshness = pd.DataFrame(
        [
            {
                "canonical_research_endpoint": endpoint.date().isoformat(),
                "as_of_date": as_of.date().isoformat(),
                "latest_common_signal_date": ranking["signal_date"].iloc[0]
                if not ranking.empty
                else "",
                "validated_security_count": validated_security_count,
                "benchmark_ready": not benchmark_combined.empty,
                "canonical_historical_files_unchanged": canonical_unchanged,
                "post_endpoint_data_ready": all_inputs_ready,
                "data_namespace": "post_endpoint_prospective_shadow",
                "source_metadata_retained": True,
                "checksums_retained": True,
            }
        ]
    )
    prospective_features_ready = (
        not prospective_panel.empty
        and prospective_panel["training_eligible"].map(_bool_value).all()
    )
    ranking_ready = (
        not ranking.empty
        and ranking["prediction_is_prospective"].map(_bool_value).all()
        and freeze_matches
    )
    target_ready = not current_target.empty and bool(
        current_target["reference_price"].notna().all()
    )
    simulated_fill_ready = bool(
        target_ready
        and "execution_price_available" in current_target.columns
        and current_target["execution_price_available"].map(_bool_value).all()
    )
    gates = pd.DataFrame(
        [
            _gate("canonical_historical_files_unchanged", canonical_unchanged, "hash comparison"),
            _gate("all_required_extensions_valid", all_inputs_ready, f"validated={validated_security_count}"),
            _gate("post_endpoint_feature_panel_ready", prospective_features_ready, f"rows={len(prospective_panel)}"),
            _gate("frozen_model_hash_verified", freeze_matches, observed_freeze_hash),
            _gate("prospective_ranking_generated", ranking_ready, f"rows={len(ranking)}"),
            _gate("target_portfolio_generated", target_ready, f"rows={len(current_target)}"),
            _gate("research_only_safety_boundary", True, NONCANONICAL_WARNING),
        ]
    )
    gates["all_gates_passed"] = bool(gates["passed"].all())
    proposal_ready = bool(gates["passed"].all())
    ready = proposal_ready and simulated_fill_ready
    decision = (
        "phase23j_post_endpoint_shadow_activation_ready_manual_research_only"
        if ready
        else "phase23j_post_endpoint_shadow_proposal_ready_execution_pending"
        if proposal_ready
        else "phase23j_post_endpoint_extension_completed_shadow_blocked"
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23J",
                "phase23j_decision": decision,
                "phase_execution_gates_passed": ready,
                "all_gates_passed": ready,
                "post_endpoint_data_ready": all_inputs_ready,
                "prospective_features_generated": prospective_features_ready,
                "prospective_ranking_generated": ranking_ready,
                "prospective_target_generated": target_ready,
                "manual_shadow_proposal_ready": proposal_ready,
                "simulated_fill_ready": simulated_fill_ready,
                "planned_execution_date": ""
                if pd.isna(expected_execution_date)
                else expected_execution_date.date().isoformat(),
                "expected_execution_date": ""
                if pd.isna(expected_execution_date)
                else expected_execution_date.date().isoformat(),
                "observed_execution_date": ""
                if pd.isna(observed_execution_date)
                else observed_execution_date.date().isoformat(),
                "shadow_activation_ready": ready,
                "validated_security_count": validated_security_count,
                "prospective_feature_rows": len(prospective_panel),
                "prospective_ranking_rows": len(ranking),
                "selected_signal_date": ranking["signal_date"].iloc[0]
                if not ranking.empty
                else "",
                "model_version": RIDGE_MODEL,
                "phase23i_freeze_hash": observed_freeze_hash,
                "canonical_research_endpoint": endpoint.date().isoformat(),
                "post_endpoint_as_of_date": as_of.date().isoformat(),
                "membership_canonical": False,
                "market_data_canonical": False,
                "research_pilot_only": True,
                "generalization_claim_allowed": False,
                "investable_performance_claim_allowed": False,
                "paper_trading_allowed": False,
                "automated_broker_paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase23j_decision": decision,
                "verdict": (
                    "Post-endpoint data, frozen-model features, ranking, and target portfolio "
                    "are ready for explicit manual research-only shadow entry."
                    if ready
                    else "Phase23J completed with one or more shadow activation blockers."
                ),
                "cannot_prove": (
                    "investable performance, canonical universe generalization, live readiness, "
                    "or real-money suitability"
                ),
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    constraint_audit = pd.DataFrame(constraint_rows)
    outputs = {
        "summary": summary,
        "gate_report": gates,
        "download_status": download_status,
        "source_inventory": inventory,
        "extension_validation": extension_validation,
        "data_freshness": data_freshness,
        "current_features": prospective_panel,
        "prospective_feature_panel": prospective_panel,
        "prospective_model_coefficients": prospective_coefficients,
        "current_ranking": ranking,
        "current_target_portfolio": current_target,
        "constraint_audit": constraint_audit,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        _write_csv(frame, output_dir / f"phase23j_{name}.csv")
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23j_post_endpoint_extension_status_written"
    dashboard["notes"] = NONCANONICAL_WARNING
    _write_csv(dashboard, dashboard_path)
    markdown = "\n".join(
        [
            "# Phase 23J - Post-Endpoint Individual-Equity Extension",
            "",
            "NO LIVE TRADING",
            "NO REAL MONEY",
            "NO BROKER/API",
            "NO STRATEGY PROMOTION",
            "",
            NONCANONICAL_WARNING,
            "",
            f"Decision: `{decision}`",
            f"Selected signal date: `{summary.iloc[0]['selected_signal_date']}`",
            "",
            "Canonical historical files are hash-checked and never overwritten.",
        ]
    )
    (output_dir / "phase23j_post_endpoint_individual_equity_extension.md").write_text(
        markdown + "\n", encoding="utf-8"
    )
    print("Wrote Phase 23J post-endpoint individual-equity extension reports.")
    return outputs | {"dashboard": dashboard}
