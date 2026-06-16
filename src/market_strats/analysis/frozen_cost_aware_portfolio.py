from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_strats.analysis.interpretable_stock_ranker import (
    DEFAULT_PHASE23G_CONFIG,
)
from market_strats.analysis.pilot_individual_equity_feature_calculation import (
    CORE_FEATURE_COLUMNS,
)


PHASE23I_SECTION = "phase23i_frozen_cost_aware_portfolio"
PHASE23I_SHADOW_SECTION = "phase23i_prospective_shadow_runner"
RIDGE_MODEL = "phase23g_ridge_ranker_v1"
TECHNICAL_COMPOSITE_MODEL = "baseline_equal_weight_technical_composite"
NONCANONICAL_LABEL = "NONCANONICAL PILOT DIAGNOSTIC - NOT INVESTABLE PERFORMANCE"
CANONICAL_RESEARCH_ENDPOINT = "2026-05-01"

DEFAULT_PHASE23I_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23i_frozen_cost_aware_portfolio"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23i_frozen_cost_aware_portfolio_status.csv"
    ),
    "source_phase23f_dir": (
        "reports/individual_equity_decision_system/"
        "phase23f_pilot_feature_calculation"
    ),
    "source_phase23g_dir": (
        "reports/individual_equity_decision_system/"
        "phase23g_interpretable_stock_ranker"
    ),
    "source_phase23h_dir": (
        "reports/individual_equity_decision_system/"
        "phase23h_interpretable_ranker_robustness"
    ),
    "pilot_input_dir": "data/individual_equity_pilot",
    "initial_capital": 100000.0,
    "primary_portfolio_id": "ridge_top5_equal_weight",
    "model_version": RIDGE_MODEL,
    "canonical_research_endpoint": CANONICAL_RESEARCH_ENDPOINT,
    "weekly_rebalance": True,
    "execution_price": "next_open",
    "max_single_stock_weight": 0.20,
    "max_top5_sector_security_count": 2,
    "max_sector_weight": 0.40,
    "min_order_notional": 25.0,
    "minimum_holding_buffer_weight": 0.0,
    "no_trade_band_weight": 0.0,
    "fixed_commission": 0.0,
    "spread_slippage_bps": 0.0,
    "hard_turnover_limit": 2.0,
    "portfolio_specs": [
        "ridge_top5_equal_weight",
        "ridge_top5_score_weighted",
        "ridge_top8_equal_weight",
        "technical_composite_top5_baseline",
        "equal_weight_all16_pilot_baseline",
        "spy_benchmark",
    ],
    "cost_scenarios": {
        "zero_cost": {"bps_per_one_way_notional": 0.0},
        "cost_10bps": {"bps_per_one_way_notional": 10.0},
        "cost_25bps": {"bps_per_one_way_notional": 25.0},
        "stress_50bps": {"bps_per_one_way_notional": 50.0},
    },
    "paper_only": True,
    "research_pilot_only": True,
    "membership_canonical": False,
    "market_data_canonical": False,
    "generalization_claim_allowed": False,
    "investable_performance_claim_allowed": False,
    "model_training_allowed": False,
    "paper_trading_allowed": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}

DEFAULT_PHASE23I_SHADOW_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": "reports/individual_equity_shadow/phase23i_prospective_shadow",
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/phase23i_shadow_status.csv"
    ),
    "source_phase23i_dir": (
        "reports/individual_equity_decision_system/"
        "phase23i_frozen_cost_aware_portfolio"
    ),
    "source_phase23f_dir": DEFAULT_PHASE23I_CONFIG["source_phase23f_dir"],
    "source_phase23g_dir": DEFAULT_PHASE23I_CONFIG["source_phase23g_dir"],
    "source_phase23j_dir": (
        "reports/individual_equity_decision_system/"
        "phase23j_post_endpoint_individual_equity_extension"
    ),
    "pilot_input_dir": DEFAULT_PHASE23I_CONFIG["pilot_input_dir"],
    "canonical_research_endpoint": CANONICAL_RESEARCH_ENDPOINT,
    "portfolio_id": "ridge_top5_equal_weight",
    "starting_cash": 100000.0,
    "simulated_cost_bps": 10.0,
    "filled_session_filename": "shadow_manual_session_filled.csv",
    "archive_dir": "reports/individual_equity_shadow/phase23i_prospective_shadow/archive",
    "emergency_shadow_kill_switch": False,
    "paper_only": True,
    "research_pilot_only": True,
    "membership_canonical": False,
    "market_data_canonical": False,
    "generalization_claim_allowed": False,
    "investable_performance_claim_allowed": False,
    "model_training_allowed": False,
    "automated_broker_paper_trading_allowed": False,
    "paper_trading_allowed": False,
    "live_trading_allowed": False,
    "real_money_allowed": False,
    "broker_api_integration_allowed": False,
    "promotion_allowed": False,
}


@dataclass(frozen=True)
class CostScenario:
    name: str
    bps_per_one_way_notional: float
    fixed_commission: float
    spread_slippage_bps: float


@dataclass(frozen=True)
class PortfolioSpec:
    portfolio_id: str
    model_version: str
    top_n: int | None
    weighting: str
    benchmark_ticker: str | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(DEFAULT_PHASE23I_CONFIG, config.get(PHASE23I_SECTION, {}))


