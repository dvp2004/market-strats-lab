from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import sleep
from typing import Any, Callable

import pandas as pd


DEFAULT_PILOT_SECURITIES: list[dict[str, str]] = [
    {
        "ticker": "AAPL",
        "sector": "Information Technology",
        "industry": "Technology Hardware",
    },
    {
        "ticker": "MSFT",
        "sector": "Information Technology",
        "industry": "Systems Software",
    },
    {
        "ticker": "NVDA",
        "sector": "Information Technology",
        "industry": "Semiconductors",
    },
    {
        "ticker": "AMZN",
        "sector": "Consumer Discretionary",
        "industry": "Broadline Retail",
    },
    {
        "ticker": "GOOGL",
        "sector": "Communication Services",
        "industry": "Interactive Media and Services",
    },
    {
        "ticker": "META",
        "sector": "Communication Services",
        "industry": "Interactive Media and Services",
    },
    {
        "ticker": "JPM",
        "sector": "Financials",
        "industry": "Diversified Banks",
    },
    {
        "ticker": "BRK-B",
        "sector": "Financials",
        "industry": "Multi-Sector Holdings",
    },
    {
        "ticker": "XOM",
        "sector": "Energy",
        "industry": "Integrated Oil and Gas",
    },
    {
        "ticker": "JNJ",
        "sector": "Health Care",
        "industry": "Pharmaceuticals",
    },
    {
        "ticker": "UNH",
        "sector": "Health Care",
        "industry": "Managed Health Care",
    },
    {
        "ticker": "PG",
        "sector": "Consumer Staples",
        "industry": "Household Products",
    },
    {
        "ticker": "COST",
        "sector": "Consumer Staples",
        "industry": "Consumer Staples Merchandise Retail",
    },
    {
        "ticker": "CAT",
        "sector": "Industrials",
        "industry": "Construction Machinery",
    },
    {
        "ticker": "NEE",
        "sector": "Utilities",
        "industry": "Electric Utilities",
    },
    {
        "ticker": "TSLA",
        "sector": "Consumer Discretionary",
        "industry": "Automobile Manufacturers",
    },
]


DEFAULT_PHASE23F_INPUT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23f_pilot_input_bootstrap"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23f_pilot_input_bootstrap_status.csv"
    ),
    "input_dir": "data/individual_equity_pilot",
    "membership_manifest_path": (
        "data/individual_equity_pilot/pilot_membership_manifest.csv"
    ),
    "benchmark_ticker": "SPY",
    "benchmark_filename": "benchmark_SPY.csv",
    "download_start_date": "2021-12-01",
    "download_end_date_inclusive": "2026-05-01",
    "pilot_membership_start_date": "2023-01-03",
    "pilot_membership_known_timestamp_utc": "2023-01-03T00:00:00Z",
    "pilot_universe_id": "SP500_PILOT_NONCANONICAL",
    "minimum_price_rows": 700,
    "minimum_securities": 12,
    "retry_attempts": 3,
    "retry_delay_seconds": 2.0,
    "inter_symbol_delay_seconds": 0.25,
    "reuse_existing_valid_files": True,
    "allow_overwrite_existing": False,
    "pilot_securities": DEFAULT_PILOT_SECURITIES,
    "phase_decision_ready": "phase23f_pilot_inputs_ready_for_feature_calculation",
    "phase_decision_pending": "phase23f_pilot_input_bootstrap_incomplete",
    "allow_network_download": True,
    "allow_manifest_write": True,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}

PRICE_REQUIRED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
]

