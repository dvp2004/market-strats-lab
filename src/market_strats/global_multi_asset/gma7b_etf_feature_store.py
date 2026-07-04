from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

PHASE_ID = "gma7b_etf_feature_store_v1"
FEATURE_STORE_VERSION = "gma7b_point_in_time_etf_feature_store_v1"
FEATURE_SET_VERSION = "gma7b_core22_price_features_v1"
ACTIVE_COHORT = "etf_multi_asset_core_v1"
EVIDENCE_CLASS = "observed_development_evidence"
SNAPSHOT_ROOT = Path(
    r"C:\Users\Devesh Pansare\Desktop\Personal_Projects\market-strats-lab-gma6-v1-evidence-snapshot-20260624"
)
EXPECTED_GMA6_SNAPSHOT_MANIFEST_HASH = (
    "e767cb622bfe41240a8a4536920f79def3d267092b1bd0dcb2e6a06865ecdc6a"
)
EXPECTED_GMA6B_DATA_BUNDLE_MANIFEST_HASH = (
    "b93bd9800ddfffa19f12100c4538a4668ae61c20b7e322fec8df9441f63a166b"
)
EXPECTED_NORMALISED_BUNDLE_HASH = "3d3d920e9bafa430fb313fe0f494954826a73f8962a15eb8709d02f2bae14bb6"
CORE_22_UNIVERSE = [
    "SPY",
    "QQQ",
    "IWM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "EFA",
    "EEM",
    "BIL",
    "IEF",
    "TLT",
    "AGG",
    "LQD",
    "HYG",
    "GLD",
    "DBC",
]
PREDICTION_ASSETS = [ticker for ticker in CORE_22_UNIVERSE if ticker != "BIL"]
EQUITY_CONTEXT_TICKERS = [
    "SPY",
    "QQQ",
    "IWM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "EFA",
    "EEM",
]
PER_ASSET_FEATURE_COLUMNS = [
    "return_21d",
    "return_63d",
    "return_126d",
    "return_252d",
    "excess_return_vs_bil_21d",
    "excess_return_vs_bil_63d",
    "excess_return_vs_bil_126d",
    "excess_return_vs_bil_252d",
    "ma_gap_50d",
    "ma_gap_200d",
    "short_reversal_5d",
    "short_reversal_10d",
    "realised_volatility_21d",
    "realised_volatility_63d",
    "drawdown_63d",
    "drawdown_252d",
    "correlation_to_spy_63d",
    "cross_section_rank_return_63d",
    "cross_section_rank_return_126d",
    "cross_section_rank_return_252d",
]
CONTEXT_FEATURE_COLUMNS = [
    "equity_breadth_above_ma200",
    "spy_drawdown_252d",
    "spy_above_ma200",
    "credit_duration_spread_63d",
    "bond_equity_relative_return_63d",
    "gold_equity_relative_return_63d",
    "cross_asset_return_dispersion_63d",
]
FEATURE_COLUMNS = PER_ASSET_FEATURE_COLUMNS + CONTEXT_FEATURE_COLUMNS
METADATA_COLUMNS = [
    "feature_store_version",
    "feature_set_version",
    "asset_ticker",
    "is_prediction_asset",
    "decision_session_date",
    "decision_timestamp",
    "signal_observation_cutoff",
    "earliest_execution_session_date",
    "target_start_session_date",
    "forward_label_window_available",
    "source_last_observed_session",
    "feature_availability_status",
    "research_partition",
    "core22_universe_hash",
    "gma7a_contract_hash",
    "gma6b_data_bundle_manifest_hash",
    "normalised_bundle_hash",
]
FEATURE_STORE_COLUMNS = METADATA_COLUMNS + FEATURE_COLUMNS
FORBIDDEN_COLUMN_FRAGMENTS = [
    "target_return",
    "forward_return",
    "forecast",
    "prediction",
    "weight",
    "cagr",
    "sharpe",
    "portfolio",
    "performance",
]
REQUIRED_LANGUAGE = [
    "This is a point-in-time feature store built from frozen adjusted-price evidence.",
    "All feature values use only information available by the monthly decision-session close.",
    "Forward target values, forecasts, model outputs, portfolio weights, and performance results are not generated in GMA-7B.",
    "This is observed development evidence and not a pristine final holdout.",
    "No execution or promotion decision is produced.",
]
OUTPUT_DIR = Path("reports/global_multi_asset_alpha/gma7b_etf_feature_store_v1")
OUTPUT_PATHS = {
    "config": Path("configs/global_multi_asset_alpha/gma7b_etf_feature_store_contract_v1.yaml"),
    "docs": Path("docs/global_multi_asset_alpha/gma7b_etf_feature_store_contract_v1.md"),
    "feature_dictionary": OUTPUT_DIR / "gma7b_feature_dictionary_v1.csv",
    "features": OUTPUT_DIR / "gma7b_monthly_point_in_time_features_v1.csv",
    "manifest": OUTPUT_DIR / "gma7b_feature_store_manifest_v1.json",
    "coverage_csv": OUTPUT_DIR / "gma7b_feature_store_coverage_audit_v1.csv",
    "coverage_md": OUTPUT_DIR / "gma7b_feature_store_coverage_audit_v1.md",
    "lock": OUTPUT_DIR / "gma7b_feature_store_lock_v1.json",
}