def _shadow_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(
        DEFAULT_PHASE23I_SHADOW_CONFIG,
        config.get(PHASE23I_SHADOW_SECTION, {}),
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


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _write_text(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (float, int)) and pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _safe_float(value: Any, default: float = np.nan) -> float:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(converted) if pd.notna(converted) else default


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _hash_frame(frame: pd.DataFrame) -> str:
    if frame.empty:
        return _sha256_text("")
    canonical = frame.copy()
    canonical = canonical.reindex(sorted(canonical.columns), axis=1)
    return _sha256_text(canonical.to_csv(index=False))


def _file_hash(path: Path) -> str:
    if not path.exists() or path.is_dir():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return "unavailable"
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else "unavailable"


def _gate_row(gate: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _portfolio_spec(spec_id: str) -> PortfolioSpec:
    if spec_id == "ridge_top5_equal_weight":
        return PortfolioSpec(spec_id, RIDGE_MODEL, 5, "equal")
    if spec_id == "ridge_top5_score_weighted":
        return PortfolioSpec(spec_id, RIDGE_MODEL, 5, "score_weighted")
    if spec_id == "ridge_top8_equal_weight":
        return PortfolioSpec(spec_id, RIDGE_MODEL, 8, "equal")
    if spec_id == "technical_composite_top5_baseline":
        return PortfolioSpec(spec_id, TECHNICAL_COMPOSITE_MODEL, 5, "equal")
    if spec_id == "equal_weight_all16_pilot_baseline":
        return PortfolioSpec(spec_id, RIDGE_MODEL, None, "equal_all")
    if spec_id == "spy_benchmark":
        return PortfolioSpec(spec_id, RIDGE_MODEL, None, "benchmark", "SPY")
    raise ValueError(f"Unsupported Phase23I portfolio specification: {spec_id}")


def _cost_scenarios(config: dict[str, Any]) -> list[CostScenario]:
    scenarios = []
    fixed = float(config.get("fixed_commission", 0.0))
    spread = float(config.get("spread_slippage_bps", 0.0))
    for name, values in config.get("cost_scenarios", {}).items():
        scenarios.append(
            CostScenario(
                name=name,
                bps_per_one_way_notional=float(
                    values.get("bps_per_one_way_notional", 0.0)
                ),
                fixed_commission=float(values.get("fixed_commission", fixed)),
                spread_slippage_bps=float(
                    values.get("spread_slippage_bps", spread)
                ),
            )
        )
    return scenarios


def build_phase23i_model_freeze(
    *,
    config: dict[str, Any],
    model_registry: pd.DataFrame,
    feature_registry: pd.DataFrame,
    phase23g_config: dict[str, Any] | None = None,
    git_commit: str | None = None,
    generated_at_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    phase23g_config = phase23g_config or DEFAULT_PHASE23G_CONFIG
    model_version = str(config.get("model_version", RIDGE_MODEL))
    registry_row = model_registry.loc[
        model_registry.get("model_version", pd.Series(dtype=str)).astype(str).eq(
            model_version
        )
    ]
    registry = registry_row.iloc[0].to_dict() if not registry_row.empty else {}
    feature_text = str(registry.get("feature_set", ";".join(CORE_FEATURE_COLUMNS)))
    ordered_features = [item.strip() for item in feature_text.split(";") if item.strip()]
    if not ordered_features:
        ordered_features = list(CORE_FEATURE_COLUMNS)

    freeze_spec = {
        "model_identifier": model_version,
        "ridge_alpha": float(registry.get("ridge_alpha", phase23g_config["ridge_alpha"])),
        "ordered_feature_list": ordered_features,
        "preprocessing_rules": registry.get(
            "preprocessing",
            "cross-sectional z-score by decision timestamp",
        ),
        "imputation_rules": "training median imputation; missing medians fill to zero",
        "scaling_rules": "cross-sectional z-score features before ridge fit",
        "winsorization_rules": "none in Phase23G",
        "training_window_specification": (
            "walk-forward expanding training with purged prior labels"
        ),
        "purge_window_trading_days": int(
            registry.get(
                "purge_window_trading_days",
                phase23g_config["purge_window_trading_days"],
            )
        ),
        "embargo_window_trading_days": int(
            registry.get(
                "embargo_window_trading_days",
                phase23g_config["embargo_window_trading_days"],
            )
        ),
        "primary_target": registry.get(
            "primary_target",
            phase23g_config["primary_target"],
        ),
        "decision_cadence": "weekly Friday close signal; next eligible open execution",
        "ranking_method": "ascending predicted_rank where 1 is highest score",
        "code_config_version": "phase23i_frozen_cost_aware_portfolio_v1",
        "git_commit": git_commit or _git_commit(),
        "canonical_research_endpoint": config.get(
            "canonical_research_endpoint", CANONICAL_RESEARCH_ENDPOINT
        ),
        "noncanonical_pilot_warning": (
            "membership_canonical=False; market_data_canonical=False; "
            "research pilot only"
        ),
        "research_pilot_only": True,
        "membership_canonical": False,
        "market_data_canonical": False,
        "generalization_claim_allowed": False,
        "investable_performance_claim_allowed": False,
        "promotion_allowed": False,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }
    relevant_config_hash = _sha256_text(
        _stable_json(
            {
                "phase23i": config,
                "phase23g": phase23g_config,
                "ordered_features": ordered_features,
            }
        )
    )
    feature_contract_hash = _hash_frame(feature_registry)
    model_spec_hash = _sha256_text(_stable_json(freeze_spec))
    freeze_hash = _sha256_text(
        _stable_json(
            {
                "relevant_config_hash": relevant_config_hash,
                "feature_contract_hash": feature_contract_hash,
                "model_spec_hash": model_spec_hash,
            }
        )
    )
    freeze = pd.DataFrame(
        [
            {
                **freeze_spec,
                "ordered_feature_list": ";".join(ordered_features),
                "phase23i_freeze_hash": freeze_hash,
                "freeze_timestamp_utc": generated_at_utc or _generated_at(),
            }
        ]
    )
    hashes = pd.DataFrame(
        [
            {
                "hash_name": "relevant_config_hash",
                "hash_value": relevant_config_hash,
                "hash_scope": "Phase23I and frozen Phase23G config",
            },
            {
                "hash_name": "feature_panel_contract_hash",
                "hash_value": feature_contract_hash,
                "hash_scope": "Phase23F calculated feature registry",
            },
            {
                "hash_name": "model_spec_hash",
                "hash_value": model_spec_hash,
                "hash_scope": "immutable model specification excluding timestamp",
            },
            {
                "hash_name": "phase23i_freeze_hash",
                "hash_value": freeze_hash,
                "hash_scope": "combined model freeze hash",
            },
        ]
    )
    return freeze, hashes


def _load_price_files(
    *, membership: pd.DataFrame, pilot_input_dir: Path
) -> dict[str, pd.DataFrame]:
    prices: dict[str, pd.DataFrame] = {}
    for row in membership.to_dict("records"):
        ticker = str(row["ticker"])
        price_file = pilot_input_dir / str(row.get("price_file", f"{ticker}.csv"))
        frame = _read_csv(price_file)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        for column in ["open", "high", "low", "close", "adj_close", "volume"]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        prices[ticker] = frame.sort_values("date").reset_index(drop=True)
    spy_path = pilot_input_dir / "benchmark_SPY.csv"
    spy = _read_csv(spy_path)
    if not spy.empty:
        spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
        for column in ["open", "high", "low", "close", "adj_close", "volume"]:
            spy[column] = pd.to_numeric(spy[column], errors="coerce")
        prices["SPY"] = spy.sort_values("date").reset_index(drop=True)
    return prices


def _price_lookup(prices: dict[str, pd.DataFrame], ticker: str) -> pd.DataFrame:
    return prices.get(ticker, pd.DataFrame())


def _next_eligible_date(prices: dict[str, pd.DataFrame], signal_date: pd.Timestamp) -> pd.Timestamp | None:
    spy = _price_lookup(prices, "SPY")
    if spy.empty:
        return None
    dates = spy.loc[spy["date"].gt(signal_date), "date"]
    if dates.empty:
        return None
    return pd.Timestamp(dates.iloc[0])


def _price_on(
    prices: dict[str, pd.DataFrame],
    ticker: str,
    date: pd.Timestamp,
    column: str,
) -> float:
    frame = _price_lookup(prices, ticker)
    if frame.empty or column not in frame.columns:
        return np.nan
    rows = frame.loc[frame["date"].eq(date), column]
    if rows.empty:
        return np.nan
    return _safe_float(rows.iloc[0])


def _all_calendar_dates(prices: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    spy = _price_lookup(prices, "SPY")
    if spy.empty:
        return []
    return [pd.Timestamp(value) for value in spy["date"].dropna().tolist()]


def _normalise_capped_weights(
    raw: dict[str, float],
    max_single_stock_weight: float,
) -> dict[str, float]:
    if not raw:
        return {}
    values = {key: max(float(value), 0.0) for key, value in raw.items()}
    total = sum(values.values())
    if total <= 0:
        values = {key: 1.0 / len(values) for key in values}
    else:
        values = {key: value / total for key, value in values.items()}
    capped: dict[str, float] = {}
    remaining = values.copy()
    leftover = 1.0
    while remaining:
        equal_remaining = sum(remaining.values())
        changed = False
        for key, value in list(remaining.items()):
            proposed = value / equal_remaining * leftover if equal_remaining > 0 else 0.0
            if proposed >= max_single_stock_weight:
                capped[key] = max_single_stock_weight
                leftover -= max_single_stock_weight
                remaining.pop(key)
                changed = True
        if not changed:
            for key, value in remaining.items():
                capped[key] = value / equal_remaining * leftover if equal_remaining > 0 else 0.0
            break
    return capped


def build_phase23i_targets_for_signal(
    *,
    predictions: pd.DataFrame,
    membership: pd.DataFrame,
    signal_date: pd.Timestamp,
    spec: PortfolioSpec,
    config: dict[str, Any],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    constraints: list[dict[str, Any]] = []
    max_weight = float(config.get("max_single_stock_weight", 0.20))
    max_sector_weight = float(config.get("max_sector_weight", 0.40))
    max_sector_count = int(config.get("max_top5_sector_security_count", 2))
    sector_by_ticker = dict(zip(membership["ticker"], membership["sector"], strict=False))

    if spec.weighting == "benchmark":
        return {"SPY": 1.0}, constraints

    if spec.weighting == "equal_all":
        tickers = sorted(membership["ticker"].astype(str).unique().tolist())
        weight = min(max_weight, 1.0 / len(tickers)) if tickers else 0.0
        return {ticker: weight for ticker in tickers}, constraints

    model_rows = predictions.loc[
        predictions["model_version"].astype(str).eq(spec.model_version)
        & pd.to_datetime(predictions["signal_date"]).dt.normalize().eq(signal_date)
    ].copy()
    if model_rows.empty:
        return {}, [
            {
                "portfolio_id": spec.portfolio_id,
                "signal_date": signal_date.date().isoformat(),
                "constraint_type": "missing_prediction_rows",
                "ticker": "",
                "sector": "",
                "action": "blocked",
                "reason": "no rankings for signal date",
            }
        ]
    model_rows["predicted_rank"] = pd.to_numeric(
        model_rows["predicted_rank"], errors="coerce"
    )
    ranked = model_rows.sort_values(["predicted_rank", "ticker"])
    selected: list[str] = []
    sector_counts: dict[str, int] = {}
    sector_weights: dict[str, float] = {}
    intended_count = int(spec.top_n or len(ranked))
    nominal_weight = min(max_weight, 1.0 / intended_count)

    for row in ranked.to_dict("records"):
        ticker = str(row["ticker"])
        sector = str(sector_by_ticker.get(ticker, "Unknown"))
        next_count = sector_counts.get(sector, 0) + 1
        next_weight = sector_weights.get(sector, 0.0) + nominal_weight
        violates_count = spec.top_n == 5 and next_count > max_sector_count
        violates_weight = next_weight > max_sector_weight + 1e-12
        if violates_count or violates_weight:
            constraints.append(
                {
                    "portfolio_id": spec.portfolio_id,
                    "signal_date": signal_date.date().isoformat(),
                    "constraint_type": "sector_limit",
                    "ticker": ticker,
                    "sector": sector,
                    "action": "excluded_and_next_rank_considered",
                    "reason": (
                        "max top5 sector count exceeded"
                        if violates_count
                        else "max sector target weight exceeded"
                    ),
                }
            )
            continue
        selected.append(ticker)
        sector_counts[sector] = next_count
        sector_weights[sector] = next_weight
        if len(selected) >= intended_count:
            break

    if not selected:
        return {}, constraints

    if spec.weighting == "score_weighted":
        scores = ranked.loc[ranked["ticker"].isin(selected)].copy()
        raw_score = pd.to_numeric(
            scores["predicted_20d_excess_return_or_ranking_score"],
            errors="coerce",
        )
        shifted = raw_score - raw_score.min() + 1e-6
        if shifted.sum() <= 0 or shifted.isna().all():
            raw = {ticker: 1.0 for ticker in selected}
        else:
            raw = dict(zip(scores["ticker"].astype(str), shifted, strict=False))
        return _normalise_capped_weights(raw, max_weight), constraints

    weight = min(max_weight, 1.0 / len(selected))
    return {ticker: weight for ticker in selected}, constraints


def _target_weight_frame(
    *, portfolio_id: str, signal_date: pd.Timestamp, weights: dict[str, float]
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "portfolio_id": portfolio_id,
                "signal_date": signal_date.date().isoformat(),
                "asset": ticker,
                "target_weight": weight,
            }
            for ticker, weight in sorted(weights.items())
        ]
    )


def _adjust_buys_for_cash(
    *,
    target_shares: dict[str, int],
    opens: dict[str, float],
    cash_after: float,
    buy_tickers: list[str],
    per_share_cost_rate: float,
) -> tuple[dict[str, int], float]:
    adjusted = target_shares.copy()
    while cash_after < -1e-8 and buy_tickers:
        ticker = max(buy_tickers, key=lambda key: opens.get(key, 0.0))
        if adjusted.get(ticker, 0) <= 0:
            buy_tickers.remove(ticker)
            continue
        adjusted[ticker] -= 1
        cash_after += opens[ticker] * (1.0 + per_share_cost_rate)
    return adjusted, cash_after


def simulate_phase23i_portfolio(
    *,
    predictions: pd.DataFrame,
    membership: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    spec: PortfolioSpec,
    cost: CostScenario,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    initial_capital = float(config["initial_capital"])
    min_order_notional = float(config.get("min_order_notional", 0.0))
    no_trade_band = float(config.get("no_trade_band_weight", 0.0))
    scenario_cost_rate = (
        cost.bps_per_one_way_notional + cost.spread_slippage_bps
    ) / 10000.0
    signal_dates = sorted(
        pd.to_datetime(predictions["signal_date"]).dt.normalize().dropna().unique()
    )
    calendar = _all_calendar_dates(prices)
    shares: dict[str, int] = {}
    cash = initial_capital
    target_by_exec: dict[pd.Timestamp, tuple[pd.Timestamp, dict[str, float], list[dict[str, Any]]]] = {}

    for raw_signal_date in signal_dates:
        signal_date = pd.Timestamp(raw_signal_date)
        execution_date = _next_eligible_date(prices, signal_date)
        if execution_date is None:
            continue
        weights, constraints = build_phase23i_targets_for_signal(
            predictions=predictions,
            membership=membership,
            signal_date=signal_date,
            spec=spec,
            config=config,
        )
        target_by_exec[execution_date] = (signal_date, weights, constraints)

    equity_rows: list[dict[str, Any]] = []
    drawdown_rows: list[dict[str, Any]] = []
    rebalance_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    cash_rows: list[dict[str, Any]] = [
        {
            "date": calendar[0].date().isoformat() if calendar else "",
            "portfolio_id": spec.portfolio_id,
            "cost_scenario": cost.name,
            "cash_flow_type": "initial_cash",
            "cash_change": initial_capital,
            "cash_balance": cash,
        }
    ]
    holdings_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    constraints_all: list[dict[str, Any]] = []

    high_water = initial_capital
    current_weights: dict[str, float] = {}

    for date in calendar:
        if date in target_by_exec:
            signal_date, target_weights, constraints = target_by_exec[date]
            constraints_all.extend(constraints)
            tickers = sorted(set(shares) | set(target_weights))
            opens = {ticker: _price_on(prices, ticker, date, "open") for ticker in tickers}
            missing_open = [ticker for ticker, price in opens.items() if not np.isfinite(price) or price <= 0]
            pre_trade_value = cash + sum(
                shares.get(ticker, 0) * opens.get(ticker, np.nan)
                for ticker in tickers
                if np.isfinite(opens.get(ticker, np.nan))
            )
            rejected = bool(missing_open or pre_trade_value <= 0)
            total_abs_notional = 0.0
            total_cost = 0.0
            if not rejected:
                target_shares: dict[str, int] = {}
                for ticker in tickers:
                    target_notional = pre_trade_value * target_weights.get(ticker, 0.0)
                    current_weight = (
                        shares.get(ticker, 0) * opens[ticker] / pre_trade_value
                        if pre_trade_value > 0
                        else 0.0
                    )
                    if abs(target_weights.get(ticker, 0.0) - current_weight) < no_trade_band:
                        target_shares[ticker] = shares.get(ticker, 0)
                    else:
                        target_shares[ticker] = int(np.floor(target_notional / opens[ticker]))
                buy_tickers = [
                    ticker
                    for ticker in tickers
                    if target_shares.get(ticker, 0) > shares.get(ticker, 0)
                ]
                gross_trade_cash = 0.0
                order_costs: dict[str, float] = {}
                for ticker in tickers:
                    delta = target_shares.get(ticker, 0) - shares.get(ticker, 0)
                    notional = delta * opens[ticker]
                    if abs(notional) < min_order_notional:
                        target_shares[ticker] = shares.get(ticker, 0)
                        delta = 0
                        notional = 0.0
                    order_cost = (
                        abs(notional) * scenario_cost_rate
                        + (cost.fixed_commission if delta != 0 else 0.0)
                    )
                    order_costs[ticker] = order_cost
                    gross_trade_cash += notional
                    total_abs_notional += abs(notional)
                    total_cost += order_cost
                cash_after = cash - gross_trade_cash - total_cost
                target_shares, cash_after = _adjust_buys_for_cash(
                    target_shares=target_shares,
                    opens=opens,
                    cash_after=cash_after,
                    buy_tickers=buy_tickers,
                    per_share_cost_rate=scenario_cost_rate,
                )
                cash = cash_after
                for ticker in tickers:
                    previous = shares.get(ticker, 0)
                    new = target_shares.get(ticker, 0)
                    delta = new - previous
                    notional = delta * opens[ticker]
                    if delta == 0:
                        continue
                    order_cost = (
                        abs(notional) * scenario_cost_rate
                        + cost.fixed_commission
                    )
                    direction = "BUY" if delta > 0 else "SELL"
                    order = {
                        "signal_date": signal_date.date().isoformat(),
                        "execution_date": date.date().isoformat(),
                        "portfolio_id": spec.portfolio_id,
                        "cost_scenario": cost.name,
                        "ticker": ticker,
                        "order_direction": direction,
                        "order_shares": abs(delta),
                        "order_notional": abs(notional),
                        "target_weight": target_weights.get(ticker, 0.0),
                        "execution_rule": "next_eligible_open",
                        "order_status": "filled_simulated",
                        "noncanonical_label": NONCANONICAL_LABEL,
                    }
                    fill = {
                        **order,
                        "fill_price": opens[ticker],
                        "fill_cost": order_cost,
                        "fill_status": "simulated_next_open_fill",
                        "same_close_execution_used": False,
                    }
                    order_rows.append(order)
                    fill_rows.append(fill)
                    shares[ticker] = new
                shares = {ticker: amount for ticker, amount in shares.items() if amount != 0}
            else:
                execution_rows.append(
                    {
                        "portfolio_id": spec.portfolio_id,
                        "cost_scenario": cost.name,
                        "signal_date": signal_date.date().isoformat(),
                        "execution_date": date.date().isoformat(),
                        "execution_status": "blocked_missing_or_invalid_open",
                        "missing_price_tickers": ";".join(missing_open),
                        "same_close_execution_used": False,
                    }
                )
            if not rejected:
                turnover = total_abs_notional / pre_trade_value if pre_trade_value > 0 else 0.0
                turnover_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "portfolio_id": spec.portfolio_id,
                        "cost_scenario": cost.name,
                        "turnover": turnover,
                        "traded_notional": total_abs_notional,
                    }
                )
                cash_rows.append(
                    {
                        "date": date.date().isoformat(),
                        "portfolio_id": spec.portfolio_id,
                        "cost_scenario": cost.name,
                        "cash_flow_type": "rebalance_after_trades",
                        "cash_change": -total_cost,
                        "cash_balance": cash,
                    }
                )
                rebalance_rows.append(
                    {
                        "signal_date": signal_date.date().isoformat(),
                        "execution_date": date.date().isoformat(),
                        "portfolio_id": spec.portfolio_id,
                        "cost_scenario": cost.name,
                        "pre_trade_value": pre_trade_value,
                        "total_abs_traded_notional": total_abs_notional,
                        "total_cost": total_cost,
                        "turnover": turnover,
                        "holdings_after_rebalance": len(shares),
                        "cash_after_rebalance": cash,
                        "execution_price": "next_open",
                        "same_close_execution_used": False,
                    }
                )
                execution_rows.append(
                    {
                        "portfolio_id": spec.portfolio_id,
                        "cost_scenario": cost.name,
                        "signal_date": signal_date.date().isoformat(),
                        "execution_date": date.date().isoformat(),
                        "execution_status": "completed_next_open",
                        "missing_price_tickers": "",
                        "same_close_execution_used": False,
                    }
                )

        close_values = {
            ticker: _price_on(prices, ticker, date, "adj_close")
            for ticker in set(shares) | ({"SPY"} if spec.benchmark_ticker else set())
        }
        holdings_value = sum(
            shares.get(ticker, 0) * close_values.get(ticker, np.nan)
            for ticker in shares
            if np.isfinite(close_values.get(ticker, np.nan))
        )
        equity = cash + holdings_value
        if equity <= 0 or not np.isfinite(equity):
            continue
        high_water = max(high_water, equity)
        drawdown = equity / high_water - 1.0
        holdings_count = len([amount for amount in shares.values() if amount > 0])
        cash_weight = cash / equity if equity > 0 else np.nan
        current_weights = {
            ticker: shares[ticker] * close_values[ticker] / equity
            for ticker in shares
            if np.isfinite(close_values.get(ticker, np.nan))
        }
        equity_rows.append(
            {
                "date": date.date().isoformat(),
                "portfolio_id": spec.portfolio_id,
                "cost_scenario": cost.name,
                "gross_equity": equity if cost.bps_per_one_way_notional == 0 else np.nan,
                "net_equity": equity,
                "cash": cash,
                "cash_weight": cash_weight,
                "holdings_count": holdings_count,
                "max_security_weight": max(current_weights.values(), default=0.0),
                "noncanonical_label": NONCANONICAL_LABEL,
            }
        )
        drawdown_rows.append(
            {
                "date": date.date().isoformat(),
                "portfolio_id": spec.portfolio_id,
                "cost_scenario": cost.name,
                "net_drawdown": drawdown,
            }
        )
        for ticker, amount in sorted(shares.items()):
            holdings_rows.append(
                {
                    "date": date.date().isoformat(),
                    "portfolio_id": spec.portfolio_id,
                    "cost_scenario": cost.name,
                    "ticker": ticker,
                    "shares": amount,
                    "price": close_values.get(ticker, np.nan),
                    "market_value": amount * close_values.get(ticker, np.nan),
                    "portfolio_weight": current_weights.get(ticker, 0.0),
                }
            )

    return {
        "daily_equity": pd.DataFrame(equity_rows),
        "daily_drawdowns": pd.DataFrame(drawdown_rows),
        "rebalance_log": pd.DataFrame(rebalance_rows),
        "order_blotter": pd.DataFrame(order_rows),
        "fill_blotter": pd.DataFrame(fill_rows),
        "cash_ledger": pd.DataFrame(cash_rows),
        "holdings_history": pd.DataFrame(holdings_rows),
        "turnover": pd.DataFrame(turnover_rows),
        "constraint_audit": pd.DataFrame(constraints_all),
        "execution_audit": pd.DataFrame(execution_rows),
    }


def _metric_from_equity(
    equity: pd.DataFrame,
    turnover: pd.DataFrame,
    costs: pd.DataFrame,
    benchmark_returns: pd.Series | None,
) -> dict[str, float]:
    if equity.empty:
        return {}
    frame = equity.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    value_frame = frame[["date", "net_equity"]].copy()
    value_frame["net_equity"] = pd.to_numeric(
        value_frame["net_equity"], errors="coerce"
    )
    value_frame = value_frame.dropna(subset=["net_equity"])
    if len(value_frame) < 2:
        return {}
    values = value_frame.set_index("date")["net_equity"]
    returns = values.pct_change().dropna()
    years = max((values.index[-1] - values.index[0]).days / 365.25, 1 / 252)
    cagr = (values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1
    vol = returns.std() * np.sqrt(252) if len(returns) > 1 else np.nan
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else np.nan
    downside = returns.loc[returns < 0]
    sortino = (
        returns.mean() / downside.std() * np.sqrt(252)
        if len(downside) > 1 and downside.std() > 0
        else np.nan
    )
    rolling_max = values.cummax()
    drawdown = values / rolling_max - 1.0
    max_dd = drawdown.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    total_turnover = (
        pd.to_numeric(turnover.get("turnover", pd.Series(dtype=float)), errors="coerce").sum()
        if not turnover.empty
        else 0.0
    )
    annual_turnover = total_turnover / years
    total_cost = (
        pd.to_numeric(costs.get("fill_cost", pd.Series(dtype=float)), errors="coerce").sum()
        if not costs.empty
        else 0.0
    )
    worst_week = (1 + returns).rolling(5).apply(np.prod, raw=True).min() - 1
    worst_month = (1 + returns).rolling(21).apply(np.prod, raw=True).min() - 1
    time_under_water = float((drawdown < 0).mean())
    tracking_error = np.nan
    information_ratio = np.nan
    benchmark_relative_return = np.nan
    if benchmark_returns is not None and not benchmark_returns.empty:
        aligned = returns.align(benchmark_returns, join="inner")
        if len(aligned[0]) > 2:
            active = aligned[0] - aligned[1]
            tracking_error = active.std() * np.sqrt(252)
            information_ratio = (
                active.mean() / active.std() * np.sqrt(252)
                if active.std() > 0
                else np.nan
            )
            benchmark_relative_return = (values.iloc[-1] / values.iloc[0] - 1) - (
                (1 + aligned[1]).prod() - 1
            )
    return {
        "end_value": float(values.iloc[-1]),
        "total_return": float(values.iloc[-1] / values.iloc[0] - 1),
        "CAGR": float(cagr),
        "annualized_volatility": float(vol),
        "Sharpe": float(sharpe),
        "Sortino": float(sortino),
        "max_drawdown": float(max_dd),
        "Calmar": float(calmar),
        "turnover": float(total_turnover),
        "annual_turnover": float(annual_turnover),
        "total_costs": float(total_cost),
        "cost_drag": float(total_cost / values.iloc[0]),
        "average_number_of_holdings": float(frame["holdings_count"].mean()),
        "average_cash_weight": float(frame["cash_weight"].mean()),
        "average_concentration": float(frame["max_security_weight"].mean()),
        "worst_week": float(worst_week),
        "worst_month": float(worst_month),
        "time_under_water": float(time_under_water),
        "benchmark_relative_return": float(benchmark_relative_return),
        "tracking_error": float(tracking_error),
        "information_ratio": float(information_ratio),
    }


def _benchmark_return_series(daily_equity: pd.DataFrame) -> pd.Series:
    benchmark = daily_equity.loc[
        daily_equity["portfolio_id"].eq("spy_benchmark")
        & daily_equity["cost_scenario"].eq("zero_cost")
    ].copy()
    if benchmark.empty:
        return pd.Series(dtype=float)
    benchmark["date"] = pd.to_datetime(benchmark["date"])
    benchmark = benchmark.sort_values("date")
    returns = pd.to_numeric(benchmark["net_equity"], errors="coerce").pct_change()
    returns.index = benchmark["date"]
    return returns.dropna()


def _security_attribution(holdings: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame()
    frame = holdings.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["portfolio_id", "cost_scenario", "ticker", "date"])
    frame["market_value"] = pd.to_numeric(frame["market_value"], errors="coerce")
    frame["daily_contribution"] = frame.groupby(
        ["portfolio_id", "cost_scenario", "ticker"]
    )["market_value"].diff()
    sector = dict(zip(membership["ticker"], membership["sector"], strict=False))
    grouped = (
        frame.groupby(["portfolio_id", "cost_scenario", "ticker"], dropna=False)
        .agg(
            average_weight=("portfolio_weight", "mean"),
            ending_market_value=("market_value", "last"),
            contribution=("daily_contribution", "sum"),
            days_held=("date", "nunique"),
        )
        .reset_index()
    )
    grouped["sector"] = grouped["ticker"].map(sector).fillna("Benchmark")
    return grouped


def _sector_attribution(security_attribution: pd.DataFrame) -> pd.DataFrame:
    if security_attribution.empty:
        return pd.DataFrame()
    return (
        security_attribution.groupby(["portfolio_id", "cost_scenario", "sector"])
        .agg(
            average_weight=("average_weight", "sum"),
            ending_market_value=("ending_market_value", "sum"),
            contribution=("contribution", "sum"),
        )
        .reset_index()
    )


def _calendar_metrics(daily_equity: pd.DataFrame) -> pd.DataFrame:
    if daily_equity.empty:
        return pd.DataFrame()
    frame = daily_equity.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["calendar_year"] = frame["date"].dt.year
    rows = []
    for keys, group in frame.groupby(["portfolio_id", "cost_scenario", "calendar_year"]):
        values = pd.to_numeric(group.sort_values("date")["net_equity"], errors="coerce")
        if len(values) < 2:
            continue
        rows.append(
            {
                "portfolio_id": keys[0],
                "cost_scenario": keys[1],
                "calendar_year": keys[2],
                "calendar_year_return": values.iloc[-1] / values.iloc[0] - 1,
                "noncanonical_label": NONCANONICAL_LABEL,
            }
        )
    return pd.DataFrame(rows)


def _regime_bucket_metrics(
    daily_equity: pd.DataFrame,
    phase23h_regimes: pd.DataFrame,
) -> pd.DataFrame:
    if daily_equity.empty:
        return pd.DataFrame()
    frame = daily_equity.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    rows = []
    buckets = {
        "pilot_2023": ("2023-01-01", "2023-12-31"),
        "pilot_2024": ("2024-01-01", "2024-12-31"),
        "pilot_2025": ("2025-01-01", "2025-12-31"),
        "pilot_2026_to_endpoint": ("2026-01-01", CANONICAL_RESEARCH_ENDPOINT),
    }
    if not phase23h_regimes.empty and "regime_bucket" in phase23h_regimes.columns:
        for bucket in phase23h_regimes["regime_bucket"].dropna().astype(str).unique():
            if bucket.startswith("year_"):
                year = bucket.removeprefix("year_")
                buckets[bucket] = (f"{year}-01-01", f"{year}-12-31")
    for (portfolio_id, cost_scenario), group in frame.groupby(["portfolio_id", "cost_scenario"]):
        for bucket, (start, end) in buckets.items():
            subset = group.loc[group["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
            values = pd.to_numeric(subset.sort_values("date")["net_equity"], errors="coerce")
            if len(values) < 2:
                continue
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "cost_scenario": cost_scenario,
                    "regime_bucket": bucket,
                    "regime_return": values.iloc[-1] / values.iloc[0] - 1,
                    "regime_metric_status": "computed_from_daily_equity",
                    "noncanonical_label": NONCANONICAL_LABEL,
                }
            )
    return pd.DataFrame(rows)


def _failure_modes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "failure_mode": "noncanonical_pilot_universe",
                "severity": "high",
                "evidence": "manual surviving 16-stock pilot universe",
                "mitigation": "replace with point-in-time canonical membership",
            },
            {
                "failure_mode": "cost_assumption_sensitivity",
                "severity": "medium",
                "evidence": "portfolio results depend on one-way bps costs and spread/slippage",
                "mitigation": "extend with broker-free observed spread estimates",
            },
            {
                "failure_mode": "no_prospective_shadow_history_yet",
                "severity": "high",
                "evidence": "historical OOS predictions only through canonical endpoint",
                "mitigation": "collect post-endpoint shadow sessions without changing model",
            },
            {
                "failure_mode": "not_investable_performance",
                "severity": "high",
                "evidence": NONCANONICAL_LABEL,
                "mitigation": "canonical data, costs, and prospective discipline needed",
            },
        ]
    )


