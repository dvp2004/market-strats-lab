from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PHASE23F_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23f_pilot_feature_calculation"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23f_pilot_feature_calculation_status.csv"
    ),
    "input_dir": "data/individual_equity_pilot",
    "membership_manifest_path": (
        "data/individual_equity_pilot/pilot_membership_manifest.csv"
    ),
    "benchmark_path": "data/individual_equity_pilot/benchmark_SPY.csv",
    "pilot_start_date": "2023-01-03",
    "pilot_end_date": "2026-05-01",
    "pilot_universe_id": "SP500_PILOT_NONCANONICAL",
    "decision_weekday": "FRIDAY",
    "decision_time_utc": "22:00:00",
    "market_data_available_time_utc": "21:05:00",
    "minimum_securities": 3,
    "minimum_price_rows": 320,
    "minimum_average_dollar_volume": 1_000_000.0,
    "feature_set_version": "phase23f_technical_pilot_v1",
    "target_set_version": "phase23f_targets_v1",
    "phase_decision_ready": "phase23f_pilot_panel_built_validation_pending",
    "phase_decision_pending": "phase23f_feature_engine_ready_local_inputs_pending",
    "allow_data_download": False,
    "allow_local_input_ingestion": True,
    "allow_feature_calculation": True,
    "allow_target_calculation": True,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}

MEMBERSHIP_REQUIRED_COLUMNS = [
    "universe_id",
    "permanent_security_id",
    "permanent_company_id",
    "ticker",
    "sector",
    "industry",
    "membership_start_date",
    "membership_end_date",
    "membership_known_timestamp_utc",
    "price_file",
    "canonical_membership",
    "research_pilot_only",
]

PRICE_REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]

CORE_FEATURE_COLUMNS = [
    "momentum_21d",
    "momentum_63d",
    "momentum_252d_skip21d",
    "trend_distance_200d",
    "realized_volatility_21d",
    "volume_surprise_20d",
    "average_dollar_volume_20d",
    "beta_252d",
    "market_breadth_200d",
    "cross_sectional_dispersion_21d",
]

TARGET_HORIZONS = (1, 5, 20, 63)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(
        DEFAULT_PHASE23F_CONFIG,
        config.get("phase23f_pilot_individual_equity_feature_calculation", {}),
    )


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


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