class GMA7BFeatureStoreError(ValueError):
    pass


@dataclass(frozen=True)
class FrozenHashExpectations:
    gma6_snapshot_manifest_sha256: str = EXPECTED_GMA6_SNAPSHOT_MANIFEST_HASH
    gma6b_data_bundle_manifest_hash: str = EXPECTED_GMA6B_DATA_BUNDLE_MANIFEST_HASH
    normalised_bundle_hash: str = EXPECTED_NORMALISED_BUNDLE_HASH


@dataclass(frozen=True)
class FrozenInputVerification:
    snapshot_root: Path
    snapshot_manifest_path: Path
    bundle_manifest_path: Path
    normalised_hash_inventory_path: Path
    gma6_snapshot_manifest_hash: str
    gma6b_data_bundle_manifest_hash: str
    normalised_bundle_hash: str
    bundle_manifest: dict[str, Any]
    normalised_hash_inventory: dict[str, str]


@dataclass(frozen=True)
class FeatureStoreResult:
    manifest: dict[str, Any]
    output_paths: dict[str, Path]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GMA7BFeatureStoreError(f"YAML file must be a mapping: {path}")
    return raw


def core22_universe_hash(symbols: list[str] | None = None) -> str:
    values = symbols if symbols is not None else CORE_22_UNIVERSE
    return sha256_text("|".join(values))


def load_and_validate_gma7a_contract(repo_root: Path) -> tuple[dict[str, Any], str]:
    path = repo_root / "configs/global_multi_asset_alpha/gma7a_predictive_ensemble_contract_v1.yaml"
    if not path.is_file():
        raise GMA7BFeatureStoreError(f"Missing GMA-7A contract: {path}")
    contract = _read_yaml_mapping(path)
    symbols = list((contract.get("universe") or {}).get("symbols") or [])
    if symbols != CORE_22_UNIVERSE:
        raise GMA7BFeatureStoreError("GMA-7A Core-22 ticker order mismatch")
    cohort = (contract.get("universe") or {}).get("cohort_id")
    if cohort != ACTIVE_COHORT:
        raise GMA7BFeatureStoreError("GMA-7B only accepts etf_multi_asset_core_v1")
    return contract, sha256_file(path)


def load_and_validate_gma7a_lock(repo_root: Path) -> tuple[dict[str, Any], str]:
    path = repo_root / "reports/global_multi_asset_alpha/gma7a_predictive_ensemble_lock_v1.json"
    if not path.is_file():
        raise GMA7BFeatureStoreError(f"Missing GMA-7A lock: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("core22_universe_hash") != core22_universe_hash():
        raise GMA7BFeatureStoreError("GMA-7A lock Core-22 hash mismatch")
    if raw.get("active_cohorts") != [ACTIVE_COHORT]:
        raise GMA7BFeatureStoreError("GMA-7A lock active cohort mismatch")
    return raw, sha256_file(path)


def verify_frozen_inputs(
    snapshot_root: Path = SNAPSHOT_ROOT,
    expectations: FrozenHashExpectations = FrozenHashExpectations(),
) -> FrozenInputVerification:
    snapshot_manifest = snapshot_root / "gma6_v1_evidence_snapshot_manifest_v1.csv"
    bundle_root = (
        snapshot_root / "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1"
    )
    bundle_manifest = bundle_root / "gma6b_data_bundle_manifest_v1.json"
    normalised_inventory = bundle_root / "gma6b_normalised_file_hashes_v1.csv"
    for path in [snapshot_manifest, bundle_manifest, normalised_inventory]:
        if not path.is_file():
            raise GMA7BFeatureStoreError(f"Missing frozen input: {path}")
    snapshot_hash = sha256_file(snapshot_manifest)
    bundle_hash = sha256_file(bundle_manifest)
    normalised_hash = sha256_file(normalised_inventory)
    if snapshot_hash != expectations.gma6_snapshot_manifest_sha256:
        raise GMA7BFeatureStoreError("GMA-6 snapshot manifest hash mismatch")
    if bundle_hash != expectations.gma6b_data_bundle_manifest_hash:
        raise GMA7BFeatureStoreError("GMA-6B data bundle manifest hash mismatch")
    if normalised_hash != expectations.normalised_bundle_hash:
        raise GMA7BFeatureStoreError("GMA-6B normalised bundle hash mismatch")
    manifest = json.loads(bundle_manifest.read_text(encoding="utf-8"))
    requested = list(manifest.get("requested_tickers") or [])
    if requested[: len(CORE_22_UNIVERSE)] != CORE_22_UNIVERSE:
        raise GMA7BFeatureStoreError("GMA-6B requested ticker order does not begin with Core-22")
    if manifest.get("normalised_file_hashes_hash") != expectations.normalised_bundle_hash:
        raise GMA7BFeatureStoreError("GMA-6B manifest normalised hash inventory mismatch")
    inventory: dict[str, str] = {}
    with normalised_inventory.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("ticker") or "")
            digest = str(row.get("normalised_series_file_hash") or "")
            if ticker and digest:
                inventory[ticker] = digest
    missing = [ticker for ticker in CORE_22_UNIVERSE if ticker not in inventory]
    if missing:
        raise GMA7BFeatureStoreError(f"Missing Core-22 normalised hash rows: {missing}")
    return FrozenInputVerification(
        snapshot_root=snapshot_root,
        snapshot_manifest_path=snapshot_manifest,
        bundle_manifest_path=bundle_manifest,
        normalised_hash_inventory_path=normalised_inventory,
        gma6_snapshot_manifest_hash=snapshot_hash,
        gma6b_data_bundle_manifest_hash=bundle_hash,
        normalised_bundle_hash=normalised_hash,
        bundle_manifest=manifest,
        normalised_hash_inventory=inventory,
    )