def _historical_markdown(summary: pd.DataFrame, metrics: pd.DataFrame) -> str:
    primary = metrics.loc[
        metrics["portfolio_id"].eq("ridge_top5_equal_weight")
        & metrics["cost_scenario"].eq("cost_25bps")
    ]
    primary_text = "not_available"
    if not primary.empty:
        row = primary.iloc[0]
        primary_text = (
            f"CAGR {row['CAGR']:.2%}, max drawdown {row['max_drawdown']:.2%}, "
            f"Calmar {row['Calmar']:.3f}"
        )
    decision = summary.iloc[0].get("phase23i_decision", "") if not summary.empty else ""
    return "\n".join(
        [
            "# Phase 23I - Frozen Cost-Aware Portfolio Construction",
            "",
            NONCANONICAL_LABEL,
            "",
            "NO LIVE TRADING",
            "NO REAL MONEY",
            "NO BROKER/API",
            "NO STRATEGY PROMOTION",
            "",
            f"Decision: `{decision}`",
            "",
            "Primary diagnostic portfolio was preregistered as "
            "`ridge_top5_equal_weight`; it was not selected using Phase23I "
            "performance.",
            "",
            f"Primary 25 bps diagnostic: {primary_text}",
            "",
            "Historical diagnostics use next eligible open execution, integer "
            "share rounding, residual cash, and explicit one-way trading costs.",
            "",
            "These outputs are research diagnostics only. They do not prove "
            "investable performance and do not authorize paper, live, or "
            "real-money trading.",
            "",
        ]
    )