MEMBERSHIP_COLUMNS = [
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

DownloadFn = Callable[[str, str, str], pd.DataFrame]


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
        DEFAULT_PHASE23F_INPUT_CONFIG,
        config.get("phase23f_pilot_individual_equity_input_bootstrap", {}),
    )


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


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_pilot_security_registry(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in phase_config["pilot_securities"]:
        ticker = str(item["ticker"]).strip().upper()
        rows.append(
            {
                "ticker": ticker,
                "permanent_security_id": f"PILOT_SEC_{ticker.replace('-', '_')}",
                "permanent_company_id": f"PILOT_CO_{ticker.replace('-', '_')}",
                "sector": str(item["sector"]).strip(),
                "industry": str(item["industry"]).strip(),
                "price_file": f"{ticker}.csv",
                "canonical_membership": False,
                "research_pilot_only": True,
                "selection_policy": "fixed_diversified_engineering_pilot_not_investment_universe",
            }
        )
    return pd.DataFrame(rows)


def validate_pilot_security_registry(
    registry: pd.DataFrame, *, minimum_securities: int
) -> pd.DataFrame:
    required = {
        "ticker",
        "permanent_security_id",
        "permanent_company_id",
        "sector",
        "industry",
        "price_file",
        "canonical_membership",
        "research_pilot_only",
    }
    missing = sorted(required - set(registry.columns))
    rows = [_gate("required_columns_present", not missing, "missing=" + ";".join(missing))]
    if missing:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    rows.extend(
        [
            _gate(
                "minimum_security_count",
                len(registry) >= int(minimum_securities),
                f"count={len(registry)};required={minimum_securities}",
            ),
            _gate(
                "tickers_unique",
                not bool(registry["ticker"].duplicated().any()),
                f"count={len(registry)}",
            ),
            _gate(
                "security_ids_unique",
                not bool(registry["permanent_security_id"].duplicated().any()),
                f"count={len(registry)}",
            ),
            _gate(
                "pilot_noncanonical",
                not bool(registry["canonical_membership"].fillna(False).astype(bool).any()),
                "canonical membership is prohibited for this pilot",
            ),
            _gate(
                "research_pilot_acknowledged",
                bool(registry["research_pilot_only"].fillna(False).astype(bool).all()),
                f"count={len(registry)}",
            ),
        ]
    )
    nonblank = bool(
        registry[["ticker", "sector", "industry", "price_file"]]
        .fillna("")
        .astype(str)
        .apply(lambda column: column.str.strip().ne(""))
        .all()
        .all()
    )
    rows.append(_gate("required_values_nonblank", nonblank, f"count={len(registry)}"))
    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def _flatten_single_ticker_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame
    levels = frame.columns.nlevels
    if levels != 2:
        raise ValueError(f"Unsupported yfinance column levels: {levels}")
    first = [str(value) for value in frame.columns.get_level_values(0)]
    second = [str(value) for value in frame.columns.get_level_values(1)]
    known = {"Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"}
    if set(first) & known:
        working = frame.copy()
        working.columns = frame.columns.get_level_values(0)
        return working
    if set(second) & known:
        working = frame.copy()
        working.columns = frame.columns.get_level_values(1)
        return working
    raise ValueError("Unable to identify yfinance field level")


def normalize_yfinance_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise ValueError("Downloaded price frame is empty")
    working = _flatten_single_ticker_columns(frame.copy())
    if "Date" not in working.columns and "date" not in working.columns and isinstance(working.index, pd.DatetimeIndex):
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
    missing = sorted(set(PRICE_REQUIRED_COLUMNS) - set(working.columns))
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

    required_values = PRICE_REQUIRED_COLUMNS[1:]
    incomplete = working[required_values].isna().any(axis=1)
    if incomplete.any():
        complete_positions = [position for position, value in enumerate(incomplete) if not value]
        last_complete_position = max(complete_positions) if complete_positions else -1
        interior_mask = pd.Series(
            [bool(value) and position < last_complete_position for position, value in enumerate(incomplete)],
            index=working.index,
        )
        if interior_mask.any():
            bad_dates = working.loc[interior_mask, "date"].dt.strftime("%Y-%m-%d").tolist()
            raise ValueError("Downloaded frame has incomplete non-trailing rows: " + ";".join(bad_dates))
        working = working.loc[~incomplete]

    return working[
        PRICE_REQUIRED_COLUMNS + ["dividends", "stock_splits"]
    ].reset_index(drop=True)


def validate_downloaded_price_frame(
    frame: pd.DataFrame,
    *,
    minimum_price_rows: int,
    requested_start_date: str,
    requested_end_date_inclusive: str,
) -> pd.DataFrame:
    missing = sorted(set(PRICE_REQUIRED_COLUMNS) - set(frame.columns))
    rows = [_gate("required_columns_present", not missing, "missing=" + ";".join(missing))]
    if missing:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    working = frame.copy()
    dates = pd.to_datetime(working["date"], errors="coerce")
    rows.extend(
        [
            _gate(
                "minimum_history_rows",
                len(working) >= int(minimum_price_rows),
                f"rows={len(working)};required={minimum_price_rows}",
            ),
            _gate(
                "dates_parse_sorted_unique",
                bool(
                    dates.notna().all()
                    and dates.is_monotonic_increasing
                    and not dates.duplicated().any()
                ),
                f"rows={len(working)}",
            ),
            _gate(
                "requested_window_intersects",
                bool(
                    dates.notna().any()
                    and dates.min() <= pd.Timestamp(requested_start_date) + pd.Timedelta(days=10)
                    and dates.max() >= pd.Timestamp(requested_end_date_inclusive) - pd.Timedelta(days=10)
                ),
                (
                    f"first={dates.min() if dates.notna().any() else ''};"
                    f"last={dates.max() if dates.notna().any() else ''}"
                ),
            ),
        ]
    )
    numeric = working[["open", "high", "low", "close", "adj_close", "volume"]]
    finite = bool(numeric.notna().all().all())
    rows.append(_gate("required_values_complete", finite, f"rows={len(working)}"))
    positive = bool(
        (working[["open", "high", "low", "close", "adj_close"]] > 0).all().all()
        and (working["volume"] >= 0).all()
    )
    rows.append(_gate("prices_positive_volume_nonnegative", positive, f"rows={len(working)}"))
    ohlc = bool(
        (working["high"] >= working[["open", "close", "low"]].max(axis=1)).all()
        and (working["low"] <= working[["open", "close", "high"]].min(axis=1)).all()
    )
    rows.append(_gate("ohlc_consistent", ohlc, f"rows={len(working)}"))
    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def _default_yfinance_download(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is required for Phase23F pilot input download") from exc

    kwargs = {
        "tickers": ticker,
        "start": start,
        "end": end_exclusive,
        "interval": "1d",
        "actions": True,
        "auto_adjust": False,
        "back_adjust": False,
        "repair": False,
        "keepna": True,
        "progress": False,
        "threads": False,
        "group_by": "column",
        "multi_level_index": False,
    }
    try:
        downloaded = yf.download(**kwargs)
    except TypeError:
        # Compatible older yfinance releases may not expose this argument.
        kwargs.pop("multi_level_index", None)
        downloaded = yf.download(**kwargs)
    if downloaded is None:
        raise ValueError(f"No data returned for {ticker}")
    return downloaded


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _download_with_retries(
    *,
    ticker: str,
    start: str,
    end_exclusive: str,
    download_fn: DownloadFn,
    attempts: int,
    delay_seconds: float,
) -> pd.DataFrame:
    errors: list[str] = []
    for attempt in range(1, max(int(attempts), 1) + 1):
        try:
            return download_fn(ticker, start, end_exclusive)
        except Exception as exc:  # network/provider failures are recorded and fail closed
            errors.append(f"attempt={attempt}:{type(exc).__name__}:{exc}")
            if attempt < max(int(attempts), 1) and delay_seconds > 0:
                sleep(float(delay_seconds))
    raise RuntimeError(" | ".join(errors))


def _build_membership_manifest(
    registry: pd.DataFrame, phase_config: dict[str, Any]
) -> pd.DataFrame:
    manifest = registry[
        [
            "permanent_security_id",
            "permanent_company_id",
            "ticker",
            "sector",
            "industry",
            "price_file",
            "canonical_membership",
            "research_pilot_only",
        ]
    ].copy()
    manifest.insert(0, "universe_id", phase_config["pilot_universe_id"])
    manifest["membership_start_date"] = phase_config["pilot_membership_start_date"]
    manifest["membership_end_date"] = ""
    manifest["membership_known_timestamp_utc"] = phase_config[
        "pilot_membership_known_timestamp_utc"
    ]
    return manifest[MEMBERSHIP_COLUMNS]


def _scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    controls = [
        ("network_download_allowed", phase_config["allow_network_download"], True),
        ("manifest_write_allowed", phase_config["allow_manifest_write"], True),
        ("model_training_allowed", phase_config["allow_model_training"], False),
        ("backtest_allowed", phase_config["allow_backtest"], False),
        ("paper_orders_allowed", phase_config["allow_paper_orders"], False),
        ("live_trading_allowed", phase_config["allow_live_trading"], False),
        ("real_money_allowed", phase_config["allow_real_money"], False),
        ("broker_api_integration_allowed", phase_config["allow_broker_api"], False),
        ("promotion_allowed", phase_config["allow_promotion"], False),
    ]
    return pd.DataFrame(
        [
            {
                "control": name,
                "allowed": bool(actual),
                "required_state": bool(required),
                "passed": bool(actual) is bool(required),
            }
            for name, actual, required in controls
        ]
    )


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    lines = [
        "# Phase 23F Input Bootstrap — Controlled Individual-Equity Pilot",
        "",
        "This phase downloads a fixed, noncanonical engineering pilot using yfinance/Yahoo "
        "Finance data. It does not establish historical index membership, approve canonical "
        "market data, train a model, run a stock-selection backtest, or create orders.",
        "",
    ]
    titles = {
        "security_registry": "Pilot Security Registry",
        "registry_validation": "Registry Validation",
        "download_status": "Download Status",
        "source_inventory": "Source Inventory",
        "scope_boundary": "Scope Boundary",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    for key, title in titles.items():
        lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23f_pilot_individual_equity_input_bootstrap(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    download_fn: DownloadFn | None = None,
) -> dict[str, pd.DataFrame]:
    phase_config = _phase_config(config)
    if not phase_config["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "download_status": empty, "conclusion": empty}

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
    input_dir.mkdir(parents=True, exist_ok=True)

    registry = build_pilot_security_registry(phase_config)
    registry_validation = validate_pilot_security_registry(
        registry, minimum_securities=int(phase_config["minimum_securities"])
    )
    scope_boundary = _scope_boundary(phase_config)
    configured_download = download_fn or _default_yfinance_download

    download_start = str(phase_config["download_start_date"])
    inclusive_end = pd.Timestamp(phase_config["download_end_date_inclusive"])
    end_exclusive = (inclusive_end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    retrieved_at = datetime.now(timezone.utc).isoformat()

    requests: list[dict[str, str]] = [
        {
            "ticker": str(phase_config["benchmark_ticker"]).upper(),
            "role": "benchmark",
            "filename": str(phase_config["benchmark_filename"]),
        }
    ]
    requests.extend(
        {
            "ticker": str(row.ticker),
            "role": "pilot_security",
            "filename": str(row.price_file),
        }
        for row in registry.itertuples(index=False)
    )

    statuses: list[dict[str, Any]] = []
    inventories: list[dict[str, Any]] = []
    for index, request in enumerate(requests):
        ticker = request["ticker"]
        path = input_dir / request["filename"]
        status = "pending"
        error = ""
        validation_passed = False
        reused_existing = False
        frame = pd.DataFrame()

        try:
            if path.exists() and bool(phase_config["reuse_existing_valid_files"]):
                existing = pd.read_csv(path)
                normalized_existing = normalize_yfinance_price_frame(existing)
                existing_report = validate_downloaded_price_frame(
                    normalized_existing,
                    minimum_price_rows=int(phase_config["minimum_price_rows"]),
                    requested_start_date=download_start,
                    requested_end_date_inclusive=str(inclusive_end.date()),
                )
                if bool(existing_report["passed"].all()):
                    frame = normalized_existing
                    reused_existing = True
                    status = "reused_existing_valid_file"
                    validation_passed = True

            if not validation_passed:
                if path.exists() and not bool(phase_config["allow_overwrite_existing"]):
                    raise FileExistsError(
                        f"Existing invalid or unreused file cannot be overwritten: {path}"
                    )
                raw = _download_with_retries(
                    ticker=ticker,
                    start=download_start,
                    end_exclusive=end_exclusive,
                    download_fn=configured_download,
                    attempts=int(phase_config["retry_attempts"]),
                    delay_seconds=float(phase_config["retry_delay_seconds"]),
                )
                frame = normalize_yfinance_price_frame(raw)
                validation = validate_downloaded_price_frame(
                    frame,
                    minimum_price_rows=int(phase_config["minimum_price_rows"]),
                    requested_start_date=download_start,
                    requested_end_date_inclusive=str(inclusive_end.date()),
                )
                validation_passed = bool(validation["passed"].all())
                if not validation_passed:
                    failed = validation.loc[~validation["passed"], "gate"].tolist()
                    raise ValueError("price_validation_failed:" + ";".join(failed))
                _write_csv_atomic(frame, path)
                status = "downloaded_and_validated"

            inventories.append(
                {
                    "ticker": ticker,
                    "role": request["role"],
                    "path": str(path),
                    "rows": len(frame),
                    "first_date": frame["date"].min(),
                    "last_date": frame["date"].max(),
                    "sha256": _file_sha256(path),
                    "provider": "Yahoo Finance via yfinance",
                    "download_start": download_start,
                    "download_end_exclusive": end_exclusive,
                    "retrieved_at_utc": retrieved_at,
                    "auto_adjust": False,
                    "actions": True,
                    "canonical_market_data": False,
                    "research_pilot_only": True,
                }
            )
        except Exception as exc:
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"

        statuses.append(
            {
                "ticker": ticker,
                "role": request["role"],
                "path": str(path),
                "status": status,
                "validation_passed": validation_passed,
                "reused_existing": reused_existing,
                "error": error,
            }
        )
        if (
            index < len(requests) - 1
            and not reused_existing
            and float(phase_config["inter_symbol_delay_seconds"]) > 0
        ):
            sleep(float(phase_config["inter_symbol_delay_seconds"]))

    download_status = pd.DataFrame(statuses)
    source_inventory = pd.DataFrame(inventories)
    all_downloads_ready = bool(
        len(download_status) == len(requests)
        and download_status["validation_passed"].all()
    )
    registry_ready = bool(registry_validation["passed"].all())
    scope_ready = bool(scope_boundary["passed"].all())
    manifest_written = False

    if all_downloads_ready and registry_ready and bool(phase_config["allow_manifest_write"]):
        manifest = _build_membership_manifest(registry, phase_config)
        _write_csv_atomic(manifest, manifest_path)
        manifest_written = True
    else:
        manifest = _build_membership_manifest(registry, phase_config)
        manifest.to_csv(output_dir / "phase23f_pending_membership_manifest.csv", index=False)

    phase_ready = bool(all_downloads_ready and registry_ready and scope_ready and manifest_written)
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23F Input Bootstrap",
                "phase23f_input_decision": (
                    phase_config["phase_decision_ready"]
                    if phase_ready
                    else phase_config["phase_decision_pending"]
                ),
                "phase_execution_gates_passed": scope_ready,
                "all_gates_passed": scope_ready,
                "pilot_registry_valid": registry_ready,
                "configured_security_count": int(len(registry)),
                "minimum_security_count": int(phase_config["minimum_securities"]),
                "validated_security_files": int(
                    download_status.loc[
                        download_status["role"].eq("pilot_security"),
                        "validation_passed",
                    ].sum()
                ),
                "benchmark_ready": bool(
                    download_status.loc[
                        download_status["role"].eq("benchmark"),
                        "validation_passed",
                    ].all()
                ),
                "all_required_downloads_ready": all_downloads_ready,
                "membership_manifest_written": manifest_written,
                "membership_manifest_path": str(manifest_path),
                "download_start_date": download_start,
                "download_end_date_inclusive": str(inclusive_end.date()),
                "membership_canonical": False,
                "market_data_canonical": False,
                "research_pilot_only": True,
                "phase23f_feature_calculation_ready": phase_ready,
                "model_training_allowed": False,
                "backtest_allowed": False,
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "verdict": (
                    "Controlled noncanonical pilot price inputs and membership manifest are "
                    "ready for the Phase23F feature calculation engine."
                    if phase_ready
                    else "Pilot input bootstrap remains incomplete; failed or missing files "
                    "must be resolved before Phase23F feature calculation."
                ),
                "allowed_next_step": (
                    "run --phase23f-only and review panel validation"
                    if phase_ready
                    else "review phase23f_download_status.csv and rerun input bootstrap"
                ),
                "blocked_next_step": (
                    "model training, stock-selection backtest, paper orders, live trading, "
                    "real money, broker API"
                ),
            }
        ]
    )

    outputs = {
        "security_registry": registry,
        "registry_validation": registry_validation,
        "download_status": download_status,
        "source_inventory": source_inventory,
        "scope_boundary": scope_boundary,
        "summary": summary,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23f_input_{name}.csv", index=False)
    _write_markdown(outputs, output_dir / "phase23f_pilot_input_bootstrap.md")

    dashboard_path = _resolve_reports_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23f_pilot_input_bootstrap_status_written"
    dashboard["notes"] = (
        "Research-only yfinance/Yahoo pilot inputs; not canonical point-in-time index data and "
        "not approved for production or investment decisions."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23F controlled pilot input bootstrap reports.")
    return outputs