def _normalised_file_for_ticker(verification: FrozenInputVerification, ticker: str) -> Path:
    base = (
        verification.snapshot_root
        / "reports/global_multi_asset_alpha/gma6b_expanded_etf_data_bundle_v1"
        / "normalised/yahoo_yfinance"
        / ticker
    )
    files = sorted(base.glob("*_normalised.csv"))
    if len(files) != 1:
        raise GMA7BFeatureStoreError(
            f"Expected one normalised CSV for {ticker}; found {len(files)}"
        )
    actual = sha256_file(files[0])
    expected = verification.normalised_hash_inventory[ticker]
    if actual != expected:
        raise GMA7BFeatureStoreError(f"Normalised file hash mismatch for {ticker}")
    return files[0]


def load_adjusted_price_panel(verification: FrozenInputVerification) -> pd.DataFrame:
    series_by_ticker: dict[str, pd.Series] = {}
    reference_index: pd.DatetimeIndex | None = None
    for ticker in CORE_22_UNIVERSE:
        path = _normalised_file_for_ticker(verification, ticker)
        raw = pd.read_csv(path)
        required = {"date", "adj_close"}
        missing = required - set(raw.columns)
        if missing:
            raise GMA7BFeatureStoreError(f"{ticker} normalised file missing columns: {missing}")
        dates = pd.to_datetime(raw["date"], errors="raise")
        if dates.duplicated().any():
            raise GMA7BFeatureStoreError(f"Duplicate dates in normalised series for {ticker}")
        values = pd.to_numeric(raw["adj_close"], errors="raise")
        if values.isna().any() or (values <= 0).any():
            raise GMA7BFeatureStoreError(
                f"Invalid adjusted prices in normalised series for {ticker}"
            )
        series = pd.Series(values.to_numpy(dtype="float64"), index=dates, name=ticker).sort_index()
        if reference_index is None:
            reference_index = pd.DatetimeIndex(series.index)
        elif not series.index.equals(reference_index):
            raise GMA7BFeatureStoreError(f"Adjusted-price coverage is incomplete for {ticker}")
        series_by_ticker[ticker] = series
    panel = pd.DataFrame(series_by_ticker, index=reference_index)
    if panel.columns.tolist() != CORE_22_UNIVERSE:
        raise GMA7BFeatureStoreError("Adjusted-price panel ticker order mismatch")
    if panel.isna().any().any():
        raise GMA7BFeatureStoreError("Adjusted-price panel contains missing Core-22 values")
    return panel


def monthly_decision_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    if not index.is_monotonic_increasing:
        raise GMA7BFeatureStoreError("Price index must be sorted")
    frame = pd.DataFrame({"session": index}, index=index)
    return list(frame.groupby(index.to_period("M"))["session"].last())


def _utc_iso_from_ny_session(session: pd.Timestamp, local_hour: int) -> str:
    ny = ZoneInfo("America/New_York")
    local = datetime.combine(session.date(), time(local_hour, 0), tzinfo=ny)
    return local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")


def research_partition_for_session(session: pd.Timestamp) -> str:
    value = session.date()
    if value <= date(2020, 12, 31):
        return "development_nested_walk_forward"
    if date(2021, 1, 4) <= value <= date(2026, 5, 1):
        return "gma7_model_specific_lockbox"
    raise GMA7BFeatureStoreError(f"Decision session outside frozen GMA-7 partitions: {value}")