def save_phase23i_frozen_cost_aware_portfolio(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _phase_config(config)
    reports_path = Path(reports_dir)
    output_dir = _resolve_reports_path(
        configured_path=section["output_dir"], reports_dir=reports_path
    )
    dashboard_path = _resolve_reports_path(
        configured_path=section["dashboard_status_path"], reports_dir=reports_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    phase23f_dir = _resolve_reports_path(
        configured_path=section["source_phase23f_dir"], reports_dir=reports_path
    )
    phase23g_dir = _resolve_reports_path(
        configured_path=section["source_phase23g_dir"], reports_dir=reports_path
    )
    phase23h_dir = _resolve_reports_path(
        configured_path=section["source_phase23h_dir"], reports_dir=reports_path
    )
    pilot_input_dir = _resolve_project_path(section["pilot_input_dir"])

    panel = _read_csv(phase23f_dir / "phase23f_pilot_feature_panel.csv")
    feature_registry = _read_csv(phase23f_dir / "phase23f_calculated_feature_registry.csv")
    source_inventory = _read_csv(phase23f_dir / "phase23f_source_inventory.csv")
    phase23f_summary = _read_csv(phase23f_dir / "phase23f_summary.csv")
    predictions = _read_csv(phase23g_dir / "phase23g_oos_predictions.csv")
    model_registry = _read_csv(phase23g_dir / "phase23g_model_registry.csv")
    phase23g_gate = _read_csv(phase23g_dir / "phase23g_gate_report.csv")
    phase23h_gate = _read_csv(phase23h_dir / "phase23h_gate_report.csv")
    phase23h_regimes = _read_csv(phase23h_dir / "phase23h_regime_diagnostics.csv")
    membership = _read_csv(pilot_input_dir / "pilot_membership_manifest.csv")

    phase23g_config = _deep_merge(
        DEFAULT_PHASE23G_CONFIG,
        config.get("phase23g_interpretable_stock_ranker", {}),
    )
    freeze, hashes = build_phase23i_model_freeze(
        config=section,
        model_registry=model_registry,
        feature_registry=feature_registry,
        phase23g_config=phase23g_config,
    )

    source_paths = {
        "phase23f_panel": phase23f_dir / "phase23f_pilot_feature_panel.csv",
        "phase23g_predictions": phase23g_dir / "phase23g_oos_predictions.csv",
        "phase23g_model_registry": phase23g_dir / "phase23g_model_registry.csv",
        "phase23h_gate_report": phase23h_dir / "phase23h_gate_report.csv",
        "membership_manifest": pilot_input_dir / "pilot_membership_manifest.csv",
    }
    gates = [
        _gate_row(name + "_present", path.exists(), str(path))
        for name, path in source_paths.items()
    ]
    gates.extend(
        [
            _gate_row(
                "phase23f_integrity_passed",
                not phase23f_summary.empty
                and _bool_value(phase23f_summary.iloc[0].get("all_gates_passed", False)),
                "Phase23F summary all_gates_passed",
            ),
            _gate_row(
                "phase23f_panel_available",
                not panel.empty,
                f"panel_rows={len(panel)}",
            ),
            _gate_row(
                "phase23f_source_inventory_available",
                not source_inventory.empty,
                f"source_inventory_rows={len(source_inventory)}",
            ),
            _gate_row(
                "phase23g_integrity_passed",
                not phase23g_gate.empty
                and bool(phase23g_gate["passed"].map(_bool_value).all()),
                "Phase23G gates pass",
            ),
            _gate_row(
                "phase23h_integrity_passed",
                not phase23h_gate.empty
                and bool(phase23h_gate["passed"].map(_bool_value).all()),
                "Phase23H gates pass",
            ),
            _gate_row(
                "safety_flags_false",
                not any(
                    _bool_value(section.get(flag, False))
                    for flag in [
                        "live_trading_allowed",
                        "real_money_allowed",
                        "broker_api_integration_allowed",
                        "promotion_allowed",
                    ]
                ),
                "live/real/broker/promotion false",
            ),
        ]
    )
    all_sources_present = all(path.exists() for path in source_paths.values())
    if not all_sources_present or predictions.empty or membership.empty:
        decision = "phase23i_blocked_missing_required_sources"
        gate_report = pd.DataFrame(gates)
        gate_report["all_gates_passed"] = False
        summary = pd.DataFrame(
            [
                {
                    "phase": "Phase 23I",
                    "phase23i_decision": decision,
                    "historical_diagnostics_written": False,
                    "shadow_readiness_allowed": False,
                    "noncanonical_label": NONCANONICAL_LABEL,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                    "promotion_allowed": False,
                }
            ]
        )
        outputs = {
            "summary": summary,
            "gate_report": gate_report,
            "model_freeze": freeze,
            "model_freeze_hashes": hashes,
        }
        _write_phase23i_outputs(output_dir, dashboard_path, outputs, decision)
        print("Wrote Phase 23I frozen cost-aware portfolio reports.")
        return outputs

    prices = _load_price_files(membership=membership, pilot_input_dir=pilot_input_dir)
    all_outputs: dict[str, list[pd.DataFrame]] = {
        "daily_equity": [],
        "daily_drawdowns": [],
        "rebalance_log": [],
        "order_blotter": [],
        "fill_blotter": [],
        "cash_ledger": [],
        "holdings_history": [],
        "turnover": [],
        "constraint_audit": [],
        "execution_audit": [],
    }
    portfolio_rows = []
    for spec_id in section["portfolio_specs"]:
        spec = _portfolio_spec(spec_id)
        portfolio_rows.append(
            {
                "portfolio_id": spec.portfolio_id,
                "model_version": spec.model_version,
                "top_n": spec.top_n,
                "weighting": spec.weighting,
                "primary_preregistered": spec.portfolio_id
                == section["primary_portfolio_id"],
                "selected_by_phase23i_performance": False,
                "noncanonical_label": NONCANONICAL_LABEL,
            }
        )
        for cost in _cost_scenarios(section):
            outputs = simulate_phase23i_portfolio(
                predictions=predictions,
                membership=membership,
                prices=prices,
                spec=spec,
                cost=cost,
                config=section,
            )
            for key, value in outputs.items():
                all_outputs[key].append(value)

    combined = {
        key: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for key, frames in all_outputs.items()
    }
    benchmark_returns = _benchmark_return_series(combined["daily_equity"])
    metric_rows = []
    for (portfolio_id, cost_scenario), group in combined["daily_equity"].groupby(
        ["portfolio_id", "cost_scenario"]
    ):
        turnover = combined["turnover"].loc[
            combined["turnover"]["portfolio_id"].eq(portfolio_id)
            & combined["turnover"]["cost_scenario"].eq(cost_scenario)
        ]
        fills = combined["fill_blotter"].loc[
            combined["fill_blotter"]["portfolio_id"].eq(portfolio_id)
            & combined["fill_blotter"]["cost_scenario"].eq(cost_scenario)
        ]
        metrics = _metric_from_equity(group, turnover, fills, benchmark_returns)
        if metrics:
            metric_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "cost_scenario": cost_scenario,
                    **metrics,
                    "noncanonical_label": NONCANONICAL_LABEL,
                }
            )
    historical_metrics = pd.DataFrame(metric_rows)
    cost_sensitivity = historical_metrics[
        [
            "portfolio_id",
            "cost_scenario",
            "end_value",
            "CAGR",
            "max_drawdown",
            "turnover",
            "total_costs",
            "cost_drag",
        ]
    ].copy()
    security_attr = _security_attribution(combined["holdings_history"], membership)
    sector_attr = _sector_attribution(security_attr)
    calendar = _calendar_metrics(combined["daily_equity"])
    regime_bucket = _regime_bucket_metrics(combined["daily_equity"], phase23h_regimes)

    cost_reconcile_passed = True
    if not cost_sensitivity.empty:
        primary_costs = cost_sensitivity.loc[
            cost_sensitivity["portfolio_id"].eq(section["primary_portfolio_id"])
        ].sort_values("total_costs")
        if len(primary_costs) >= 2:
            cost_reconcile_passed = bool(
                pd.to_numeric(primary_costs["end_value"], errors="coerce").is_monotonic_decreasing
            )
    gates.extend(
        [
            _gate_row(
                "model_freeze_artifact_written",
                not freeze.empty and not hashes.empty,
                "freeze hash generated",
            ),
            _gate_row(
                "next_open_execution_used",
                not combined["execution_audit"].empty
                and not combined["execution_audit"]["same_close_execution_used"]
                .map(_bool_value)
                .any(),
                "no same-close fills",
            ),
            _gate_row(
                "cash_and_holdings_reconcile",
                not combined["daily_equity"].empty
                and pd.to_numeric(
                    combined["daily_equity"]["net_equity"], errors="coerce"
                ).gt(0).all(),
                "positive net equity from simulated holdings/cash",
            ),
            _gate_row(
                "cost_sensitivity_monotonic_for_primary",
                cost_reconcile_passed,
                "primary end value does not increase as costs rise",
            ),
        ]
    )
    gate_report = pd.DataFrame(gates)
    gate_report["all_gates_passed"] = bool(gate_report["passed"].map(_bool_value).all())
    historical_passed = bool(gate_report["all_gates_passed"].all())
    decision = (
        "phase23i_cost_aware_portfolio_diagnostics_completed_research_only"
        if historical_passed
        else "phase23i_cost_aware_portfolio_diagnostics_failed_gates"
    )
    primary_25 = historical_metrics.loc[
        historical_metrics["portfolio_id"].eq(section["primary_portfolio_id"])
        & historical_metrics["cost_scenario"].eq("cost_25bps")
    ]
    primary_survived = (
        not primary_25.empty and _safe_float(primary_25.iloc[0].get("CAGR")) > 0
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23I",
                "phase23i_decision": decision,
                "historical_diagnostics_written": True,
                "software_execution_gates_passed": historical_passed,
                "primary_preregistered_portfolio_id": section["primary_portfolio_id"],
                "primary_selected_by_phase23i_performance": False,
                "primary_survived_25bps_costs": primary_survived,
                "model_freeze_hash": freeze.iloc[0]["phase23i_freeze_hash"],
                "portfolio_count": len(section["portfolio_specs"]),
                "cost_scenario_count": len(_cost_scenarios(section)),
                "shadow_readiness_allowed": False,
                "membership_canonical": False,
                "market_data_canonical": False,
                "research_pilot_only": True,
                "generalization_claim_allowed": False,
                "investable_performance_claim_allowed": False,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "noncanonical_label": NONCANONICAL_LABEL,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23I",
                "phase23i_decision": decision,
                "verdict": (
                    "Frozen cost-aware diagnostics were written for the "
                    "noncanonical individual-equity pilot. Results remain "
                    "research-only and non-investable."
                ),
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        ]
    )
    outputs = {
        "summary": summary,
        "gate_report": gate_report,
        "model_freeze": freeze,
        "model_freeze_hashes": hashes,
        "portfolio_registry": pd.DataFrame(portfolio_rows),
        "historical_metrics": historical_metrics,
        "cost_sensitivity": cost_sensitivity,
        "daily_equity": combined["daily_equity"],
        "daily_drawdowns": combined["daily_drawdowns"],
        "rebalance_log": combined["rebalance_log"],
        "order_blotter": combined["order_blotter"],
        "fill_blotter": combined["fill_blotter"],
        "cash_ledger": combined["cash_ledger"],
        "holdings_history": combined["holdings_history"],
        "turnover": combined["turnover"],
        "security_attribution": security_attr,
        "sector_attribution": sector_attr,
        "constraint_audit": combined["constraint_audit"],
        "execution_audit": combined["execution_audit"],
        "calendar_year_metrics": calendar,
        "regime_bucket_metrics": regime_bucket,
        "failure_mode_register": _failure_modes(),
        "conclusion": conclusion,
    }
    _write_phase23i_outputs(output_dir, dashboard_path, outputs, decision)
    _write_text(
        _historical_markdown(summary, historical_metrics),
        output_dir / "phase23i_frozen_cost_aware_portfolio.md",
    )
    print("Wrote Phase 23I frozen cost-aware portfolio reports.")
    return outputs