def build_membership_manifest_schema() -> pd.DataFrame:
    rows = [
        ("universe_id", "string", True, "explicit noncanonical pilot universe"),
        ("permanent_security_id", "string", True, "stable share-line identifier"),
        ("permanent_company_id", "string", True, "stable issuer identifier"),
        ("ticker", "string", True, "ticker valid for the pilot interval"),
        ("sector", "string", True, "point-in-time sector label"),
        ("industry", "string", True, "point-in-time industry label"),
        ("membership_start_date", "date", True, "inclusive pilot membership start"),
        ("membership_end_date", "date", False, "exclusive end; blank while active"),
        (
            "membership_known_timestamp_utc",
            "timestamp",
            True,
            "when pilot membership became knowable",
        ),
        ("price_file", "string", True, "CSV or Parquet file under input directory"),
        (
            "canonical_membership",
            "boolean",
            True,
            "must remain false until Phase23B canonical data is approved",
        ),
        (
            "research_pilot_only",
            "boolean",
            True,
            "must be true for this controlled pilot",
        ),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_price_input_schema() -> pd.DataFrame:
    rows = [
        ("date", "date", True, "trading date"),
        ("open", "float", True, "split-aware source open"),
        ("high", "float", True, "split-aware source high"),
        ("low", "float", True, "split-aware source low"),
        ("close", "float", True, "unadjusted close used for liquidity"),
        ("adj_close", "float", True, "total-return-adjusted close used for returns"),
        ("volume", "float", True, "daily share volume"),
        ("dividends", "float", False, "optional explicit cash dividend"),
        ("stock_splits", "float", False, "optional split factor"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_calculated_feature_registry() -> pd.DataFrame:
    rows = [
        ("momentum_21d", "technical", "adj_close/adj_close_lag21-1", 21),
        ("momentum_63d", "technical", "adj_close/adj_close_lag63-1", 63),
        (
            "momentum_252d_skip21d",
            "technical",
            "adj_close_lag21/adj_close_lag252-1",
            252,
        ),
        (
            "trend_distance_200d",
            "technical",
            "adj_close/rolling_mean_200-1",
            200,
        ),
        (
            "realized_volatility_21d",
            "technical",
            "std(daily_total_return,21)*sqrt(252)",
            22,
        ),
        (
            "volume_surprise_20d",
            "technical",
            "volume/rolling_median_volume_20-1",
            20,
        ),
        (
            "average_dollar_volume_20d",
            "liquidity_risk",
            "rolling_mean(close*volume,20)",
            20,
        ),
        (
            "beta_252d",
            "liquidity_risk",
            "rolling_cov(stock_return,benchmark_return)/rolling_var(benchmark_return)",
            253,
        ),
        (
            "market_breadth_200d",
            "market_stress",
            "cross_sectional_share(adj_close>moving_average_200)",
            200,
        ),
        (
            "cross_sectional_dispersion_21d",
            "market_stress",
            "cross_sectional_std(momentum_21d)",
            21,
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=["feature_name", "feature_family", "formula", "minimum_history_rows"],
    )


def build_target_registry() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in TARGET_HORIZONS:
        rows.extend(
            [
                {
                    "target_name": f"forward_{horizon}d_total_return",
                    "horizon_trading_days": horizon,
                    "target_type": "regression",
                    "primary_target": False,
                },
                {
                    "target_name": f"forward_{horizon}d_excess_return_vs_universe",
                    "horizon_trading_days": horizon,
                    "target_type": "regression",
                    "primary_target": horizon == 20,
                },
            ]
        )
    rows.append(
        {
            "target_name": "forward_20d_positive_alpha_probability",
            "horizon_trading_days": 20,
            "target_type": "binary_classification",
            "primary_target": False,
        }
    )
    return pd.DataFrame(rows)


def build_input_readiness_contract() -> pd.DataFrame:
    rows = [
        (
            "I1",
            "local_files_only",
            "Phase23F performs no network download; only explicitly supplied local files are read.",
        ),
        (
            "I2",
            "noncanonical_pilot",
            "Pilot membership must be marked noncanonical and research_pilot_only.",
        ),
        (
            "I3",
            "delisting_aware_source_required",
            "Any future canonical extension must retain removed, failed, and delisted securities.",
        ),
        (
            "I4",
            "adjusted_return_series",
            "adj_close must represent split/dividend-adjusted total-return history.",
        ),
        (
            "I5",
            "immutable_source_snapshot",
            "Input file checksums and paths are preserved in the source inventory.",
        ),
        (
            "I6",
            "no_model_training",
            "Pilot features and targets may be calculated, but no model is trained in Phase23F.",
        ),
    ]
    return pd.DataFrame(rows, columns=["contract_id", "contract", "requirement"])


def build_scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    required_false = {
        "data_download_allowed": phase_config["allow_data_download"],
        "model_training_allowed": phase_config["allow_model_training"],
        "backtest_allowed": phase_config["allow_backtest"],
        "paper_orders_allowed": phase_config["allow_paper_orders"],
        "live_trading_allowed": phase_config["allow_live_trading"],
        "real_money_allowed": phase_config["allow_real_money"],
        "broker_api_integration_allowed": phase_config["allow_broker_api"],
        "promotion_allowed": phase_config["allow_promotion"],
    }
    rows = [
        {
            "control": name,
            "allowed": bool(value),
            "required_state": False,
            "passed": not bool(value),
        }
        for name, value in required_false.items()
    ]
    rows.extend(
        [
            {
                "control": "local_input_ingestion_allowed",
                "allowed": bool(phase_config["allow_local_input_ingestion"]),
                "required_state": True,
                "passed": bool(phase_config["allow_local_input_ingestion"]),
            },
            {
                "control": "feature_calculation_allowed",
                "allowed": bool(phase_config["allow_feature_calculation"]),
                "required_state": True,
                "passed": bool(phase_config["allow_feature_calculation"]),
            },
            {
                "control": "target_calculation_allowed",
                "allowed": bool(phase_config["allow_target_calculation"]),
                "required_state": True,
                "passed": bool(phase_config["allow_target_calculation"]),
            },
        ]
    )
    return pd.DataFrame(rows)


def build_empty_membership_manifest() -> pd.DataFrame:
    return pd.DataFrame(columns=MEMBERSHIP_REQUIRED_COLUMNS)


def build_empty_price_template() -> pd.DataFrame:
    return pd.DataFrame(columns=PRICE_REQUIRED_COLUMNS + ["dividends", "stock_splits"])


def validate_membership_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(MEMBERSHIP_REQUIRED_COLUMNS) - set(manifest.columns))
    rows = [_gate("required_columns_present", not missing, "missing=" + ";".join(missing))]
    if missing:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    working = manifest.copy()
    nonblank_columns = [column for column in MEMBERSHIP_REQUIRED_COLUMNS if column != "membership_end_date"]
    nonblank = bool(
        working[nonblank_columns]
        .fillna("")
        .astype(str)
        .apply(lambda column: column.str.strip().ne(""))
        .all()
        .all()
    )
    rows.append(_gate("required_values_nonblank", nonblank, f"rows={len(working)}"))

    unique_ids = not bool(working["permanent_security_id"].duplicated().any())
    rows.append(_gate("security_ids_unique", unique_ids, f"rows={len(working)}"))

    start = pd.to_datetime(working["membership_start_date"], errors="coerce")
    end = pd.to_datetime(working["membership_end_date"], errors="coerce")
    known = pd.to_datetime(working["membership_known_timestamp_utc"], utc=True, errors="coerce")
    dates_parse = bool(start.notna().all() and known.notna().all())
    rows.append(_gate("membership_dates_parse", dates_parse, f"rows={len(working)}"))
    valid_intervals = bool(((end.isna()) | (end > start)).all()) if dates_parse else False
    rows.append(_gate("membership_intervals_valid", valid_intervals, "end is exclusive"))

    canonical = working["canonical_membership"].fillna(False).astype(bool)
    research_only = working["research_pilot_only"].fillna(False).astype(bool)
    rows.append(
        _gate(
            "pilot_is_noncanonical",
            not bool(canonical.any()),
            "Phase23B acquisition remains pending",
        )
    )
    rows.append(
        _gate(
            "research_pilot_only_acknowledged",
            bool(research_only.all()),
            f"rows={len(working)}",
        )
    )
    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported table format: {path}")


def normalize_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    rename = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Adj_Close": "adj_close",
        "Volume": "volume",
        "Dividends": "dividends",
        "Stock Splits": "stock_splits",
    }
    working = working.rename(columns={key: value for key, value in rename.items() if key in working.columns})
    if "date" not in working.columns and isinstance(working.index, pd.DatetimeIndex):
        working = working.reset_index().rename(columns={working.index.name or "index": "date"})
    if "adj_close" not in working.columns and "close" in working.columns:
        working["adj_close"] = working["close"]
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    working["date"] = pd.to_datetime(working["date"], errors="coerce").dt.normalize()
    working = working.sort_values("date").drop_duplicates("date", keep="last")
    return working.reset_index(drop=True)


def validate_price_frame(
    prices: pd.DataFrame, *, minimum_price_rows: int = 320
) -> pd.DataFrame:
    missing = sorted(set(PRICE_REQUIRED_COLUMNS) - set(prices.columns))
    rows = [_gate("required_columns_present", not missing, "missing=" + ";".join(missing))]
    if missing:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    working = normalize_price_frame(prices)
    rows.append(
        _gate(
            "minimum_history_rows",
            len(working) >= int(minimum_price_rows),
            f"rows={len(working)};required={minimum_price_rows}",
        )
    )
    dates_valid = bool(working["date"].notna().all() and working["date"].is_monotonic_increasing)
    rows.append(_gate("dates_valid_and_sorted", dates_valid, f"rows={len(working)}"))
    positive = bool(
        (working[["open", "high", "low", "close", "adj_close"]] > 0).all().all()
        and (working["volume"] >= 0).all()
    )
    rows.append(_gate("prices_positive_volume_nonnegative", positive, f"rows={len(working)}"))
    ohlc_valid = bool(
        (working["high"] >= working[["open", "close", "low"]].max(axis=1)).all()
        and (working["low"] <= working[["open", "close", "high"]].min(axis=1)).all()
    )
    rows.append(_gate("ohlc_consistent", ohlc_valid, f"rows={len(working)}"))
    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def calculate_security_features(
    prices: pd.DataFrame, *, benchmark: pd.DataFrame | None = None
) -> pd.DataFrame:
    working = normalize_price_frame(prices).set_index("date")
    adjusted = working["adj_close"].astype(float)
    returns = adjusted.pct_change()
    working["daily_total_return"] = returns
    working["momentum_21d"] = adjusted.pct_change(21)
    working["momentum_63d"] = adjusted.pct_change(63)
    working["momentum_252d_skip21d"] = adjusted.shift(21) / adjusted.shift(252) - 1.0
    working["moving_average_200d"] = adjusted.rolling(200, min_periods=200).mean()
    working["trend_distance_200d"] = adjusted / working["moving_average_200d"] - 1.0
    working["realized_volatility_21d"] = returns.rolling(21, min_periods=21).std(ddof=1) * np.sqrt(252.0)
    rolling_volume = working["volume"].rolling(20, min_periods=20).median()
    working["volume_surprise_20d"] = working["volume"] / rolling_volume - 1.0
    working["average_dollar_volume_20d"] = (
        working["close"] * working["volume"]
    ).rolling(20, min_periods=20).mean()

    working["beta_252d"] = np.nan
    if benchmark is not None and not benchmark.empty:
        benchmark_working = normalize_price_frame(benchmark).set_index("date")
        benchmark_return = benchmark_working["adj_close"].pct_change().rename("benchmark_return")
        aligned = pd.concat([returns.rename("stock_return"), benchmark_return], axis=1)
        covariance = aligned["stock_return"].rolling(252, min_periods=252).cov(
            aligned["benchmark_return"]
        )
        variance = aligned["benchmark_return"].rolling(252, min_periods=252).var()
        working["beta_252d"] = covariance / variance.replace(0.0, np.nan)

    return working.reset_index()


def _decision_dates(all_dates: pd.DatetimeIndex, weekday: str) -> pd.DatetimeIndex:
    weekday_map = {
        "MONDAY": 0,
        "TUESDAY": 1,
        "WEDNESDAY": 2,
        "THURSDAY": 3,
        "FRIDAY": 4,
    }
    target = weekday_map.get(str(weekday).upper(), 4)
    dates = pd.DatetimeIndex(sorted(pd.unique(all_dates.dropna())))
    if dates.empty:
        return dates
    frame = pd.DataFrame({"date": dates})
    frame["week"] = frame["date"].dt.to_period("W-FRI")
    selected = frame.groupby("week", observed=True)["date"].max()
    selected = selected[selected.dt.weekday <= target]
    return pd.DatetimeIndex(selected.values)


def _next_trading_date(date: pd.Timestamp, calendar: pd.DatetimeIndex) -> pd.Timestamp | pd.NaT:
    future = calendar[calendar > date]
    return future[0] if len(future) else pd.NaT


def build_pilot_panel_and_targets(
    *,
    manifest: pd.DataFrame,
    price_frames: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    phase_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manifest_report = validate_membership_manifest(manifest)
    if not bool(manifest_report["passed"].all()):
        raise ValueError("Membership manifest failed validation")

    calculated: dict[str, pd.DataFrame] = {}
    inventories: list[dict[str, Any]] = []
    for row in manifest.itertuples(index=False):
        security_id = str(row.permanent_security_id)
        if security_id not in price_frames:
            raise ValueError(f"Missing price frame for {security_id}")
        normalized = normalize_price_frame(price_frames[security_id])
        report = validate_price_frame(
            normalized,
            minimum_price_rows=int(phase_config["minimum_price_rows"]),
        )
        if not bool(report["passed"].all()):
            raise ValueError(f"Price frame failed validation for {security_id}")
        features = calculate_security_features(normalized, benchmark=benchmark)
        calculated[security_id] = features
        inventories.append(
            {
                "permanent_security_id": security_id,
                "ticker": str(row.ticker),
                "price_file": str(row.price_file),
                "price_rows": len(normalized),
                "first_date": normalized["date"].min(),
                "last_date": normalized["date"].max(),
                "validation_passed": True,
            }
        )

    if len(calculated) < int(phase_config["minimum_securities"]):
        raise ValueError("Pilot has fewer securities than minimum_securities")

    all_dates = pd.DatetimeIndex(
        sorted(
            set().union(
                *(set(frame["date"].dropna()) for frame in calculated.values())
            )
        )
    )
    start = pd.Timestamp(phase_config["pilot_start_date"])
    end = pd.Timestamp(phase_config["pilot_end_date"])
    all_dates = all_dates[(all_dates >= start) & (all_dates <= end)]
    decision_dates = _decision_dates(all_dates, str(phase_config["decision_weekday"]))

    long_rows: list[pd.DataFrame] = []
    for row in manifest.itertuples(index=False):
        frame = calculated[str(row.permanent_security_id)].copy()
        frame["permanent_security_id"] = str(row.permanent_security_id)
        frame["permanent_company_id"] = str(row.permanent_company_id)
        frame["ticker_asof"] = str(row.ticker)
        frame["sector_asof"] = str(row.sector)
        frame["industry_asof"] = str(row.industry)
        frame["universe_id"] = str(row.universe_id)
        frame["membership_start_date"] = pd.Timestamp(row.membership_start_date)
        frame["membership_end_date"] = pd.to_datetime(row.membership_end_date, errors="coerce")
        frame["membership_known_timestamp_utc"] = pd.to_datetime(
            row.membership_known_timestamp_utc, utc=True
        )
        long_rows.append(frame)
    daily = pd.concat(long_rows, ignore_index=True)

    daily["above_200d"] = daily["adj_close"] > daily["moving_average_200d"]
    daily["market_breadth_200d"] = daily.groupby("date")["above_200d"].transform("mean")
    daily["cross_sectional_dispersion_21d"] = daily.groupby("date")["momentum_21d"].transform("std")

    panel = daily[daily["date"].isin(decision_dates)].copy()
    panel = panel[(panel["date"] >= start) & (panel["date"] <= end)]
    panel["membership_active"] = (
        (panel["date"] >= panel["membership_start_date"])
        & (panel["membership_end_date"].isna() | (panel["date"] < panel["membership_end_date"]))
    )
    panel = panel[panel["membership_active"]].copy()

    decision_stamp = pd.to_datetime(
        panel["date"].dt.strftime("%Y-%m-%d")
        + "T"
        + str(phase_config["decision_time_utc"])
        + "Z",
        utc=True,
    )
    available_stamp = pd.to_datetime(
        panel["date"].dt.strftime("%Y-%m-%d")
        + "T"
        + str(phase_config["market_data_available_time_utc"])
        + "Z",
        utc=True,
    )
    panel["decision_timestamp_utc"] = decision_stamp
    panel["model_cutoff_timestamp_utc"] = decision_stamp
    panel["technical_available_timestamp_utc"] = available_stamp
    panel["liquidity_available_timestamp_utc"] = available_stamp
    panel["market_stress_available_timestamp_utc"] = available_stamp
    panel["fundamental_available_timestamp_utc"] = pd.NaT
    panel["sentiment_available_timestamp_utc"] = pd.NaT
    panel["macro_available_timestamp_utc"] = pd.NaT
    panel["cross_asset_available_timestamp_utc"] = pd.NaT
    panel["event_available_timestamp_utc"] = pd.NaT
    panel["feature_max_available_timestamp_utc"] = available_stamp
    panel["signal_date"] = panel["date"].dt.date.astype(str)
    calendar = pd.DatetimeIndex(sorted(pd.unique(daily["date"])))
    panel["execution_date"] = panel["date"].map(lambda value: _next_trading_date(value, calendar))
    panel["execution_date"] = pd.to_datetime(panel["execution_date"]).dt.date.astype("string")
    panel["panel_row_id"] = (
        panel["signal_date"].astype(str)
        + "|"
        + panel["universe_id"].astype(str)
        + "|"
        + panel["permanent_security_id"].astype(str)
    )
    panel["membership_effective_date"] = panel["membership_start_date"].dt.date.astype(str)
    panel["feature_set_version"] = str(phase_config["feature_set_version"])
    panel["source_snapshot_id"] = "phase23f_local_pilot_inputs"
    panel["split_label"] = "UNASSIGNED"
    panel["feature_missing_count"] = panel[CORE_FEATURE_COLUMNS].isna().sum(axis=1)
    panel["oldest_feature_age_days"] = 0
    panel["training_eligible"] = (
        panel["membership_active"]
        & panel[CORE_FEATURE_COLUMNS].notna().all(axis=1)
        & (
            panel["average_dollar_volume_20d"]
            >= float(phase_config["minimum_average_dollar_volume"])
        )
    )

    target_rows: list[dict[str, Any]] = []
    feature_lookup = daily.set_index(["permanent_security_id", "date"]).sort_index()
    for row in panel.itertuples(index=False):
        security_id = str(row.permanent_security_id)
        security_daily = feature_lookup.loc[security_id].sort_index()
        dates = security_daily.index
        try:
            location = dates.get_loc(pd.Timestamp(row.date))
        except KeyError:
            continue
        if isinstance(location, slice | np.ndarray):
            continue
        current_price = float(security_daily.iloc[int(location)]["adj_close"])
        for horizon in TARGET_HORIZONS:
            end_location = int(location) + horizon
            if end_location >= len(security_daily):
                continue
            future_row = security_daily.iloc[end_location]
            total_return = float(future_row["adj_close"] / current_price - 1.0)
            target_rows.append(
                {
                    "panel_row_id": row.panel_row_id,
                    "permanent_security_id": security_id,
                    "signal_date": row.signal_date,
                    "target_name": f"forward_{horizon}d_total_return",
                    "target_horizon_trading_days": horizon,
                    "target_value": total_return,
                    "target_period_start_date": str(
                        dates[min(int(location) + 1, len(dates) - 1)].date()
                    ),
                    "target_period_end_date": str(pd.Timestamp(future_row.name).date()),
                    "target_available_timestamp_utc": (
                        pd.Timestamp(future_row.name).tz_localize("UTC")
                        + pd.Timedelta(days=1)
                    ),
                    "target_set_version": str(phase_config["target_set_version"]),
                }
            )
    targets = pd.DataFrame(target_rows)
    if not targets.empty:
        total_mask = targets["target_name"].str.contains("total_return")
        total = targets[total_mask].copy()
        total["universe_mean"] = total.groupby(
            ["signal_date", "target_horizon_trading_days"]
        )["target_value"].transform("mean")
        excess = total.copy()
        excess["target_value"] = excess["target_value"] - excess["universe_mean"]
        excess["target_name"] = excess["target_horizon_trading_days"].map(
            lambda value: f"forward_{int(value)}d_excess_return_vs_universe"
        )
        excess = excess.drop(columns="universe_mean")
        positive = excess[excess["target_horizon_trading_days"].eq(20)].copy()
        positive["target_name"] = "forward_20d_positive_alpha_probability"
        positive["target_value"] = (positive["target_value"] > 0.0).astype(float)
        targets = pd.concat([targets, excess, positive], ignore_index=True)

    panel_columns = [
        "panel_row_id",
        "decision_timestamp_utc",
        "signal_date",
        "execution_date",
        "universe_id",
        "permanent_security_id",
        "permanent_company_id",
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
    panel = panel[panel_columns].sort_values(
        ["decision_timestamp_utc", "permanent_security_id"]
    ).reset_index(drop=True)
    return panel, targets, pd.DataFrame(inventories)


def validate_pilot_panel(panel: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append(_gate("panel_nonempty", not panel.empty, f"rows={len(panel)}"))
    rows.append(_gate("targets_nonempty", not targets.empty, f"rows={len(targets)}"))
    if panel.empty:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    unique = not bool(panel["panel_row_id"].duplicated().any())
    rows.append(_gate("panel_row_ids_unique", unique, f"rows={len(panel)}"))
    cutoff = pd.to_datetime(panel["model_cutoff_timestamp_utc"], utc=True, errors="coerce")
    maximum = pd.to_datetime(panel["feature_max_available_timestamp_utc"], utc=True, errors="coerce")
    rows.append(
        _gate(
            "feature_availability_not_after_cutoff",
            bool(maximum.notna().all() and cutoff.notna().all() and (maximum <= cutoff).all()),
            "technical pilot clocks",
        )
    )
    membership_known = pd.to_datetime(
        panel["membership_known_timestamp_utc"], utc=True, errors="coerce"
    )
    rows.append(
        _gate(
            "membership_known_before_cutoff",
            bool(membership_known.notna().all() and (membership_known <= cutoff).all()),
            "pilot membership knowledge clock",
        )
    )
    target_ids_valid = bool(targets["panel_row_id"].isin(set(panel["panel_row_id"])).all()) if not targets.empty else False
    rows.append(_gate("targets_join_to_panel", target_ids_valid, f"targets={len(targets)}"))
    if not targets.empty:
        end = pd.to_datetime(targets["target_period_end_date"], utc=True, errors="coerce")
        available = pd.to_datetime(
            targets["target_available_timestamp_utc"], utc=True, errors="coerce"
        )
        target_clock_valid = bool(
            end.notna().all() and available.notna().all() and (available > end).all()
        )
    else:
        target_clock_valid = False
    rows.append(_gate("targets_available_after_period_end", target_clock_valid, "label clock"))
    rows.append(
        _gate(
            "no_model_or_order_outputs",
            True,
            "Phase23F writes features and targets only",
        )
    )
    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    titles = {
        "membership_manifest_schema": "Membership Manifest Schema",
        "price_input_schema": "Price Input Schema",
        "calculated_feature_registry": "Calculated Feature Registry",
        "target_registry": "Target Registry",
        "input_readiness_contract": "Input Readiness Contract",
        "scope_boundary": "Phase Boundary",
        "input_readiness": "Input Readiness",
        "manifest_validation": "Manifest Validation",
        "source_inventory": "Source Inventory",
        "panel_validation": "Panel Validation",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    lines = [
        "# Phase 23F — Pilot Point-in-Time Individual-Stock Feature Calculation",
        "",
        (
            "This phase provides a local-input-only calculator for the first technical, "
            "liquidity, market-stress, and forward-target stock panel. It does not download "
            "data, train a model, backtest stock selection, or create orders."
        ),
        "",
    ]
    for key, title in titles.items():
        if key in outputs:
            lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23f_pilot_individual_equity_feature_calculation(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    phase_config = _phase_config(config)
    if not phase_config["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "panel_validation": empty, "conclusion": empty}

    output_dir = _resolve_reports_path(
        configured_path=phase_config["output_dir"], reports_dir=reports_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = _resolve_project_path(
        configured_path=phase_config["input_dir"], reports_dir=reports_dir
    )
    manifest_path = _resolve_project_path(
        configured_path=phase_config["membership_manifest_path"], reports_dir=reports_dir
    )
    benchmark_path = _resolve_project_path(
        configured_path=phase_config["benchmark_path"], reports_dir=reports_dir
    )

    membership_schema = build_membership_manifest_schema()
    price_schema = build_price_input_schema()
    feature_registry = build_calculated_feature_registry()
    target_registry = build_target_registry()
    readiness_contract = build_input_readiness_contract()
    scope_boundary = build_scope_boundary(phase_config)

    manifest_exists = manifest_path.exists()
    benchmark_exists = benchmark_path.exists()
    input_readiness = pd.DataFrame(
        [
            {
                "input": "membership_manifest",
                "path": str(manifest_path),
                "present": manifest_exists,
                "required": True,
            },
            {
                "input": "benchmark",
                "path": str(benchmark_path),
                "present": benchmark_exists,
                "required": True,
            },
        ]
    )

    manifest_validation = pd.DataFrame(
        [_gate("manifest_not_loaded", False, "local membership manifest pending")]
    )
    source_inventory = pd.DataFrame()
    panel_validation = pd.DataFrame(
        [_gate("pilot_panel_not_built", False, "local inputs pending")]
    )
    panel = pd.DataFrame()
    targets = pd.DataFrame()
    build_error = ""

    if manifest_exists:
        try:
            manifest = _read_table(manifest_path)
            manifest_validation = validate_membership_manifest(manifest)
            if bool(manifest_validation["passed"].all()):
                price_frames: dict[str, pd.DataFrame] = {}
                missing_files: list[str] = []
                for row in manifest.itertuples(index=False):
                    price_path = Path(str(row.price_file))
                    if not price_path.is_absolute():
                        price_path = input_dir / price_path
                    if not price_path.exists():
                        missing_files.append(str(price_path))
                        continue
                    price_frames[str(row.permanent_security_id)] = _read_table(price_path)
                input_readiness = pd.concat(
                    [
                        input_readiness,
                        pd.DataFrame(
                            [
                                {
                                    "input": "security_price_files",
                                    "path": str(input_dir),
                                    "present": not missing_files,
                                    "required": True,
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )
                if not missing_files and benchmark_exists:
                    benchmark = _read_table(benchmark_path)
                    panel, targets, source_inventory = build_pilot_panel_and_targets(
                        manifest=manifest,
                        price_frames=price_frames,
                        benchmark=benchmark,
                        phase_config=phase_config,
                    )
                    panel_validation = validate_pilot_panel(panel, targets)
        except (ValueError, KeyError, OSError) as exc:
            build_error = str(exc)
            panel_validation = pd.DataFrame(
                [_gate("pilot_panel_build", False, build_error)]
            )

    inputs_ready = bool(
        not input_readiness.empty
        and input_readiness.loc[input_readiness["required"], "present"].all()
    )
    panel_built = not panel.empty
    validation_passed = bool(
        not panel_validation.empty and panel_validation["passed"].all()
    )
    execution_passed = bool(scope_boundary["passed"].all())

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23F",
                "phase23f_decision": (
                    phase_config["phase_decision_ready"]
                    if panel_built and validation_passed
                    else phase_config["phase_decision_pending"]
                ),
                "phase_execution_gates_passed": execution_passed,
                "all_gates_passed": execution_passed,
                "feature_calculation_engine_ready": execution_passed,
                "pilot_input_data_ready": inputs_ready,
                "pilot_panel_built": panel_built,
                "pilot_panel_validation_passed": validation_passed,
                "pilot_panel_rows": int(len(panel)),
                "pilot_target_rows": int(len(targets)),
                "pilot_security_count": int(
                    panel["permanent_security_id"].nunique() if not panel.empty else 0
                ),
                "training_eligible_rows": int(
                    panel["training_eligible"].sum() if not panel.empty else 0
                ),
                "calculated_feature_count": int(len(feature_registry)),
                "registered_target_count": int(len(target_registry)),
                "pilot_start_date": phase_config["pilot_start_date"],
                "pilot_end_date": phase_config["pilot_end_date"],
                "membership_canonical": False,
                "research_pilot_only": True,
                "model_training_allowed": False,
                "backtest_allowed": False,
                "next_phase": (
                    "Phase 23F input completion and validation; then Phase 23G first "
                    "interpretable cross-sectional stock-ranking model"
                ),
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "build_error": build_error,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "verdict": (
                    "Phase23F built and validated a noncanonical local pilot stock feature and "
                    "target panel. It is not approved for model training until dependency and "
                    "coverage audits are completed."
                    if panel_built and validation_passed
                    else "Phase23F calculation engine is ready, but approved local pilot "
                    "membership, benchmark, and stock price files are still required."
                ),
                "pilot_panel_built": panel_built,
                "pilot_panel_validation_passed": validation_passed,
                "allowed_next_step": (
                    "review pilot coverage and leakage diagnostics"
                    if panel_built
                    else "populate the generated local input templates"
                ),
                "blocked_next_step": (
                    "model training, stock-selection backtest, paper orders, live trading, "
                    "real money, broker API"
                ),
            }
        ]
    )

    outputs = {
        "membership_manifest_schema": membership_schema,
        "price_input_schema": price_schema,
        "calculated_feature_registry": feature_registry,
        "target_registry": target_registry,
        "input_readiness_contract": readiness_contract,
        "scope_boundary": scope_boundary,
        "input_readiness": input_readiness,
        "manifest_validation": manifest_validation,
        "source_inventory": source_inventory,
        "panel_validation": panel_validation,
        "summary": summary,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23f_{name}.csv", index=False)
    if panel_built:
        panel.to_csv(output_dir / "phase23f_pilot_feature_panel.csv", index=False)
        try:
            panel.to_parquet(
                output_dir / "phase23f_pilot_feature_panel.parquet", index=False
            )
        except ImportError:
            pass
    if not targets.empty:
        targets.to_csv(output_dir / "phase23f_pilot_targets.csv", index=False)
        try:
            targets.to_parquet(output_dir / "phase23f_pilot_targets.parquet", index=False)
        except ImportError:
            pass

    build_empty_membership_manifest().to_csv(
        output_dir / "phase23f_pilot_membership_manifest_template.csv", index=False
    )
    build_empty_price_template().to_csv(
        output_dir / "phase23f_pilot_price_template.csv", index=False
    )
    _write_markdown(outputs, output_dir / "phase23f_pilot_feature_calculation.md")

    dashboard_path = _resolve_reports_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23f_pilot_feature_calculation_status_written"
    dashboard["notes"] = (
        "Local-input-only technical pilot; no model training, stock-selection backtest, or "
        "orders are permitted."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23F pilot individual-stock feature calculation reports.")
    return outputs