def _return(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    return prices / prices.shift(window) - 1.0


def _ma_gap(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    return prices / prices.rolling(window=window, min_periods=window).mean() - 1.0


def _drawdown(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    return prices / prices.rolling(window=window, min_periods=window).max() - 1.0


def _annualised_volatility(log_returns: pd.DataFrame, window: int) -> pd.DataFrame:
    return log_returns.rolling(window=window, min_periods=window).std(ddof=1) * math.sqrt(252.0)


def compute_feature_tables(prices: pd.DataFrame) -> dict[str, Any]:
    log_returns = (prices / prices.shift(1)).apply(lambda column: column.map(math.log))
    returns = {window: _return(prices, window) for window in [5, 10, 21, 63, 126, 252]}
    ma_gaps = {window: _ma_gap(prices, window) for window in [50, 200]}
    drawdowns = {window: _drawdown(prices, window) for window in [63, 252]}
    vol = {window: _annualised_volatility(log_returns, window) for window in [21, 63]}
    corr_spy = log_returns.rolling(window=63, min_periods=63).corr(log_returns["SPY"])
    return {
        "returns": returns,
        "ma_gaps": ma_gaps,
        "drawdowns": drawdowns,
        "volatility": vol,
        "correlation_to_spy_63d": corr_spy,
    }


def _average_tie_rank(values: pd.Series) -> pd.Series:
    ranks = values.rank(method="average", ascending=True)
    return (ranks - 1.0) / 20.0


def _context_features(
    session: pd.Timestamp,
    tables: dict[str, Any],
) -> dict[str, float]:
    returns = tables["returns"]
    ma_200 = tables["ma_gaps"][200].loc[session]
    drawdown_252 = tables["drawdowns"][252].loc[session]
    ret_63 = returns[63].loc[session]
    pred_ret_63 = ret_63[PREDICTION_ASSETS]
    return {
        "equity_breadth_above_ma200": float((ma_200[EQUITY_CONTEXT_TICKERS] > 0).mean()),
        "spy_drawdown_252d": float(drawdown_252["SPY"]),
        "spy_above_ma200": float(1.0 if ma_200["SPY"] > 0 else 0.0),
        "credit_duration_spread_63d": float(ret_63["HYG"] - ret_63["IEF"]),
        "bond_equity_relative_return_63d": float(ret_63["AGG"] - ret_63["SPY"]),
        "gold_equity_relative_return_63d": float(ret_63["GLD"] - ret_63["SPY"]),
        "cross_asset_return_dispersion_63d": float(pred_ret_63.std(ddof=1)),
    }


def build_feature_store(
    prices: pd.DataFrame,
    *,
    gma7a_contract_hash: str,
    gma6b_data_bundle_manifest_hash: str,
    normalised_bundle_hash: str,
    core_hash: str,
) -> pd.DataFrame:
    if prices.columns.tolist() != CORE_22_UNIVERSE:
        raise GMA7BFeatureStoreError("Feature store requires exact Core-22 ticker order")
    tables = compute_feature_tables(prices)
    index = pd.DatetimeIndex(prices.index)
    index_positions = {session: position for position, session in enumerate(index)}
    rows: list[dict[str, Any]] = []
    for session in monthly_decision_dates(index):
        position = index_positions[session]
        if position < 252 or position >= len(index) - 1:
            continue
        next_session = index[position + 1]
        forward_available = position + 20 < len(index)
        context = _context_features(session, tables)
        rank_inputs = {
            window: tables["returns"][window].loc[session, PREDICTION_ASSETS]
            for window in [63, 126, 252]
        }
        rank_missing = any(values.isna().any() for values in rank_inputs.values())
        ranks = {
            window: _average_tie_rank(values) if not rank_missing else values * math.nan
            for window, values in rank_inputs.items()
        }
        for asset in PREDICTION_ASSETS:
            feature_values = {
                "return_21d": tables["returns"][21].loc[session, asset],
                "return_63d": tables["returns"][63].loc[session, asset],
                "return_126d": tables["returns"][126].loc[session, asset],
                "return_252d": tables["returns"][252].loc[session, asset],
                "excess_return_vs_bil_21d": tables["returns"][21].loc[session, asset]
                - tables["returns"][21].loc[session, "BIL"],
                "excess_return_vs_bil_63d": tables["returns"][63].loc[session, asset]
                - tables["returns"][63].loc[session, "BIL"],
                "excess_return_vs_bil_126d": tables["returns"][126].loc[session, asset]
                - tables["returns"][126].loc[session, "BIL"],
                "excess_return_vs_bil_252d": tables["returns"][252].loc[session, asset]
                - tables["returns"][252].loc[session, "BIL"],
                "ma_gap_50d": tables["ma_gaps"][50].loc[session, asset],
                "ma_gap_200d": tables["ma_gaps"][200].loc[session, asset],
                "short_reversal_5d": -tables["returns"][5].loc[session, asset],
                "short_reversal_10d": -tables["returns"][10].loc[session, asset],
                "realised_volatility_21d": tables["volatility"][21].loc[session, asset],
                "realised_volatility_63d": tables["volatility"][63].loc[session, asset],
                "drawdown_63d": tables["drawdowns"][63].loc[session, asset],
                "drawdown_252d": tables["drawdowns"][252].loc[session, asset],
                "correlation_to_spy_63d": tables["correlation_to_spy_63d"].loc[session, asset],
                "cross_section_rank_return_63d": ranks[63].loc[asset],
                "cross_section_rank_return_126d": ranks[126].loc[asset],
                "cross_section_rank_return_252d": ranks[252].loc[asset],
            }
            feature_values.update(context)
            missing_feature_names = [key for key, value in feature_values.items() if pd.isna(value)]
            reasons: list[str] = []
            if rank_missing:
                reasons.append("missing_cross_sectional_rank_input")
            if missing_feature_names:
                reasons.append("missing_required_feature_value")
            metadata = {
                "feature_store_version": FEATURE_STORE_VERSION,
                "feature_set_version": FEATURE_SET_VERSION,
                "asset_ticker": asset,
                "is_prediction_asset": True,
                "decision_session_date": session.date().isoformat(),
                "decision_timestamp": _utc_iso_from_ny_session(session, 17),
                "signal_observation_cutoff": _utc_iso_from_ny_session(session, 16),
                "earliest_execution_session_date": next_session.date().isoformat(),
                "target_start_session_date": next_session.date().isoformat(),
                "forward_label_window_available": bool(forward_available),
                "source_last_observed_session": session.date().isoformat(),
                "feature_availability_status": "available" if not reasons else ";".join(reasons),
                "research_partition": research_partition_for_session(session),
                "core22_universe_hash": core_hash,
                "gma7a_contract_hash": gma7a_contract_hash,
                "gma6b_data_bundle_manifest_hash": gma6b_data_bundle_manifest_hash,
                "normalised_bundle_hash": normalised_bundle_hash,
            }
            rows.append({**metadata, **feature_values})
    frame = pd.DataFrame(rows, columns=FEATURE_STORE_COLUMNS)
    if frame.empty:
        raise GMA7BFeatureStoreError("No feature rows emitted after 252-session lookback checks")
    forbidden = [
        column
        for column in frame.columns
        if any(fragment in column.lower() for fragment in FORBIDDEN_COLUMN_FRAGMENTS)
        and column not in {"is_prediction_asset"}
    ]
    if forbidden:
        raise GMA7BFeatureStoreError(f"Forbidden output columns emitted: {forbidden}")
    return frame


def feature_dictionary_rows() -> list[dict[str, str]]:
    rows = []
    definitions = {
        "return_21d": "adjusted close at decision session divided by adjusted close 21 sessions earlier minus one",
        "return_63d": "adjusted close at decision session divided by adjusted close 63 sessions earlier minus one",
        "return_126d": "adjusted close at decision session divided by adjusted close 126 sessions earlier minus one",
        "return_252d": "adjusted close at decision session divided by adjusted close 252 sessions earlier minus one",
        "excess_return_vs_bil_21d": "asset return_21d minus BIL return_21d over the same historical window",
        "excess_return_vs_bil_63d": "asset return_63d minus BIL return_63d over the same historical window",
        "excess_return_vs_bil_126d": "asset return_126d minus BIL return_126d over the same historical window",
        "excess_return_vs_bil_252d": "asset return_252d minus BIL return_252d over the same historical window",
        "ma_gap_50d": "adjusted close at decision session divided by inclusive 50-session moving average minus one",
        "ma_gap_200d": "adjusted close at decision session divided by inclusive 200-session moving average minus one",
        "short_reversal_5d": "negative of return_5d",
        "short_reversal_10d": "negative of return_10d",
        "realised_volatility_21d": "annualised standard deviation of 21 daily log returns ending at decision session close",
        "realised_volatility_63d": "annualised standard deviation of 63 daily log returns ending at decision session close",
        "drawdown_63d": "adjusted close divided by maximum adjusted close over inclusive 63-session window minus one",
        "drawdown_252d": "adjusted close divided by maximum adjusted close over inclusive 252-session window minus one",
        "correlation_to_spy_63d": "Pearson correlation of asset and SPY daily log returns over the prior 63 sessions",
        "cross_section_rank_return_63d": "ascending average-tie percentile rank of return_63d across exactly 21 non-BIL prediction assets",
        "cross_section_rank_return_126d": "ascending average-tie percentile rank of return_126d across exactly 21 non-BIL prediction assets",
        "cross_section_rank_return_252d": "ascending average-tie percentile rank of return_252d across exactly 21 non-BIL prediction assets",
        "equity_breadth_above_ma200": "share of equity-context ETFs with ma_gap_200d greater than zero",
        "spy_drawdown_252d": "SPY drawdown_252d repeated as cross-asset context",
        "spy_above_ma200": "one when SPY ma_gap_200d is greater than zero, else zero",
        "credit_duration_spread_63d": "HYG return_63d minus IEF return_63d",
        "bond_equity_relative_return_63d": "AGG return_63d minus SPY return_63d",
        "gold_equity_relative_return_63d": "GLD return_63d minus SPY return_63d",
        "cross_asset_return_dispersion_63d": "cross-sectional standard deviation of return_63d across exactly 21 non-BIL prediction assets",
    }
    families = {
        "return_21d": "trend_and_momentum",
        "return_63d": "trend_and_momentum",
        "return_126d": "trend_and_momentum",
        "return_252d": "trend_and_momentum",
        "excess_return_vs_bil_21d": "trend_and_momentum",
        "excess_return_vs_bil_63d": "trend_and_momentum",
        "excess_return_vs_bil_126d": "trend_and_momentum",
        "excess_return_vs_bil_252d": "trend_and_momentum",
        "ma_gap_50d": "trend_and_momentum",
        "ma_gap_200d": "trend_and_momentum",
        "short_reversal_5d": "short_horizon_mean_reversion",
        "short_reversal_10d": "short_horizon_mean_reversion",
        "realised_volatility_21d": "realised_volatility_drawdown_and_correlation_risk",
        "realised_volatility_63d": "realised_volatility_drawdown_and_correlation_risk",
        "drawdown_63d": "realised_volatility_drawdown_and_correlation_risk",
        "drawdown_252d": "realised_volatility_drawdown_and_correlation_risk",
        "correlation_to_spy_63d": "realised_volatility_drawdown_and_correlation_risk",
        "cross_section_rank_return_63d": "trend_and_momentum",
        "cross_section_rank_return_126d": "trend_and_momentum",
        "cross_section_rank_return_252d": "trend_and_momentum",
    }
    for feature in PER_ASSET_FEATURE_COLUMNS:
        rows.append(
            {
                "feature_name": feature,
                "feature_scope": "per_asset",
                "feature_family": families[feature],
                "model_input": "true",
                "definition": definitions[feature],
                "rolling_window_convention": "inclusive_decision_session_close",
                "uses_forward_information": "false",
            }
        )
    for feature in CONTEXT_FEATURE_COLUMNS:
        rows.append(
            {
                "feature_name": feature,
                "feature_scope": "cross_asset_context_repeated_on_each_prediction_asset_row",
                "feature_family": "cross_asset_regime_context",
                "model_input": "true",
                "definition": definitions[feature],
                "rolling_window_convention": "inclusive_decision_session_close",
                "uses_forward_information": "false",
            }
        )
    return rows


def write_feature_dictionary(path: Path) -> None:
    rows = feature_dictionary_rows()
    fieldnames = [
        "feature_name",
        "feature_scope",
        "feature_family",
        "model_input",
        "definition",
        "rolling_window_convention",
        "uses_forward_information",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_feature_store(path: Path, features: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = features[FEATURE_STORE_COLUMNS].copy()
    ordered.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")


def build_coverage_audit(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in PREDICTION_ASSETS:
        subset = features[features["asset_ticker"] == ticker]
        available = int((subset["feature_availability_status"] == "available").sum())
        missing = int(len(subset) - available)
        rows.append(
            {
                "audit_scope": "ticker",
                "ticker": ticker,
                "feature": "ALL_FEATURES",
                "first_available_decision_date": subset["decision_session_date"].min(),
                "last_available_decision_date": subset["decision_session_date"].max(),
                "available_row_count": available,
                "missing_row_count": missing,
                "missingness_reason": "no_missing_rows"
                if missing == 0
                else "one_or_more_feature_rows_unavailable",
            }
        )
    for feature in FEATURE_COLUMNS:
        values = features[feature]
        available = int(values.notna().sum())
        missing = int(values.isna().sum())
        available_dates = features.loc[values.notna(), "decision_session_date"]
        rows.append(
            {
                "audit_scope": "feature",
                "ticker": "ALL_PREDICTION_ASSETS",
                "feature": feature,
                "first_available_decision_date": available_dates.min() if available else "",
                "last_available_decision_date": available_dates.max() if available else "",
                "available_row_count": available,
                "missing_row_count": missing,
                "missingness_reason": "no_missing_values"
                if missing == 0
                else "feature_value_missing",
            }
        )
    return pd.DataFrame(rows)


def write_coverage_audit(csv_path: Path, md_path: Path, audit: pd.DataFrame) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False, lineterminator="\n")
    missing_tickers = audit[(audit["audit_scope"] == "ticker") & (audit["missing_row_count"] > 0)]
    missing_features = audit[(audit["audit_scope"] == "feature") & (audit["missing_row_count"] > 0)]
    lines = [
        "# GMA-7B Feature Store Coverage Audit V1",
        "",
        *REQUIRED_LANGUAGE,
        "",
        f"Prediction asset count: {len(PREDICTION_ASSETS)}",
        f"Ticker rows with missing features: {len(missing_tickers)}",
        f"Feature columns with missing values: {len(missing_features)}",
        "",
        "## Missingness Summary",
        "",
        "| scope | identifier | missing_row_count | missingness_reason |",
        "| --- | --- | --- | --- |",
    ]
    for _, row in audit[audit["missing_row_count"] > 0].iterrows():
        identifier = row["ticker"] if row["audit_scope"] == "ticker" else row["feature"]
        lines.append(
            f"| {row['audit_scope']} | {identifier} | {row['missing_row_count']} | {row['missingness_reason']} |"
        )
    if not audit["missing_row_count"].sum():
        lines.append("| all | all | 0 | no_missing_values |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_contract_yaml() -> dict[str, Any]:
    return {
        "phase_id": PHASE_ID,
        "feature_store_version": FEATURE_STORE_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "active_cohort": ACTIVE_COHORT,
        "core22_universe": CORE_22_UNIVERSE,
        "prediction_assets": PREDICTION_ASSETS,
        "bil_roles": [
            "benchmark_reference",
            "fallback_asset",
            "excess_return_feature_reference",
        ],
        "decision_schedule": {
            "frequency": "monthly",
            "decision_session": "final available tradable session of each calendar month",
            "signal_observation_cutoff": "decision-session close",
            "decision_timestamp": "deterministic UTC bookkeeping timestamp one hour after New York close",
            "earliest_execution_session": "next available tradable session",
            "target_start_session": "next available tradable session",
        },
        "rolling_window_convention": {
            "all_price_windows_include_decision_session_close": True,
            "return_nd": "decision close divided by close exactly n prior sessions minus one",
            "realised_volatility_nd": "n daily log-return observations ending at decision close",
            "ma_gap_nd": "rolling mean including decision close",
            "drawdown_nd": "maximum adjusted price in inclusive rolling window ending at decision close",
        },
        "features": FEATURE_COLUMNS,
        "metadata": METADATA_COLUMNS,
        "forward_label_window_available_boundary": "scheduling_metadata_only_not_model_input_not_feature_dictionary_hash_input",
        "required_language": REQUIRED_LANGUAGE,
        "scope_boundaries": {
            "forward_target_values_generated": False,
            "forecasts_generated": False,
            "model_fit_performed": False,
            "portfolio_weights_generated": False,
            "performance_calculation_performed": False,
            "paper_paths_generated": False,
            "broker_paths_generated": False,
            "live_paths_generated": False,
        },
    }


def build_contract_markdown() -> str:
    return "\n".join(
        [
            "# GMA-7B Point-in-Time ETF Feature Store Contract V1",
            "",
            *REQUIRED_LANGUAGE,
            "",
            "## Frozen Evidence",
            "",
            "GMA-7B reads the frozen GMA-6B adjusted-price evidence snapshot and validates the snapshot manifest, bundle manifest, normalised hash inventory, Core-22 ticker order, per-file hashes, and complete adjusted-price panel before deriving features.",
            "",
            "## Timing Convention",
            "",
            "The decision session is the final available tradable session of each calendar month. The signal observation cutoff is the decision-session close. The decision timestamp is a deterministic UTC bookkeeping timestamp one hour after the New York close and is not a claim about intraday provider publication timing. The next executable and target-start session is the first subsequent tradable session.",
            "",
            "## Feature Boundary",
            "",
            "Feature columns are exactly the GMA-7B dictionary columns. BIL is used as benchmark, fallback, and excess-return reference, but BIL is not emitted as a prediction-asset row. `forward_label_window_available` is scheduling metadata only and is excluded from the feature dictionary hash and model-input set.",
            "",
            "## Terminal Boundary",
            "",
            "After GMA-7B, the feature-store outputs must be inspected and frozen before labels or models are created. GMA-7C must create labels from the frozen feature-store schedule rather than rebuilding features independently.",
            "",
        ]
    )


def write_contract_files(repo_root: Path) -> None:
    config_path = repo_root / OUTPUT_PATHS["config"]
    docs_path = repo_root / OUTPUT_PATHS["docs"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(build_contract_yaml(), sort_keys=False), encoding="utf-8")
    docs_path.write_text(build_contract_markdown(), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object is not JSON serialisable: {value!r}")


def build_manifest(
    *,
    verification: FrozenInputVerification,
    gma7a_contract_hash: str,
    gma7a_lock_hash: str,
    feature_dictionary_hash: str,
    monthly_feature_store_hash: str,
    features: pd.DataFrame,
) -> dict[str, Any]:
    missing_count = int((features["feature_availability_status"] != "available").sum())
    return {
        "phase_id": PHASE_ID,
        "feature_store_version": FEATURE_STORE_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "gma7a_contract_hash": gma7a_contract_hash,
        "gma7a_lock_hash": gma7a_lock_hash,
        "gma6_snapshot_manifest_hash": verification.gma6_snapshot_manifest_hash,
        "gma6b_data_bundle_manifest_hash": verification.gma6b_data_bundle_manifest_hash,
        "normalised_bundle_hash": verification.normalised_bundle_hash,
        "core22_universe_hash": core22_universe_hash(),
        "feature_dictionary_hash": feature_dictionary_hash,
        "monthly_feature_store_hash": monthly_feature_store_hash,
        "decision_schedule_definition": "monthly final available tradable session; next tradable session execution and target-start metadata",
        "earliest_feature_decision_date": str(features["decision_session_date"].min()),
        "latest_feature_decision_date": str(features["decision_session_date"].max()),
        "prediction_asset_count": len(PREDICTION_ASSETS),
        "decision_date_count": int(features["decision_session_date"].nunique()),
        "feature_row_count": int(len(features)),
        "missing_feature_row_count": missing_count,
        "forward_label_values_generated": False,
        "model_fit_performed": False,
        "performance_calculation_performed": False,
        "target_values_generated": False,
        "forecasts_generated": False,
        "portfolio_weights_generated": False,
        "paper_paths_generated": False,
        "broker_paths_generated": False,
        "live_paths_generated": False,
        "required_language": REQUIRED_LANGUAGE,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def generate_feature_store_files(
    repo_root: Path = Path.cwd(),
    *,
    snapshot_root: Path = SNAPSHOT_ROOT,
    expectations: FrozenHashExpectations = FrozenHashExpectations(),
) -> FeatureStoreResult:
    load_and_validate_gma7a_contract(repo_root)
    _, gma7a_contract_hash = load_and_validate_gma7a_contract(repo_root)
    _, gma7a_lock_hash = load_and_validate_gma7a_lock(repo_root)
    verification = verify_frozen_inputs(snapshot_root, expectations)
    prices = load_adjusted_price_panel(verification)
    core_hash = core22_universe_hash()
    features = build_feature_store(
        prices,
        gma7a_contract_hash=gma7a_contract_hash,
        gma6b_data_bundle_manifest_hash=verification.gma6b_data_bundle_manifest_hash,
        normalised_bundle_hash=verification.normalised_bundle_hash,
        core_hash=core_hash,
    )
    write_contract_files(repo_root)
    write_feature_dictionary(repo_root / OUTPUT_PATHS["feature_dictionary"])
    write_feature_store(repo_root / OUTPUT_PATHS["features"], features)
    audit = build_coverage_audit(features)
    write_coverage_audit(
        repo_root / OUTPUT_PATHS["coverage_csv"],
        repo_root / OUTPUT_PATHS["coverage_md"],
        audit,
    )
    feature_dictionary_hash = sha256_file(repo_root / OUTPUT_PATHS["feature_dictionary"])
    monthly_feature_store_hash = sha256_file(repo_root / OUTPUT_PATHS["features"])
    manifest = build_manifest(
        verification=verification,
        gma7a_contract_hash=gma7a_contract_hash,
        gma7a_lock_hash=gma7a_lock_hash,
        feature_dictionary_hash=feature_dictionary_hash,
        monthly_feature_store_hash=monthly_feature_store_hash,
        features=features,
    )
    write_json(repo_root / OUTPUT_PATHS["manifest"], manifest)
    write_json(repo_root / OUTPUT_PATHS["lock"], manifest | {"lock_status": "frozen_local_v1"})
    return FeatureStoreResult(
        manifest=manifest,
        output_paths={key: repo_root / value for key, value in OUTPUT_PATHS.items()},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the GMA-7B ETF feature store")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--snapshot-root", type=Path, default=SNAPSHOT_ROOT)
    args = parser.parse_args(argv)
    result = generate_feature_store_files(args.repo_root, snapshot_root=args.snapshot_root)
    print(f"phase_id={PHASE_ID}")
    print(f"feature_row_count={result.manifest['feature_row_count']}")
    print(f"decision_date_count={result.manifest['decision_date_count']}")
    print(f"prediction_asset_count={result.manifest['prediction_asset_count']}")
    print(f"earliest_feature_decision_date={result.manifest['earliest_feature_decision_date']}")
    print(f"latest_feature_decision_date={result.manifest['latest_feature_decision_date']}")
    for key, path in sorted(result.output_paths.items()):
        print(f"{key}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