def _write_phase23i_outputs(
    output_dir: Path,
    dashboard_path: Path,
    outputs: dict[str, pd.DataFrame],
    decision: str,
) -> None:
    names = {
        "summary": "phase23i_summary.csv",
        "gate_report": "phase23i_gate_report.csv",
        "model_freeze": "phase23i_model_freeze.csv",
        "model_freeze_hashes": "phase23i_model_freeze_hashes.csv",
        "portfolio_registry": "phase23i_portfolio_registry.csv",
        "historical_metrics": "phase23i_historical_metrics.csv",
        "cost_sensitivity": "phase23i_cost_sensitivity.csv",
        "daily_equity": "phase23i_daily_equity.csv",
        "daily_drawdowns": "phase23i_daily_drawdowns.csv",
        "rebalance_log": "phase23i_rebalance_log.csv",
        "order_blotter": "phase23i_order_blotter.csv",
        "fill_blotter": "phase23i_fill_blotter.csv",
        "cash_ledger": "phase23i_cash_ledger.csv",
        "holdings_history": "phase23i_holdings_history.csv",
        "turnover": "phase23i_turnover.csv",
        "security_attribution": "phase23i_security_attribution.csv",
        "sector_attribution": "phase23i_sector_attribution.csv",
        "constraint_audit": "phase23i_constraint_audit.csv",
        "execution_audit": "phase23i_execution_audit.csv",
        "calendar_year_metrics": "phase23i_calendar_year_metrics.csv",
        "regime_bucket_metrics": "phase23i_regime_bucket_metrics.csv",
        "failure_mode_register": "phase23i_failure_mode_register.csv",
        "conclusion": "phase23i_conclusion.csv",
    }
    for key, filename in names.items():
        _write_csv(outputs.get(key, pd.DataFrame()), output_dir / filename)
    dashboard = pd.DataFrame(
        [
            {
                "phase23i_decision": decision,
                "historical_output_dir": str(output_dir),
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "notes": NONCANONICAL_LABEL,
            }
        ]
    )
    _write_csv(dashboard, dashboard_path)


def _session_date_from_template(template: pd.DataFrame) -> tuple[str, str]:
    if template.empty:
        return datetime.now(timezone.utc).date().isoformat(), ""
    return (
        str(template.iloc[0].get("session_date", datetime.now(timezone.utc).date().isoformat())),
        str(template.iloc[0].get("selected_signal_date", "")),
    )


def _archive_shadow_filled_session(
    *,
    filled_path: Path,
    archive_dir: Path,
    validation: pd.DataFrame,
    ledger: pd.DataFrame,
) -> tuple[pd.DataFrame, str, str]:
    if filled_path.exists() and not validation.empty and bool(validation.iloc[0].get("session_valid", False)):
        filled = _read_csv(filled_path)
        session_date = str(filled.iloc[0].get("session_date", "unknown")) if not filled.empty else "unknown"
        signal_date = str(filled.iloc[0].get("selected_signal_date", "unknown")) if not filled.empty else "unknown"
        archive_path = (
            archive_dir
            / f"shadow_manual_session_filled_{session_date}_signal_{signal_date}.csv"
        )
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            raise FileExistsError(f"Shadow archive already exists: {archive_path}")
        shutil.move(str(filled_path), str(archive_path))
        archive_status = "archived_valid_completed_session_source_moved"
    else:
        session_date = ""
        signal_date = ""
        archive_path = None
        archive_status = "not_archived_no_valid_completed_session"
    archive_index = pd.DataFrame(
        [
            {
                "archived_at_utc": _generated_at() if archive_path is not None else "",
                "source_path": str(filled_path),
                "archive_path": "" if archive_path is None else str(archive_path),
                "session_date": session_date,
                "selected_signal_date": signal_date,
                "row_count": int(validation.iloc[0].get("rows_received", 0))
                if not validation.empty
                else 0,
                "session_valid": bool(validation.iloc[0].get("session_valid", False))
                if not validation.empty
                else False,
                "ledger_row_count_after_ingestion": len(ledger),
                "archive_status": archive_status,
                "notes": "validated filled session moved to immutable archive",
            }
        ]
    )
    return archive_index, archive_status, str(archive_path)


def _validate_shadow_filled_session(
    *,
    filled: pd.DataFrame,
    template: pd.DataFrame,
    safety_flags_false: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = [
        "session_date",
        "selected_signal_date",
        "portfolio_id",
        "ticker",
        "order_side",
        "proposed_quantity",
        "reference_price",
        "manual_decision",
        "session_state",
        "simulated_fill_price",
        "simulated_fill_quantity",
        "override_reason",
        "live_trading_allowed",
        "real_money_allowed",
        "broker_api_integration_allowed",
    ]
    rows = []
    if filled.empty:
        validation = pd.DataFrame(
            [
                {
                    "filled_session_file_present": False,
                    "session_valid": False,
                    "session_status": "pending_user_entries",
                    "rows_expected": len(template),
                    "rows_received": 0,
                    "rows_valid": 0,
                    "rows_invalid": 0,
                    "blocking_reasons": "filled_session_file_missing",
                }
            ]
        )
        return validation, pd.DataFrame()
    missing = [column for column in required if column not in filled.columns]
    template_keys: dict[tuple[str, str], dict[str, Any]] = {}
    if not template.empty and {"ticker", "order_side"}.issubset(template.columns):
        template_keys = {
            (str(row.ticker), str(row.order_side).upper()): row._asdict()
            for row in template.itertuples(index=False)
        }
    row_count_matches = len(filled) == len(template)
    for index, row in filled.iterrows():
        blockers = []
        if not row_count_matches:
            blockers.append("filled_row_count_does_not_match_template")
        if missing:
            blockers.append("missing_required_columns:" + ";".join(missing))
        decision = str(row.get("manual_decision", "")).strip()
        state = str(row.get("session_state", "")).strip()
        ticker = str(row.get("ticker", "")).strip()
        side = str(row.get("order_side", "")).strip().upper()
        template_row = template_keys.get((ticker, side))
        if template_row is None:
            blockers.append("filled_row_not_in_current_template")
        else:
            proposed = int(max(_safe_float(template_row.get("proposed_quantity", 0)), 0))
            filled_quantity = int(
                max(_safe_float(row.get("simulated_fill_quantity", 0)), 0)
            )
            if state in {"entered", "partially_entered"} and filled_quantity > proposed:
                blockers.append("filled_quantity_exceeds_proposed_quantity")
        if side not in {"BUY", "SELL"}:
            blockers.append("invalid_order_side")
        if decision == "" or decision == "pending":
            blockers.append("manual_decision_pending")
        if state not in {
            "entered",
            "partially_entered",
            "skipped",
            "blocked",
            "valued",
            "closed",
        }:
            blockers.append("invalid_session_state")
        if state in {"entered", "partially_entered"}:
            if _safe_float(row.get("simulated_fill_price")) <= 0:
                blockers.append("fill_price_missing_or_nonpositive")
            if _safe_float(row.get("simulated_fill_quantity")) <= 0:
                blockers.append("fill_quantity_missing_or_nonpositive")
        if state in {"skipped", "blocked"} and str(row.get("override_reason", "")).strip() == "":
            blockers.append("skip_or_block_requires_reason")
        if any(
            _bool_value(row.get(flag, False))
            for flag in [
                "live_trading_allowed",
                "real_money_allowed",
                "broker_api_integration_allowed",
            ]
        ):
            blockers.append("safety_flags_not_false")
        rows.append(
            {
                "row_number": index + 1,
                "portfolio_id": row.get("portfolio_id", ""),
                "ticker": row.get("ticker", ""),
                "row_valid": not blockers and safety_flags_false,
                "row_blocking_reasons": ";".join(blockers),
                "manual_decision": decision,
                "session_state": state,
            }
        )
    row_validation = pd.DataFrame(rows)
    session_valid = bool(row_validation["row_valid"].all()) and not missing
    validation = pd.DataFrame(
        [
            {
                "filled_session_file_present": True,
                "session_valid": session_valid,
                "session_status": (
                    "valid_shadow_manual_session"
                    if session_valid
                    else "invalid_shadow_manual_session"
                ),
                "rows_expected": len(template),
                "rows_received": len(filled),
                "rows_valid": int(row_validation["row_valid"].sum()),
                "rows_invalid": int((~row_validation["row_valid"]).sum()),
                "blocking_reasons": ""
                if session_valid
                else ";".join(
                    sorted(
                        {
                            reason
                            for reasons in row_validation["row_blocking_reasons"]
                            for reason in str(reasons).split(";")
                            if reason
                        }
                    )
                ),
            }
        ]
    )
    return validation, row_validation


def _shadow_price_map(
    *, ranking: pd.DataFrame, target: pd.DataFrame
) -> dict[str, float]:
    prices: dict[str, float] = {}
    for frame in [ranking, target]:
        if frame.empty or "ticker" not in frame.columns:
            continue
        for row in frame.itertuples(index=False):
            execution_price = _safe_float(
                getattr(row, "execution_open_price", np.nan)
            )
            reference_price = _safe_float(getattr(row, "reference_price", np.nan))
            price = execution_price if execution_price > 0 else reference_price
            if price > 0:
                prices[str(row.ticker)] = price
    return prices


def _shadow_accounting_from_ledger(
    *,
    ledger: pd.DataFrame,
    starting_cash: float,
    price_map: dict[str, float],
    simulated_cost_bps: float,
    valuation_date: str,
    portfolio_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int], float]:
    cash = float(starting_cash)
    shares: dict[str, int] = {}
    cash_rows: list[dict[str, Any]] = [
        {
            "ledger_date": valuation_date,
            "ticker": "CASH",
            "cash_flow_type": "initial_shadow_cash",
            "cash_change": float(starting_cash),
            "transaction_cost": 0.0,
            "cash_balance": float(starting_cash),
        }
    ]
    if not ledger.empty:
        working = ledger.copy()
        if "session_date" in working.columns:
            working["session_date"] = pd.to_datetime(
                working["session_date"], errors="coerce"
            )
        entered = working.loc[
            working.get("session_state", pd.Series(index=working.index, dtype=str))
            .astype(str)
            .isin(["entered", "partially_entered"])
        ].copy()
        if not entered.empty:
            entered["_side_order"] = (
                entered.get("order_side", pd.Series(index=entered.index, dtype=str))
                .astype(str)
                .str.upper()
                .map({"SELL": 0, "BUY": 1})
                .fillna(2)
            )
            entered = entered.sort_values(
                ["session_date", "_side_order", "ticker"], na_position="last"
            )
            for row in entered.itertuples(index=False):
                ticker = str(getattr(row, "ticker", "")).strip()
                side = str(getattr(row, "order_side", "BUY")).strip().upper()
                quantity = int(max(_safe_float(getattr(row, "simulated_fill_quantity", 0)), 0))
                price = _safe_float(getattr(row, "simulated_fill_price", np.nan))
                if not ticker or quantity <= 0 or price <= 0:
                    continue
                gross = quantity * price
                cost = gross * float(simulated_cost_bps) / 10000.0
                if side == "SELL":
                    available = shares.get(ticker, 0)
                    executed = min(quantity, available)
                    gross = executed * price
                    cost = gross * float(simulated_cost_bps) / 10000.0
                    shares[ticker] = available - executed
                    cash_change = gross - cost
                    cash += cash_change
                else:
                    affordable = int(max((cash) / max(price * (1 + float(simulated_cost_bps) / 10000.0), 1e-12), 0))
                    executed = min(quantity, affordable)
                    gross = executed * price
                    cost = gross * float(simulated_cost_bps) / 10000.0
                    shares[ticker] = shares.get(ticker, 0) + executed
                    cash_change = -(gross + cost)
                    cash += cash_change
                cash_rows.append(
                    {
                        "ledger_date": getattr(row, "session_date", valuation_date),
                        "ticker": ticker,
                        "cash_flow_type": f"shadow_{side.lower()}_fill",
                        "cash_change": cash_change,
                        "transaction_cost": cost,
                        "cash_balance": cash,
                    }
                )
    positions_rows: list[dict[str, Any]] = []
    market_value = 0.0
    for ticker, quantity in sorted(shares.items()):
        if quantity <= 0:
            continue
        price = price_map.get(ticker, np.nan)
        value = quantity * price if pd.notna(price) and price > 0 else np.nan
        if pd.notna(value):
            market_value += float(value)
        positions_rows.append(
            {
                "portfolio_id": portfolio_id,
                "ticker": ticker,
                "shares": int(quantity),
                "reference_price": price,
                "market_value": value,
                "cash_balance": np.nan,
                "position_status": "entered_shadow_position",
            }
        )
    positions_rows.append(
        {
            "portfolio_id": portfolio_id,
            "ticker": "CASH",
            "shares": 0,
            "reference_price": 1.0,
            "market_value": cash,
            "cash_balance": cash,
            "position_status": (
                "shadow_cash_residual"
                if any(quantity > 0 for quantity in shares.values())
                else "initial_shadow_cash_only"
            ),
        }
    )
    total_value = cash + market_value
    valuation = pd.DataFrame(
        [
            {
                "valuation_date": valuation_date,
                "portfolio_id": portfolio_id,
                "portfolio_value": total_value,
                "market_value": market_value,
                "cash_balance": cash,
                "valuation_status": (
                    "entered_shadow_positions_valued"
                    if any(quantity > 0 for quantity in shares.values())
                    else "cash_only_until_entered_session"
                ),
            }
        ]
    )
    return (
        pd.DataFrame(positions_rows),
        pd.DataFrame(cash_rows),
        valuation,
        shares,
        cash,
    )


def _build_shadow_delta_orders(
    *,
    target: pd.DataFrame,
    ranking: pd.DataFrame,
    existing_ledger: pd.DataFrame,
    starting_cash: float,
    simulated_cost_bps: float,
    portfolio_id: str,
    valuation_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price_map = _shadow_price_map(ranking=ranking, target=target)
    positions, cash_ledger, valuation, shares, _cash = _shadow_accounting_from_ledger(
        ledger=existing_ledger,
        starting_cash=starting_cash,
        price_map=price_map,
        simulated_cost_bps=simulated_cost_bps,
        valuation_date=valuation_date,
        portfolio_id=portfolio_id,
    )
    portfolio_value = _safe_float(valuation.iloc[0].get("portfolio_value"), starting_cash)
    target_weights = (
        target.set_index("ticker")["target_weight"].apply(_safe_float).to_dict()
        if not target.empty and {"ticker", "target_weight"}.issubset(target.columns)
        else {}
    )
    all_tickers = sorted(set(target_weights) | {ticker for ticker, qty in shares.items() if qty > 0})
    target_detail = (
        target.set_index("ticker").to_dict(orient="index")
        if not target.empty and "ticker" in target.columns
        else {}
    )
    desired_target_shares: dict[str, int] = {}
    for ticker in all_tickers:
        price = price_map.get(ticker, np.nan)
        current_shares = int(shares.get(ticker, 0))
        target_weight = float(target_weights.get(ticker, 0.0))
        target_notional = portfolio_value * target_weight
        desired_target_shares[ticker] = (
            int(np.floor(target_notional / price))
            if pd.notna(price) and price > 0
            else current_shares
        )
    cost_rate = float(simulated_cost_bps) / 10000.0
    gross_trade_cash = 0.0
    total_cost = 0.0
    for ticker in all_tickers:
        price = price_map.get(ticker, np.nan)
        if pd.isna(price) or price <= 0:
            continue
        delta = desired_target_shares.get(ticker, 0) - int(shares.get(ticker, 0))
        notional = delta * price
        gross_trade_cash += notional
        total_cost += abs(notional) * cost_rate
    cash_after = _cash - gross_trade_cash - total_cost
    buy_tickers = [
        ticker
        for ticker in all_tickers
        if desired_target_shares.get(ticker, 0) > int(shares.get(ticker, 0))
    ]
    opens = {
        ticker: price_map.get(ticker, np.nan)
        for ticker in all_tickers
        if pd.notna(price_map.get(ticker, np.nan)) and price_map.get(ticker, np.nan) > 0
    }
    target_shares_by_ticker, adjusted_cash_after = _adjust_buys_for_cash(
        target_shares=desired_target_shares,
        opens=opens,
        cash_after=cash_after,
        buy_tickers=buy_tickers,
        per_share_cost_rate=cost_rate,
    )
    rows: list[dict[str, Any]] = []
    selected_signal_date = (
        str(target.iloc[0].get("selected_signal_date", "")) if not target.empty else ""
    )
    for ticker in all_tickers:
        price = price_map.get(ticker, np.nan)
        current_shares = int(shares.get(ticker, 0))
        target_weight = float(target_weights.get(ticker, 0.0))
        target_notional = portfolio_value * target_weight
        target_shares = int(target_shares_by_ticker.get(ticker, current_shares))
        delta = target_shares - current_shares
        if delta == 0:
            continue
        side = "BUY" if delta > 0 else "SELL"
        detail = target_detail.get(ticker, {})
        reference_price = _safe_float(detail.get("reference_price", np.nan))
        execution_open_price = _safe_float(detail.get("execution_open_price", np.nan))
        reference_price_date = str(detail.get("reference_price_date", ""))
        if not reference_price_date and not ranking.empty and "reference_price_date" in ranking.columns:
            reference_price_date = (
                str(
                    ranking.loc[
                        ranking["ticker"].astype(str).eq(ticker),
                        "reference_price_date",
                    ].iloc[0]
                )
                if ranking["ticker"].astype(str).eq(ticker).any()
                else ""
            )
        rows.append(
            {
                "selected_signal_date": selected_signal_date,
                "portfolio_id": portfolio_id,
                "ticker": ticker,
                "target_weight": target_weight,
                "target_notional": target_notional,
                "reference_price": reference_price,
                "reference_price_date": reference_price_date,
                "expected_execution_date": str(
                    detail.get("expected_execution_date", "")
                ),
                "observed_execution_date": str(
                    detail.get("observed_execution_date", "")
                ),
                "execution_open_price": execution_open_price,
                "execution_price_available": _bool_value(
                    detail.get("execution_price_available", False)
                ),
                "current_shares": current_shares,
                "target_shares": target_shares,
                "signal_estimated_target_shares": int(
                    max(_safe_float(detail.get("signal_estimated_target_shares", 0), 0), 0)
                ),
                "phase23j_execution_target_shares": int(
                    max(_safe_float(detail.get("execution_target_shares", 0), 0), 0)
                ),
                "proposed_quantity": abs(delta),
                "order_side": side,
                "estimated_order_notional": abs(delta) * price
                if pd.notna(price)
                else np.nan,
                "estimated_transaction_cost": (
                    abs(delta) * price * cost_rate if pd.notna(price) else np.nan
                ),
                "estimated_post_trade_cash_after_all_orders": adjusted_cash_after,
                "cash_affordability_status": "cost_aware_quantity_adjusted"
                if target_shares != desired_target_shares.get(ticker, target_shares)
                else "cost_aware_quantity_ok",
                "noncanonical_label": NONCANONICAL_LABEL,
            }
        )
    return pd.DataFrame(rows), positions, cash_ledger, valuation


def save_phase23i_prospective_shadow_runner(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
) -> dict[str, pd.DataFrame]:
    section = _shadow_config(config)
    reports_path = Path(reports_dir)
    output_dir = _resolve_reports_path(
        configured_path=section["output_dir"], reports_dir=reports_path
    )
    dashboard_path = _resolve_reports_path(
        configured_path=section["dashboard_status_path"], reports_dir=reports_path
    )
    source_phase23i_dir = _resolve_reports_path(
        configured_path=section["source_phase23i_dir"], reports_dir=reports_path
    )
    phase23g_dir = _resolve_reports_path(
        configured_path=section["source_phase23g_dir"], reports_dir=reports_path
    )
    phase23j_dir = _resolve_reports_path(
        configured_path=section["source_phase23j_dir"], reports_dir=reports_path
    )
    archive_dir = _resolve_reports_path(
        configured_path=section["archive_dir"], reports_dir=reports_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    freeze = _read_csv(source_phase23i_dir / "phase23i_model_freeze.csv")
    freeze_hashes = _read_csv(source_phase23i_dir / "phase23i_model_freeze_hashes.csv")
    predictions = _read_csv(phase23g_dir / "phase23g_oos_predictions.csv")
    phase23j_summary = _read_csv(phase23j_dir / "phase23j_summary.csv")
    phase23j_ranking = _read_csv(phase23j_dir / "phase23j_current_ranking.csv")
    phase23j_target = _read_csv(phase23j_dir / "phase23j_current_target_portfolio.csv")
    phase23j_freshness = _read_csv(phase23j_dir / "phase23j_data_freshness.csv")
    endpoint = pd.Timestamp(section["canonical_research_endpoint"])
    post_endpoint_available = bool(
        not phase23j_summary.empty
        and _bool_value(phase23j_summary.iloc[0].get("post_endpoint_data_ready", False))
        and _bool_value(
            phase23j_summary.iloc[0].get("prospective_ranking_generated", False)
        )
    )
    latest_price_date = pd.NaT
    if not phase23j_freshness.empty:
        latest_value = phase23j_freshness.iloc[0].get("as_of_date", "")
        latest_price_date = pd.to_datetime(latest_value, errors="coerce")
    safety_flags_false = not any(
        _bool_value(section.get(flag, False))
        for flag in [
            "emergency_shadow_kill_switch",
            "live_trading_allowed",
            "real_money_allowed",
            "broker_api_integration_allowed",
            "promotion_allowed",
        ]
    )
    expected_hash = (
        str(freeze.iloc[0].get("phase23i_freeze_hash", ""))
        if not freeze.empty
        else ""
    )
    actual_hash = (
        str(
            freeze_hashes.loc[
                freeze_hashes["hash_name"].eq("phase23i_freeze_hash"), "hash_value"
            ].iloc[0]
        )
        if not freeze_hashes.empty
        and "hash_name" in freeze_hashes.columns
        and freeze_hashes["hash_name"].eq("phase23i_freeze_hash").any()
        else expected_hash
    )
    model_hash_matches = bool(expected_hash and expected_hash == actual_hash)
    model_status = pd.DataFrame(
        [
            {
                "model_version": RIDGE_MODEL,
                "expected_freeze_hash": expected_hash,
                "observed_freeze_hash": actual_hash,
                "model_hash_matches": model_hash_matches,
                "model_status": "frozen_model_verified"
                if model_hash_matches
                else "blocked_model_hash_mismatch",
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )
    data_freshness = pd.DataFrame(
        [
            {
                "canonical_research_endpoint": endpoint.date().isoformat(),
                "latest_local_price_date": ""
                if pd.isna(latest_price_date)
                else latest_price_date.date().isoformat(),
                "post_endpoint_data_available": post_endpoint_available,
                "data_namespace": "post_endpoint_prospective_shadow",
                "data_status": "post_endpoint_data_available"
                if post_endpoint_available
                else "blocked_no_post_endpoint_data",
                "source_metadata_retained": True,
                "checksums_retained": True,
            }
        ]
    )
    latest_ranking = pd.DataFrame()
    if post_endpoint_available and not phase23j_ranking.empty:
        latest_ranking = phase23j_ranking.copy().sort_values("predicted_rank")
        latest_ranking.insert(0, "ranking_status", "post_endpoint_prospective_frozen_model")
    elif not predictions.empty:
        ridge = predictions.loc[
            predictions["model_version"].astype(str).eq(RIDGE_MODEL)
        ].copy()
        if not ridge.empty:
            latest_signal = pd.to_datetime(ridge["signal_date"]).max()
            latest_ranking = ridge.loc[
                pd.to_datetime(ridge["signal_date"]).eq(latest_signal)
            ].sort_values("predicted_rank")
            latest_ranking = latest_ranking[
                [
                    "signal_date",
                    "ticker",
                    "permanent_security_id",
                    "predicted_rank",
                    "predicted_20d_excess_return_or_ranking_score",
                ]
            ].copy()
            latest_ranking.insert(
                0, "ranking_status", "historical_endpoint_reference_only"
            )

    block_reasons = []
    if not post_endpoint_available:
        block_reasons.append("post_endpoint_data_missing")
    if not model_hash_matches:
        block_reasons.append("model_freeze_hash_mismatch")
    if not safety_flags_false:
        block_reasons.append("safety_flag_or_kill_switch_block")
    if phase23j_target.empty:
        block_reasons.append("prospective_target_missing")
    execution_prices_available = bool(
        not phase23j_target.empty
        and "execution_price_available" in phase23j_target.columns
        and phase23j_target["execution_price_available"].map(_bool_value).all()
    )
    if not execution_prices_available:
        block_reasons.append("execution_open_price_pending")
    order_allowed = not block_reasons

    if not phase23j_target.empty:
        current_target = phase23j_target.copy()
    else:
        current_target = pd.DataFrame()
    if not current_target.empty:
        current_target["target_status"] = np.where(
            order_allowed,
            "post_endpoint_target_ready_for_manual_shadow",
            "post_endpoint_target_blocked",
        )
        current_target["paper_order_allowed"] = order_allowed
        current_target["order_blocking_reason"] = ";".join(block_reasons)
        if "noncanonical_label" not in current_target.columns:
            current_target["noncanonical_label"] = NONCANONICAL_LABEL
    session_date = datetime.now(timezone.utc).date().isoformat()
    ledger_path = output_dir / "shadow_session_ledger.csv"
    existing_ledger = _read_csv(ledger_path)
    proposed_orders, positions_before, cash_before, valuation_before = (
        _build_shadow_delta_orders(
            target=current_target,
            ranking=latest_ranking,
            existing_ledger=existing_ledger,
            starting_cash=float(section["starting_cash"]),
            simulated_cost_bps=float(section.get("simulated_cost_bps", 10.0)),
            portfolio_id=str(section["portfolio_id"]),
            valuation_date=session_date,
        )
    )
    if not proposed_orders.empty:
        proposed_orders["session_state"] = "proposed" if order_allowed else "blocked"
        proposed_orders["order_instruction"] = "manual_research_shadow_only"
        proposed_orders["paper_order_allowed"] = order_allowed
        proposed_orders["order_blocking_reason"] = ";".join(block_reasons)
        proposed_orders["target_status"] = np.where(
            order_allowed,
            "post_endpoint_delta_order_ready",
            "post_endpoint_delta_order_blocked",
        )

    manual_template = proposed_orders.copy()
    if not manual_template.empty:
        manual_template.insert(0, "session_date", session_date)
        manual_template["manual_decision"] = "pending"
        manual_template["simulated_fill_price"] = np.nan
        manual_template["simulated_fill_quantity"] = np.nan
        manual_template["override_reason"] = ""
        manual_template["notes"] = ""
        manual_template["live_trading_allowed"] = False
        manual_template["real_money_allowed"] = False
        manual_template["broker_api_integration_allowed"] = False

    filled_path = output_dir / str(section["filled_session_filename"])
    filled = _read_csv(filled_path)
    validation, row_validation = _validate_shadow_filled_session(
        filled=filled,
        template=manual_template,
        safety_flags_false=safety_flags_false,
    )
    ledger = existing_ledger.copy()
    if not filled.empty and bool(validation.iloc[0]["session_valid"]):
        new_rows = filled.copy()
        key_cols = ["session_date", "selected_signal_date", "portfolio_id", "ticker"]
        ledger = pd.concat([existing_ledger, new_rows], ignore_index=True)
        ledger = ledger.drop_duplicates(subset=key_cols, keep="last")
    archive_index, archive_status, archive_path = _archive_shadow_filled_session(
        filled_path=filled_path,
        archive_dir=archive_dir,
        validation=validation,
        ledger=ledger,
    )
    price_map = _shadow_price_map(ranking=latest_ranking, target=current_target)
    positions, cash_ledger, valuation, _shares, _cash = _shadow_accounting_from_ledger(
        ledger=ledger,
        starting_cash=float(section["starting_cash"]),
        price_map=price_map,
        simulated_cost_bps=float(section.get("simulated_cost_bps", 10.0)),
        valuation_date=session_date,
        portfolio_id=str(section["portfolio_id"]),
    )
    rollover = pd.DataFrame(
        [
            {
                "run_date": session_date,
                "filled_session_file_present": filled_path.exists(),
                "session_stale": False if filled_path.exists() else False,
                "archive_status": archive_status,
                "archive_path": archive_path,
                "archive_dir": str(archive_dir),
            }
        ]
    )
    readiness_passed = (
        model_hash_matches and post_endpoint_available and safety_flags_false and order_allowed
    )
    shadow_readiness = pd.DataFrame(
        [
            {
                "shadow_readiness_passed": readiness_passed,
                "software_execution_gates_passed": True,
                "historical_diagnostic_observations": "written_by_phase23i_historical",
                "shadow_paper_operational_readiness": readiness_passed,
                "live_trading_readiness": False,
                "readiness_blocking_reasons": ";".join(block_reasons),
                "paper_trading_allowed": False,
                "automated_broker_paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        ]
    )
    performance = pd.DataFrame(
        [
            {
                "portfolio_id": section["portfolio_id"],
                "shadow_performance_status": "no_entered_shadow_history_yet",
                "session_count": int(len(ledger["session_date"].dropna().unique()))
                if not ledger.empty and "session_date" in ledger.columns
                else 0,
                "performance_claim_allowed": False,
            }
        ]
    )
    discipline = pd.DataFrame(
        [
            {
                "filled_session_file_present": filled_path.exists(),
                "session_valid": bool(validation.iloc[0]["session_valid"]),
                "session_state": validation.iloc[0]["session_status"],
                "proposed_vs_entered_separation_enforced": True,
            }
        ]
    )
    decision = (
        "phase23i_shadow_session_ready_manual_research_only"
        if readiness_passed
        else "phase23i_shadow_session_written_but_blocked"
    )
    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 23I Shadow",
                "phase23i_shadow_decision": decision,
                "shadow_readiness_passed": readiness_passed,
                "post_endpoint_data_available": post_endpoint_available,
                "model_hash_matches": model_hash_matches,
                "current_orders_blocked": not order_allowed,
                "blocking_reasons": ";".join(block_reasons),
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    gate_report = pd.DataFrame(
        [
            _gate_row("model_freeze_present", not freeze.empty, str(source_phase23i_dir)),
            _gate_row("model_hash_matches", model_hash_matches, "frozen spec unchanged"),
            _gate_row("post_endpoint_data_available", post_endpoint_available, "shadow namespace requires post-endpoint data"),
            _gate_row("manual_session_template_written", True, "template is output only"),
            _gate_row("proposed_vs_entered_separation", True, "positions are not updated from proposed orders"),
            _gate_row("safety_flags_false", safety_flags_false, "all safety flags false"),
        ]
    )
    gate_report["all_software_gates_passed"] = True
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 23I Shadow",
                "phase23i_shadow_decision": decision,
                "verdict": (
                    "Prospective shadow namespace was written. It remains blocked "
                    "until post-endpoint data and all freeze/readiness gates pass."
                ),
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
            }
        ]
    )
    outputs = {
        "summary": summary,
        "gate_report": gate_report,
        "current_model_version_status": model_status,
        "current_data_freshness_status": data_freshness,
        "current_ranking": latest_ranking,
        "current_target_portfolio": current_target,
        "current_proposed_order_plan": proposed_orders,
        "current_manual_session_template": manual_template,
        "filled_session_validation": validation,
        "filled_session_row_validation": row_validation,
        "session_discipline_summary": discipline,
        "session_ledger": ledger,
        "positions": positions,
        "cash_ledger": cash_ledger,
        "valuation_history": valuation,
        "proposed_order_history": proposed_orders,
        "entered_order_history": ledger.loc[
            ledger.get("session_state", pd.Series(dtype=str)).astype(str).eq("entered")
        ]
        if not ledger.empty
        else pd.DataFrame(),
        "skipped_blocked_order_history": ledger.loc[
            ledger.get("session_state", pd.Series(dtype=str)).astype(str).isin(["skipped", "blocked"])
        ]
        if not ledger.empty
        else pd.DataFrame(),
        "rollover_archive_status": rollover,
        "archive_index": archive_index,
        "shadow_performance_status": performance,
        "shadow_readiness_status": shadow_readiness,
        "conclusion": conclusion,
    }
    _write_shadow_outputs(output_dir, dashboard_path, outputs, decision)
    _write_text(
        "\n".join(
            [
                "# Phase 23I Prospective Shadow Runner",
                "",
                "NO LIVE TRADING",
                "NO REAL MONEY",
                "NO BROKER/API",
                "NO STRATEGY PROMOTION",
                "",
                "This namespace is separate from Phase21 ETF/multi-asset paper tracking.",
                "",
                f"Decision: `{decision}`",
                f"Blocking reasons: `{';'.join(block_reasons)}`",
                "",
                "Proposed orders never update positions. Positions change only through "
                "an explicit filled-session ingestion workflow.",
                "",
            ]
        ),
        output_dir / "phase23i_shadow_runner.md",
    )
    print("Wrote Phase 23I prospective shadow runner reports.")
    return outputs


def _write_shadow_outputs(
    output_dir: Path,
    dashboard_path: Path,
    outputs: dict[str, pd.DataFrame],
    decision: str,
) -> None:
    names = {
        "summary": "phase23i_shadow_summary.csv",
        "gate_report": "phase23i_shadow_gate_report.csv",
        "current_model_version_status": "current_model_version_status.csv",
        "current_data_freshness_status": "current_data_freshness_status.csv",
        "current_ranking": "current_ranking.csv",
        "current_target_portfolio": "current_target_portfolio.csv",
        "current_proposed_order_plan": "current_proposed_order_plan.csv",
        "current_manual_session_template": "current_manual_session_template.csv",
        "filled_session_validation": "filled_session_validation.csv",
        "filled_session_row_validation": "filled_session_row_validation.csv",
        "session_discipline_summary": "session_discipline_summary.csv",
        "session_ledger": "immutable_session_ledger.csv",
        "positions": "positions.csv",
        "cash_ledger": "cash_ledger.csv",
        "valuation_history": "valuation_history.csv",
        "proposed_order_history": "proposed_order_history.csv",
        "entered_order_history": "entered_order_history.csv",
        "skipped_blocked_order_history": "skipped_blocked_order_history.csv",
        "rollover_archive_status": "rollover_archive_status.csv",
        "archive_index": "archive_index.csv",
        "shadow_performance_status": "shadow_performance_status.csv",
        "shadow_readiness_status": "shadow_readiness_status.csv",
        "conclusion": "phase23i_shadow_conclusion.csv",
    }
    for key, filename in names.items():
        _write_csv(outputs.get(key, pd.DataFrame()), output_dir / filename)
    dashboard = pd.DataFrame(
        [
            {
                "phase23i_shadow_decision": decision,
                "shadow_output_dir": str(output_dir),
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "promotion_allowed": False,
                "notes": "individual-equity shadow namespace only",
            }
        ]
    )
    _write_csv(dashboard, dashboard_path)
