from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.strategy_factory_multiverse import (
    CASH,
    _asset_col,
    _real_symbols,
    build_multiverse_price_panel,
    parse_universe_config,
    run_multiverse_candidates_for_universe,
)


PHASE21A_SECTION = "phase21a_historical_regime_stress_lab"
DEFAULT_REQUIRED_CANONICAL_CANDIDATES = [
    "canonical_spy_buy_hold",
    "phase6b_loose_relief_execution_realistic_overlay",
    "canonical_spy_qqq_60_40",
    "canonical_spy_qqq_70_30",
    "canonical_inverse_vol_63d_qqq_spy",
    "canonical_inverse_vol_126d_qqq_spy",
    "canonical_spy_qqq_btc_cap_05",
    "canonical_inverse_vol_63d_btc_usd_qqq_spy",
    "canonical_inverse_vol_126d_btc_usd_qqq_spy",
    "canonical_sf19_topk_momentum_252d_top3_btc10",
]
PHASE6_BASELINE_ID = "phase6b_loose_relief_execution_realistic_overlay"
PHASE6_BASELINE_DAILY_FILE = "phase6b_loose_relief_execution_realistic_overlay_daily.csv"
CRASH_REGIME_NAMES = {
    "dot_com_crash",
    "global_financial_crisis",
    "covid_crash",
    "inflation_rate_shock",
}
SHORT_WINDOW_DIRECTIONAL_ONLY_REGIMES = {"covid_crash"}
DEFAULT_REGIMES = {
    "dot_com_crash": {
        "start": "2000-03-10",
        "end": "2002-10-09",
        "description": "Dot-com crash / early-2000s equity bear market",
    },
    "post_dot_com_recovery": {
        "start": "2002-10-10",
        "end": "2007-10-09",
        "description": "Post-dot-com recovery before GFC",
    },
    "global_financial_crisis": {
        "start": "2007-10-09",
        "end": "2009-03-09",
        "description": "Global Financial Crisis",
    },
    "post_gfc_bull_market": {
        "start": "2009-03-10",
        "end": "2020-02-19",
        "description": "Post-GFC bull market",
    },
    "covid_crash": {
        "start": "2020-02-19",
        "end": "2020-03-23",
        "description": "COVID crash",
    },
    "covid_rebound": {
        "start": "2020-03-24",
        "end": "2021-12-31",
        "description": "COVID rebound / liquidity boom",
    },
    "inflation_rate_shock": {
        "start": "2022-01-03",
        "end": "2022-10-14",
        "description": "2022 inflation and rate shock",
    },
    "post_2022_recovery": {
        "start": "2022-10-15",
        "end": "2026-05-01",
        "description": "Post-2022 recovery to canonical endpoint",
    },
    "full_canonical": {
        "start": "2006-04-28",
        "end": "2026-05-01",
        "description": "Canonical Phase 2+ research window",
    },
}


@dataclass(frozen=True)
class CandidateSpec:
    canonical_candidate_id: str
    universe_name: str
    candidate_id: str
    candidate_role: str
    asset_roster: tuple[str, ...]
    candidate_family: str


def _section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get(PHASE21A_SECTION, {}) or {}


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (not isinstance(value, (list, dict, tuple, set)) and pd.isna(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _text_value(value: Any) -> str:
    if value is None or (not isinstance(value, (list, dict, tuple, set)) and pd.isna(value)):
        return ""
    return str(value).strip()


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.is_dir():
        return pd.DataFrame()
    return pd.read_csv(path)


def _safe_float(value: Any, default: float = 0.0) -> float:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(converted) if pd.notna(converted) else default


def _normalise_symbol(symbol: str) -> str:
    return str(symbol).strip().upper()


def parse_regime_windows(section: dict[str, Any]) -> pd.DataFrame:
    windows = section.get("regime_windows", {}) or DEFAULT_REGIMES
    rows: list[dict[str, Any]] = []
    for name, spec in windows.items():
        regime_name = str(name)
        is_full_context = regime_name == "full_canonical"
        is_short_window = regime_name in SHORT_WINDOW_DIRECTIONAL_ONLY_REGIMES
        rows.append(
            {
                "regime_name": regime_name,
                "start": pd.Timestamp(spec["start"]).date().isoformat(),
                "end": pd.Timestamp(spec["end"]).date().isoformat(),
                "description": str(spec.get("description", "")),
                "is_full_canonical_context": is_full_context,
                "is_crash_regime": regime_name in CRASH_REGIME_NAMES,
                "short_window_directional_only": is_short_window,
                "included_in_primary_subregime_score": not is_full_context,
                "included_in_primary_calmar_score": not is_full_context and not is_short_window,
            }
        )
    return pd.DataFrame(rows)


def _candidate_id_to_canonical(candidate_id: str, symbols: list[str]) -> str:
    assets = sorted(symbol for symbol in _real_symbols(symbols) if symbol != CASH)
    if candidate_id == "sf19_spy_buy_hold":
        return "canonical_spy_buy_hold"
    if "spy_qqq_60_40" in candidate_id:
        return "canonical_spy_qqq_60_40"
    if "spy_qqq_70_30" in candidate_id:
        return "canonical_spy_qqq_70_30"
    if "spy_qqq_50_50" in candidate_id:
        return "canonical_spy_qqq_50_50"
    if "spy_qqq_btc_cap_05" in candidate_id:
        return "canonical_spy_qqq_btc_cap_05"
    if "spy_qqq_btc_cap_10" in candidate_id:
        return "canonical_spy_qqq_btc_cap_10"
    if "inverse_vol_63d" in candidate_id:
        return f"canonical_inverse_vol_63d_{'_'.join(assets).lower().replace('-', '_')}"
    if "inverse_vol_126d" in candidate_id:
        return f"canonical_inverse_vol_126d_{'_'.join(assets).lower().replace('-', '_')}"
    if "topk_momentum" in candidate_id:
        return f"canonical_{candidate_id}"
    return f"canonical_{candidate_id}"


def _manual_candidate_specs() -> list[CandidateSpec]:
    return [
        CandidateSpec(
            "canonical_spy_buy_hold",
            "spy_benchmark",
            "sf19_spy_buy_hold",
            "spy_benchmark",
            ("SPY",),
            "baseline",
        ),
        CandidateSpec(
            "canonical_spy_qqq_60_40",
            "core_us_growth",
            "sf19_spy_qqq_60_40",
            "clean_growth_reference",
            ("SPY", "QQQ"),
            "fixed_allocation",
        ),
        CandidateSpec(
            "canonical_spy_qqq_70_30",
            "core_us_growth",
            "sf19_spy_qqq_70_30",
            "clean_growth_reference",
            ("SPY", "QQQ"),
            "fixed_allocation",
        ),
        CandidateSpec(
            "canonical_inverse_vol_63d_qqq_spy",
            "core_us_growth",
            "sf19_inverse_vol_63d_cap50",
            "volatility_aware_reference",
            ("SPY", "QQQ"),
            "volatility_aware",
        ),
        CandidateSpec(
            "canonical_inverse_vol_126d_qqq_spy",
            "core_us_growth",
            "sf19_inverse_vol_126d_cap50",
            "volatility_aware_reference",
            ("SPY", "QQQ"),
            "volatility_aware",
        ),
        CandidateSpec(
            "canonical_spy_qqq_btc_cap_05",
            "btc_capped_growth",
            "sf19_spy_qqq_btc_cap_05",
            "high_caveat_btc_reference",
            ("SPY", "QQQ", "BTC-USD"),
            "fixed_allocation_btc_capped",
        ),
        CandidateSpec(
            "canonical_inverse_vol_63d_btc_usd_qqq_spy",
            "btc_capped_growth",
            "sf19_inverse_vol_63d_cap50_btc05",
            "high_caveat_btc_candidate",
            ("SPY", "QQQ", "BTC-USD"),
            "volatility_aware",
        ),
        CandidateSpec(
            "canonical_inverse_vol_126d_btc_usd_qqq_spy",
            "btc_capped_growth",
            "sf19_inverse_vol_126d_cap50_btc05",
            "high_caveat_btc_candidate",
            ("SPY", "QQQ", "BTC-USD"),
            "volatility_aware",
        ),
        CandidateSpec(
            "canonical_sf19_topk_momentum_252d_top3_btc10",
            "btc_capped_growth",
            "sf19_topk_momentum_252d_top3_btc10",
            "high_caveat_btc_candidate",
            ("SPY", "QQQ", "BTC-USD"),
            "top_k_momentum",
        ),
        CandidateSpec(
            "canonical_spy_qqq_gld_tlt_50_30_10_10",
            "defensive_multi_asset",
            "sf19_spy_qqq_gld_tlt_50_30_10_10",
            "gld_tlt_reference",
            ("SPY", "QQQ", "GLD", "TLT"),
            "fixed_allocation",
        ),
    ]


def _phase6_baseline_spec() -> CandidateSpec:
    return CandidateSpec(
        PHASE6_BASELINE_ID,
        "phase6_baseline",
        PHASE6_BASELINE_ID,
        "canonical_defensive_overlay_baseline",
        ("SPY", "CASH"),
        "external_daily_equity_curve",
    )


def _load_phase19b_specs(finalists: pd.DataFrame) -> list[CandidateSpec]:
    if finalists.empty:
        return []
    rows: list[CandidateSpec] = []
    for row in finalists.to_dict("records"):
        assets = tuple(
            sorted(
                asset
                for asset in str(row.get("active_assets", "")).split(",")
                if asset and asset != CASH
            )
        )
        rows.append(
            CandidateSpec(
                canonical_candidate_id=str(row.get("canonical_candidate_id", "")),
                universe_name=str(row.get("universe_name", row.get("universe", ""))),
                candidate_id=str(row.get("candidate_id", "")),
                candidate_role=str(row.get("classification", "phase19a_finalist")),
                asset_roster=assets,
                candidate_family=str(row.get("candidate_family", row.get("strategy_family", ""))),
            )
        )
    return [
        spec
        for spec in rows
        if spec.canonical_candidate_id and spec.universe_name and spec.candidate_id
    ]


def build_phase21a_candidate_specs(
    *,
    section: dict[str, Any],
    phase19b_canonical_finalists: pd.DataFrame,
) -> list[CandidateSpec]:
    groups = section.get("candidate_groups", {}) or {}
    specs: list[CandidateSpec] = []
    if _bool_value(groups.get("include_spy_benchmark", True)):
        specs.append(_manual_candidate_specs()[0])
    if _bool_value(groups.get("include_phase6_loose_relief_baseline", True)):
        specs.append(_phase6_baseline_spec())
    if _bool_value(groups.get("include_spy_qqq_static_variants", True)):
        specs.extend(_manual_candidate_specs()[1:3])
    if _bool_value(groups.get("include_btc_candidates_where_available", True)):
        specs.extend(_manual_candidate_specs()[5:9])
    if _bool_value(groups.get("include_gls_tlt_reference_where_available", True)):
        specs.append(_manual_candidate_specs()[9])
    specs.extend(_manual_candidate_specs()[3:5])
    if _bool_value(groups.get("include_phase19a_finalists", True)):
        specs.extend(_load_phase19b_specs(phase19b_canonical_finalists))

    deduped: dict[str, CandidateSpec] = {}
    for spec in specs:
        if spec.canonical_candidate_id not in deduped:
            deduped[spec.canonical_candidate_id] = spec
    return list(deduped.values())


def _safe_symbol_file(symbol: str) -> str:
    return f"{symbol.upper()}.parquet"


def _load_price_data_from_disk(symbols: list[str], data_dir: Path) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol in _real_symbols(symbols):
        path = data_dir / _safe_symbol_file(symbol)
        if path.exists():
            out[symbol] = pd.read_parquet(path)
    return out


def _fallback_data_dir(section: dict[str, Any]) -> Path:
    configured = section.get("data_dir") or section.get("source_data_dir")
    if configured:
        return Path(configured)
    fresh = Path("data/fresh/processed")
    return fresh if fresh.exists() else Path("data/processed")


def _universe_symbols_from_config(
    universes: dict[str, dict[str, Any]],
    universe_name: str,
    fallback_assets: tuple[str, ...],
) -> tuple[list[str], bool, list[float]]:
    if universe_name == "spy_benchmark":
        return ["SPY", CASH], False, []
    universe = universes.get(universe_name)
    if universe:
        return (
            list(universe["symbols"]),
            bool(universe.get("allow_btc", False)),
            list(universe.get("btc_caps", [])),
        )
    symbols = [*fallback_assets]
    if CASH not in symbols:
        symbols.append(CASH)
    return symbols, "BTC-USD" in symbols, [0.05, 0.10] if "BTC-USD" in symbols else []


def _phase6_baseline_path(section: dict[str, Any], reports_dir: Path) -> Path:
    configured = section.get("phase6_baseline_daily_path")
    if configured:
        return Path(configured)
    return reports_dir / PHASE6_BASELINE_DAILY_FILE


def _load_phase6_baseline_result(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists() or path.is_dir():
        return pd.DataFrame(), "phase6_daily_equity_curve_missing"
    raw = _read_csv(path)
    if raw.empty:
        return pd.DataFrame(), "phase6_daily_equity_curve_empty"
    date_col = "decision_date" if "decision_date" in raw.columns else "date"
    if date_col not in raw.columns:
        return pd.DataFrame(), "phase6_daily_equity_curve_missing_date_column"
    if "strategy_return" not in raw.columns and "candidate_equity" not in raw.columns:
        return pd.DataFrame(), "phase6_daily_equity_curve_missing_return_or_equity"

    frame = pd.DataFrame()
    frame["date"] = pd.to_datetime(raw[date_col], errors="coerce")
    frame = frame.loc[frame["date"].notna()].copy()
    if frame.empty:
        return pd.DataFrame(), "phase6_daily_equity_curve_invalid_dates"

    if "strategy_return" in raw.columns:
        returns = pd.to_numeric(raw.loc[frame.index, "strategy_return"], errors="coerce")
    else:
        equity = pd.to_numeric(raw.loc[frame.index, "candidate_equity"], errors="coerce")
        returns = equity.pct_change().fillna(0.0)
    frame["strategy_return"] = returns.fillna(0.0).to_numpy()

    if "candidate_equity" in raw.columns:
        frame["equity"] = pd.to_numeric(
            raw.loc[frame.index, "candidate_equity"],
            errors="coerce",
        ).to_numpy()
    else:
        frame["equity"] = 10000.0 * (1.0 + frame["strategy_return"]).cumprod()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")

    if "exposure" in raw.columns:
        frame["position"] = pd.to_numeric(raw.loc[frame.index, "exposure"], errors="coerce").fillna(0.0).to_numpy()
    else:
        frame["position"] = 1.0
    frame["cash_position"] = (1.0 - pd.to_numeric(frame["position"], errors="coerce")).clip(0.0, 1.0)
    if "turnover" in raw.columns:
        frame["turnover"] = pd.to_numeric(raw.loc[frame.index, "turnover"], errors="coerce").fillna(0.0).to_numpy()
    else:
        frame["turnover"] = 0.0

    frame = frame.loc[frame["equity"].notna()].sort_values("date").reset_index(drop=True)
    if len(frame) < 2:
        return pd.DataFrame(), "phase6_daily_equity_curve_insufficient_rows"
    return frame, ""


def reconstruct_candidate_results(
    *,
    config: dict[str, Any],
    section: dict[str, Any],
    candidate_specs: list[CandidateSpec],
    reports_dir: Path,
    price_data: dict[str, pd.DataFrame] | None = None,
) -> tuple[dict[str, dict[str, Any]], pd.DataFrame]:
    multiverse_section = config.get("phase19a_strategy_factory_multiverse", {}) or {}
    universes = parse_universe_config(multiverse_section)
    initial_capital = float(section.get("initial_capital", 10000))
    data_dir = _fallback_data_dir(section)
    results: dict[str, dict[str, Any]] = {}
    unavailable: list[dict[str, Any]] = []

    for spec in candidate_specs:
        if spec.canonical_candidate_id == PHASE6_BASELINE_ID:
            phase6_path = _phase6_baseline_path(section, reports_dir)
            phase6_result, missing_reason = _load_phase6_baseline_result(phase6_path)
            if missing_reason:
                unavailable.append(
                    {
                        "canonical_candidate_id": spec.canonical_candidate_id,
                        "candidate_id": spec.candidate_id,
                        "regime_name": "all",
                        "availability_reason": missing_reason,
                        "asset_roster": ",".join(spec.asset_roster),
                        "regime_metric_status": "equity_curve_missing",
                        "equity_curve_source": str(phase6_path),
                        "equity_curve_daily_verified": False,
                        "equity_curve_missing_reason": missing_reason,
                        "uses_aggregate_metrics_only": False,
                    }
                )
                continue
            results[spec.canonical_candidate_id] = {
                "candidate_id": spec.candidate_id,
                "strategy_family": spec.candidate_family,
                "canonical_candidate_id": spec.canonical_candidate_id,
                "candidate_role": spec.candidate_role,
                "candidate_family": spec.candidate_family,
                "asset_roster": ",".join(spec.asset_roster),
                "assets_required": ["SPY"],
                "price_data": {},
                "result": phase6_result,
                "equity_curve_source": str(phase6_path),
                "equity_curve_daily_verified": True,
                "equity_curve_missing_reason": "",
                "uses_aggregate_metrics_only": False,
            }
            continue

        symbols, allow_btc, btc_caps = _universe_symbols_from_config(
            universes,
            spec.universe_name,
            spec.asset_roster,
        )
        loaded = (
            {
                symbol: frame
                for symbol, frame in price_data.items()
                if symbol in _real_symbols(symbols)
            }
            if price_data is not None
            else _load_price_data_from_disk(symbols, data_dir)
        )
        missing = [symbol for symbol in _real_symbols(symbols) if symbol not in loaded]
        if missing:
            unavailable.append(
                {
                    "canonical_candidate_id": spec.canonical_candidate_id,
                    "candidate_id": spec.candidate_id,
                    "regime_name": "all",
                    "availability_reason": f"missing_price_data:{','.join(missing)}",
                    "asset_roster": ",".join(spec.asset_roster),
                    "regime_metric_status": "equity_curve_missing",
                    "equity_curve_source": "strategy_factory_reconstruction",
                    "equity_curve_daily_verified": False,
                    "equity_curve_missing_reason": f"missing_price_data:{','.join(missing)}",
                    "uses_aggregate_metrics_only": False,
                }
            )
            continue
        try:
            panel = build_multiverse_price_panel(loaded, symbols)
            candidates = run_multiverse_candidates_for_universe(
                panel,
                universe_name=spec.universe_name,
                symbols=symbols,
                allow_btc=allow_btc,
                btc_caps=btc_caps,
                initial_capital=initial_capital,
            )
        except Exception as exc:
            unavailable.append(
                {
                    "canonical_candidate_id": spec.canonical_candidate_id,
                    "candidate_id": spec.candidate_id,
                    "regime_name": "all",
                    "availability_reason": f"candidate_reconstruction_failed:{exc}",
                    "asset_roster": ",".join(spec.asset_roster),
                    "regime_metric_status": "equity_curve_missing",
                    "equity_curve_source": "strategy_factory_reconstruction",
                    "equity_curve_daily_verified": False,
                    "equity_curve_missing_reason": f"candidate_reconstruction_failed:{exc}",
                    "uses_aggregate_metrics_only": False,
                }
            )
            continue
        candidate = candidates.get(spec.candidate_id)
        if candidate is None:
            unavailable.append(
                {
                    "canonical_candidate_id": spec.canonical_candidate_id,
                    "candidate_id": spec.candidate_id,
                    "regime_name": "all",
                    "availability_reason": "candidate_not_generated_by_universe",
                    "asset_roster": ",".join(spec.asset_roster),
                    "regime_metric_status": "equity_curve_missing",
                    "equity_curve_source": "strategy_factory_reconstruction",
                    "equity_curve_daily_verified": False,
                    "equity_curve_missing_reason": "candidate_not_generated_by_universe",
                    "uses_aggregate_metrics_only": False,
                }
            )
            continue
        result = candidate["result"].copy()
        results[spec.canonical_candidate_id] = {
            **candidate,
            "canonical_candidate_id": spec.canonical_candidate_id,
            "candidate_role": spec.candidate_role,
            "candidate_family": spec.candidate_family or candidate["strategy_family"],
            "asset_roster": ",".join(spec.asset_roster),
            "assets_required": list(spec.asset_roster),
            "price_data": loaded,
            "result": result,
            "equity_curve_source": "strategy_factory_reconstructed_daily_curve",
            "equity_curve_daily_verified": True,
            "equity_curve_missing_reason": "",
            "uses_aggregate_metrics_only": False,
        }

    return results, pd.DataFrame(unavailable)


def _asset_first_dates(price_data: dict[str, pd.DataFrame], assets: list[str]) -> dict[str, pd.Timestamp]:
    first_dates: dict[str, pd.Timestamp] = {}
    for asset in assets:
        frame = price_data.get(asset)
        if frame is None or frame.empty or "date" not in frame.columns:
            continue
        first_dates[asset] = pd.to_datetime(frame["date"]).min()
    return first_dates


def _asset_inception_block(
    *,
    price_data: dict[str, pd.DataFrame],
    assets: list[str],
    regime_start: pd.Timestamp,
) -> str:
    first_dates = _asset_first_dates(price_data, assets)
    blockers = [
        f"{asset}={first.date().isoformat()}"
        for asset, first in sorted(first_dates.items())
        if first > regime_start
    ]
    return (
        f"asset_inception_after_regime_start:{';'.join(blockers)}"
        if blockers
        else ""
    )


def _slice_result(
    result: pd.DataFrame,
    *,
    start: str,
    end: str,
    initial_capital: float,
) -> pd.DataFrame:
    frame = result.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.loc[
        (frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))
    ].copy()
    frame = frame.sort_values("date").reset_index(drop=True)
    if frame.empty:
        return frame
    frame["strategy_return"] = pd.to_numeric(frame["strategy_return"], errors="coerce").fillna(0.0)
    frame.loc[0, "strategy_return"] = 0.0
    frame["equity"] = float(initial_capital) * (1.0 + frame["strategy_return"]).cumprod()
    return frame


def calculate_regime_metric_row(
    *,
    candidate: dict[str, Any],
    regime: dict[str, Any],
    spy_result: pd.DataFrame,
    initial_capital: float,
    min_regime_trading_days: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    regime_start = pd.Timestamp(regime["start"])
    assets_required = list(candidate.get("assets_required", []))
    inception_block = _asset_inception_block(
        price_data=candidate.get("price_data", {}),
        assets=assets_required,
        regime_start=regime_start,
    )
    base_row = {
        "canonical_candidate_id": candidate["canonical_candidate_id"],
        "candidate_id": candidate["candidate_id"],
        "candidate_role": candidate.get("candidate_role", ""),
        "candidate_family": candidate.get("candidate_family", candidate.get("strategy_family", "")),
        "asset_roster": candidate.get("asset_roster", ""),
        "regime_name": regime["regime_name"],
        "regime_description": regime.get("description", ""),
        "is_full_canonical_context": _bool_value(
            regime.get("is_full_canonical_context", False)
        ),
        "is_crash_regime": _bool_value(regime.get("is_crash_regime", False)),
        "short_window_directional_only": _bool_value(
            regime.get("short_window_directional_only", False)
        ),
        "included_in_primary_subregime_score": _bool_value(
            regime.get("included_in_primary_subregime_score", True)
        ),
        "included_in_primary_calmar_score": _bool_value(
            regime.get("included_in_primary_calmar_score", True)
        ),
        "start_date": regime["start"],
        "end_date": regime["end"],
        "equity_curve_source": candidate.get(
            "equity_curve_source",
            "strategy_factory_reconstructed_daily_curve",
        ),
        "equity_curve_daily_verified": _bool_value(
            candidate.get("equity_curve_daily_verified", True)
        ),
        "equity_curve_missing_reason": candidate.get("equity_curve_missing_reason", ""),
        "uses_aggregate_metrics_only": _bool_value(
            candidate.get("uses_aggregate_metrics_only", False)
        ),
        "paper_only": True,
        "promotion_allowed": False,
        "live_trading_allowed": False,
        "real_money_allowed": False,
        "broker_api_integration_allowed": False,
    }
    if inception_block:
        unavailable = {
            **base_row,
            "trading_days": 0,
            "regime_available": False,
            "availability_reason": inception_block,
            "regime_metric_status": "asset_inception_unavailable",
            "equity_curve_daily_verified": True,
            "equity_curve_missing_reason": "",
            "uses_aggregate_metrics_only": False,
        }
        return unavailable, unavailable

    sliced = _slice_result(
        candidate["result"],
        start=regime["start"],
        end=regime["end"],
        initial_capital=initial_capital,
    )
    if len(sliced) < min_regime_trading_days:
        unavailable = {
            **base_row,
            "trading_days": len(sliced),
            "regime_available": False,
            "availability_reason": f"fewer_than_{min_regime_trading_days}_trading_days",
            "regime_metric_status": "insufficient_regime_rows",
            "equity_curve_daily_verified": True,
            "equity_curve_missing_reason": "",
            "uses_aggregate_metrics_only": False,
        }
        return unavailable, unavailable

    metrics = calculate_metrics(sliced, candidate["canonical_candidate_id"])
    returns = pd.to_numeric(sliced["strategy_return"], errors="coerce").fillna(0.0)
    btc_col = _asset_col("BTC-USD")
    btc_weight_max = float(sliced[btc_col].max()) if btc_col in sliced.columns else 0.0
    spy_slice = _slice_result(
        spy_result,
        start=metrics["start_date"],
        end=metrics["end_date"],
        initial_capital=initial_capital,
    )
    spy_metrics = calculate_metrics(spy_slice, "SPY") if len(spy_slice) >= 2 else {}
    excess = (
        float(metrics["total_return_pct"]) - float(spy_metrics.get("total_return_pct", np.nan))
        if spy_metrics
        else np.nan
    )
    drawdown_improvement = (
        float(metrics["max_drawdown_pct"]) - float(spy_metrics.get("max_drawdown_pct", np.nan))
        if spy_metrics
        else np.nan
    )
    calmar_diff = (
        float(metrics["calmar"]) - float(spy_metrics.get("calmar", np.nan))
        if spy_metrics
        else np.nan
    )
    row = {
        **base_row,
        "start_date": metrics["start_date"],
        "end_date": metrics["end_date"],
        "trading_days": len(sliced),
        "regime_available": True,
        "availability_reason": "",
        "start_value": metrics["start_value"],
        "end_value": metrics["end_value"],
        "total_return_pct": metrics["total_return_pct"],
        "cagr_pct": metrics["cagr_pct"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "calmar": metrics["calmar"],
        "volatility_annualized_pct": metrics["volatility_pct"],
        "sharpe_like": metrics["sharpe"],
        "worst_daily_return_pct": round(float(returns.min() * 100.0), 2),
        "best_daily_return_pct": round(float(returns.max() * 100.0), 2),
        "positive_day_rate_pct": round(float((returns > 0).mean() * 100.0), 2),
        "turnover_proxy_if_available": metrics["total_turnover"],
        "btc_weight_max_if_available": round(btc_weight_max, 4),
        "regime_metric_status": "computed",
        "excess_total_return_vs_spy_pct": round(excess, 2) if np.isfinite(excess) else np.nan,
        "drawdown_improvement_vs_spy_pct": round(drawdown_improvement, 2)
        if np.isfinite(drawdown_improvement)
        else np.nan,
        "calmar_diff_vs_spy": round(calmar_diff, 3) if np.isfinite(calmar_diff) else np.nan,
        "beat_spy_in_regime": bool(np.isfinite(excess) and excess > 0),
    }
    return row, None


def build_regime_metrics(
    *,
    candidate_results: dict[str, dict[str, Any]],
    regimes: pd.DataFrame,
    initial_capital: float,
    min_regime_trading_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "canonical_spy_buy_hold" not in candidate_results:
        return pd.DataFrame(), pd.DataFrame()
    spy_result = candidate_results["canonical_spy_buy_hold"]["result"]
    rows: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for candidate in candidate_results.values():
        for regime in regimes.to_dict("records"):
            row, unavailable_row = calculate_regime_metric_row(
                candidate=candidate,
                regime=regime,
                spy_result=spy_result,
                initial_capital=initial_capital,
                min_regime_trading_days=min_regime_trading_days,
            )
            rows.append(row)
            if unavailable_row is not None:
                unavailable.append(unavailable_row)
    return pd.DataFrame(rows), pd.DataFrame(unavailable)


def build_candidate_regime_summary(regime_metrics: pd.DataFrame) -> pd.DataFrame:
    if regime_metrics.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for candidate_id, group in regime_metrics.groupby("canonical_candidate_id", sort=False):
        available = group.loc[group["regime_available"].map(_bool_value)].copy()
        total_regimes = len(group)
        unavailable_count = total_regimes - len(available)
        if available.empty:
            rows.append(
                {
                    "canonical_candidate_id": candidate_id,
                    "candidate_role": _text_value(group.iloc[0].get("candidate_role", "")),
                    "asset_roster": _text_value(group.iloc[0].get("asset_roster", "")),
                    "equity_curve_source": _text_value(
                        group.iloc[0].get("equity_curve_source", "")
                    ),
                    "equity_curve_daily_verified": False,
                    "equity_curve_missing_reason": _text_value(
                        group.iloc[0].get("equity_curve_missing_reason", "")
                    ),
                    "uses_aggregate_metrics_only": False,
                    "regimes_available": 0,
                    "regimes_unavailable": unavailable_count,
                    "positive_return_regimes": 0,
                    "beat_spy_regimes": 0,
                    "worst_max_drawdown_pct": np.nan,
                    "mean_total_return_pct": np.nan,
                    "mean_calmar": np.nan,
                    "regime_metric_status": "unavailable_insufficient_history",
                }
            )
            continue
        rows.append(
            {
                "canonical_candidate_id": candidate_id,
                "candidate_role": _text_value(group.iloc[0].get("candidate_role", "")),
                "asset_roster": _text_value(group.iloc[0].get("asset_roster", "")),
                "uses_btc": "BTC-USD" in _text_value(group.iloc[0].get("asset_roster", "")),
                "equity_curve_source": ";".join(
                    sorted(available["equity_curve_source"].dropna().astype(str).unique())
                )
                if "equity_curve_source" in available.columns
                else "",
                "equity_curve_daily_verified": bool(
                    available.get("equity_curve_daily_verified", pd.Series([True]))
                    .map(_bool_value)
                    .all()
                ),
                "equity_curve_missing_reason": "",
                "uses_aggregate_metrics_only": bool(
                    available.get("uses_aggregate_metrics_only", pd.Series([False]))
                    .map(_bool_value)
                    .any()
                ),
                "regimes_available": len(available),
                "regimes_unavailable": unavailable_count,
                "positive_return_regimes": int(
                    (pd.to_numeric(available["total_return_pct"], errors="coerce") > 0).sum()
                ),
                "beat_spy_regimes": int(available["beat_spy_in_regime"].map(_bool_value).sum()),
                "worst_max_drawdown_pct": round(
                    float(pd.to_numeric(available["max_drawdown_pct"], errors="coerce").min()),
                    2,
                ),
                "mean_total_return_pct": round(
                    float(pd.to_numeric(available["total_return_pct"], errors="coerce").mean()),
                    2,
                ),
                "mean_calmar": round(
                    float(pd.to_numeric(available["calmar"], errors="coerce").mean()),
                    3,
                ),
                "mean_excess_total_return_vs_spy_pct": round(
                    float(
                        pd.to_numeric(
                            available["excess_total_return_vs_spy_pct"],
                            errors="coerce",
                        ).mean()
                    ),
                    2,
                ),
                "regime_metric_status": "computed",
            }
        )
    return pd.DataFrame(rows)


def build_regime_robustness_scores(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    out = summary.copy()
    total_regimes = (
        out["regimes_available"].astype(float) + out["regimes_unavailable"].astype(float)
    ).replace(0, np.nan)
    out["availability_component"] = (out["regimes_available"].astype(float) / total_regimes).fillna(0.0)
    available = out["regimes_available"].replace(0, np.nan).astype(float)
    out["positive_return_component"] = (
        out["positive_return_regimes"].astype(float) / available
    ).fillna(0.0)
    out["beat_spy_component"] = (
        out["beat_spy_regimes"].astype(float) / available
    ).fillna(0.0)
    worst_dd = pd.to_numeric(out["worst_max_drawdown_pct"], errors="coerce").fillna(-100.0)
    out["drawdown_component"] = (1.0 - worst_dd.abs() / 70.0).clip(0.0, 1.0)
    excess = pd.to_numeric(out["mean_excess_total_return_vs_spy_pct"], errors="coerce").fillna(0.0)
    out["excess_return_component"] = ((excess + 25.0) / 50.0).clip(0.0, 1.0)
    out["btc_dependence_penalty"] = np.where(out.get("uses_btc", False).map(_bool_value), 0.10, 0.0)
    out["regime_robustness_score"] = (
        100.0
        * (
            0.25 * out["availability_component"]
            + 0.20 * out["positive_return_component"]
            + 0.20 * out["beat_spy_component"]
            + 0.20 * out["drawdown_component"]
            + 0.15 * out["excess_return_component"]
            - out["btc_dependence_penalty"]
        )
    ).round(2)
    out["rank_regime_robustness"] = out["regime_robustness_score"].rank(
        ascending=False,
        method="min",
    )
    return out.sort_values("rank_regime_robustness").reset_index(drop=True)


def _mean_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> float:
    if frame.empty or column not in frame.columns:
        return default
    value = pd.to_numeric(frame[column], errors="coerce").mean()
    return float(value) if pd.notna(value) else default


def _min_numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> float:
    if frame.empty or column not in frame.columns:
        return default
    value = pd.to_numeric(frame[column], errors="coerce").min()
    return float(value) if pd.notna(value) else default


def _normalised_drawdown_component(worst_drawdown_pct: float) -> float:
    if not np.isfinite(worst_drawdown_pct):
        return 0.0
    return float(np.clip(1.0 - abs(worst_drawdown_pct) / 70.0, 0.0, 1.0))


def _normalised_calmar_component(mean_calmar: float) -> float:
    if not np.isfinite(mean_calmar):
        return 0.0
    return float(np.clip((mean_calmar + 0.10) / 1.10, 0.0, 1.0))


def _normalised_relative_return_component(mean_excess_return_pct: float) -> float:
    if not np.isfinite(mean_excess_return_pct):
        return 0.0
    return float(np.clip((mean_excess_return_pct + 25.0) / 50.0, 0.0, 1.0))


def _component_score(*components: float) -> float:
    return round(float(np.clip(sum(components), 0.0, 100.0)), 2)


def build_regime_robustness_score_components(regime_metrics: pd.DataFrame) -> pd.DataFrame:
    if regime_metrics.empty:
        return pd.DataFrame()

    total_primary_regimes = int(
        regime_metrics.loc[
            regime_metrics["included_in_primary_subregime_score"].map(_bool_value),
            "regime_name",
        ].nunique()
    )
    rows: list[dict[str, Any]] = []
    for candidate_id, group in regime_metrics.groupby("canonical_candidate_id", sort=False):
        available = group.loc[group["regime_available"].map(_bool_value)].copy()
        primary = available.loc[
            available["included_in_primary_subregime_score"].map(_bool_value)
        ].copy()
        primary_calmar = primary.loc[
            primary["included_in_primary_calmar_score"].map(_bool_value)
        ].copy()
        full_context = available.loc[
            available["is_full_canonical_context"].map(_bool_value)
        ].copy()
        crash = primary.loc[primary["is_crash_regime"].map(_bool_value)].copy()
        major_crash = crash.loc[
            ~crash["short_window_directional_only"].map(_bool_value)
        ].copy()

        available_subregime_count = len(primary)
        available_crash_regime_count = len(crash)
        beat_spy_subregime_count = int(primary["beat_spy_in_regime"].map(_bool_value).sum())
        beat_spy_crash_regime_count = int(crash["beat_spy_in_regime"].map(_bool_value).sum())
        availability_component = (
            available_subregime_count / total_primary_regimes
            if total_primary_regimes
            else 0.0
        )

        worst_dd = _min_numeric(primary, "max_drawdown_pct", default=np.nan)
        mean_calmar = _mean_numeric(primary_calmar, "calmar", default=0.0)
        mean_excess = _mean_numeric(
            primary,
            "excess_total_return_vs_spy_pct",
            default=0.0,
        )
        drawdown_component = _normalised_drawdown_component(worst_dd)
        calmar_component = _normalised_calmar_component(mean_calmar)
        relative_return_component = _normalised_relative_return_component(mean_excess)

        crash_beat_rate = (
            beat_spy_crash_regime_count / available_crash_regime_count
            if available_crash_regime_count
            else 0.0
        )
        crash_positive_rate = (
            float((pd.to_numeric(crash["total_return_pct"], errors="coerce") > 0).mean())
            if not crash.empty
            else 0.0
        )
        crash_worst_dd = _min_numeric(crash, "max_drawdown_pct", default=np.nan)
        crash_drawdown_component = _normalised_drawdown_component(crash_worst_dd)
        crash_survival_component = (
            0.40 * crash_beat_rate
            + 0.25 * crash_positive_rate
            + 0.35 * crash_drawdown_component
        )

        primary_subregime_score = _component_score(
            25.0 * availability_component,
            20.0 * relative_return_component,
            20.0 * drawdown_component,
            15.0 * calmar_component,
            20.0 * crash_survival_component,
        )

        full_canonical_context_score = np.nan
        if not full_context.empty:
            full_excess_component = _normalised_relative_return_component(
                _mean_numeric(full_context, "excess_total_return_vs_spy_pct", default=0.0)
            )
            full_drawdown_component = _normalised_drawdown_component(
                _min_numeric(full_context, "max_drawdown_pct", default=np.nan)
            )
            full_beat_component = float(full_context["beat_spy_in_regime"].map(_bool_value).mean())
            full_canonical_context_score = _component_score(
                40.0 * full_excess_component,
                40.0 * full_drawdown_component,
                20.0 * full_beat_component,
            )

        uses_btc = "BTC-USD" in _text_value(group.iloc[0].get("asset_roster", ""))
        unavailable_count = int((~group["regime_available"].map(_bool_value)).sum())
        inception_limited = (
            unavailable_count > 0
            and group.get("availability_reason", pd.Series(dtype=str))
            .astype(str)
            .str.contains("asset_inception_after_regime_start", na=False)
            .any()
        )
        btc_or_inception_caveat_component = -8.0 if uses_btc else (-3.0 if inception_limited else 0.0)

        blocking_reasons: list[str] = []
        worst_dd_all = _min_numeric(available, "max_drawdown_pct", default=np.nan)
        if np.isfinite(worst_dd_all) and worst_dd_all < -50.0:
            blocking_reasons.append("severe_drawdown_worse_than_minus_50pct")

        crash_drawdown_underperformance = major_crash.loc[
            pd.to_numeric(
                major_crash["drawdown_improvement_vs_spy_pct"],
                errors="coerce",
            )
            <= -10.0
        ]
        if not crash_drawdown_underperformance.empty:
            regimes = ",".join(crash_drawdown_underperformance["regime_name"].astype(str))
            blocking_reasons.append(f"crash_drawdown_worse_than_spy_by_10pp:{regimes}")

        crash_failures = major_crash.loc[
            (
                pd.to_numeric(major_crash["excess_total_return_vs_spy_pct"], errors="coerce")
                < 0
            )
            & (
                pd.to_numeric(
                    major_crash["drawdown_improvement_vs_spy_pct"],
                    errors="coerce",
                )
                < 0
            )
        ]
        multiple_crash_failure = len(crash_failures) >= 2
        if multiple_crash_failure:
            blocking_reasons.append("multiple_major_crash_return_and_drawdown_failures")

        if uses_btc and inception_limited:
            blocking_reasons.append("btc_inception_limited_pre_2014_regime_history")
        elif inception_limited:
            blocking_reasons.append("asset_inception_limited_regime_history")

        hard_gate_penalty_component = 0.0
        if np.isfinite(worst_dd_all) and worst_dd_all < -60.0:
            hard_gate_penalty_component -= 20.0
        elif np.isfinite(worst_dd_all) and worst_dd_all < -50.0:
            hard_gate_penalty_component -= 8.0
        if not crash_drawdown_underperformance.empty:
            hard_gate_penalty_component -= 8.0
        if multiple_crash_failure:
            hard_gate_penalty_component -= 20.0

        final_score = round(
            max(
                0.0,
                primary_subregime_score
                + btc_or_inception_caveat_component
                + hard_gate_penalty_component,
            ),
            2,
        )

        if available_subregime_count < 2:
            classification = "unavailable_insufficient_history"
        elif multiple_crash_failure or (np.isfinite(worst_dd_all) and worst_dd_all < -60.0):
            classification = "rejected_regime_fragile"
        elif uses_btc and final_score >= 35.0:
            classification = "provisional_high_caveat_candidate_for_further_research"
        elif (
            final_score >= 50.0
            and np.isfinite(worst_dd_all)
            and worst_dd_all >= -50.0
            and crash_drawdown_underperformance.empty
        ):
            classification = (
                "provisional_core_inception_limited_for_further_research"
                if inception_limited
                else "provisional_core_candidate_for_further_research"
            )
        elif final_score >= 35.0:
            classification = "research_only"
        else:
            classification = "rejected_regime_fragile"

        rows.append(
            {
                "canonical_candidate_id": candidate_id,
                "candidate_role": _text_value(group.iloc[0].get("candidate_role", "")),
                "asset_roster": _text_value(group.iloc[0].get("asset_roster", "")),
                "uses_btc": uses_btc,
                "regimes_available": len(available),
                "regimes_unavailable": unavailable_count,
                "available_subregime_count": available_subregime_count,
                "available_crash_regime_count": available_crash_regime_count,
                "beat_spy_subregime_count": beat_spy_subregime_count,
                "beat_spy_crash_regime_count": beat_spy_crash_regime_count,
                "primary_subregime_score": primary_subregime_score,
                "full_canonical_context_score": full_canonical_context_score,
                "drawdown_component": round(drawdown_component, 4),
                "calmar_component": round(calmar_component, 4),
                "relative_return_component": round(relative_return_component, 4),
                "availability_component": round(availability_component, 4),
                "crash_survival_component": round(crash_survival_component, 4),
                "btc_or_inception_caveat_component": btc_or_inception_caveat_component,
                "hard_gate_penalty_component": hard_gate_penalty_component,
                "final_regime_robustness_score": final_score,
                "regime_robustness_score": final_score,
                "classification_after_hard_gates": classification,
                "classification_blocking_reasons": ";".join(blocking_reasons),
                "worst_max_drawdown_pct": round(worst_dd_all, 2)
                if np.isfinite(worst_dd_all)
                else np.nan,
                "mean_total_return_pct": round(
                    _mean_numeric(primary, "total_return_pct", default=np.nan),
                    2,
                )
                if not primary.empty
                else np.nan,
                "mean_calmar": round(mean_calmar, 3),
                "mean_excess_total_return_vs_spy_pct": round(mean_excess, 2),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["rank_regime_robustness"] = out["final_regime_robustness_score"].rank(
        ascending=False,
        method="min",
    )
    return out.sort_values("rank_regime_robustness").reset_index(drop=True)


def classify_master_strategy_candidates(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    out = scores.copy()
    if "classification_after_hard_gates" in out.columns:
        out["master_strategy_classification"] = out["classification_after_hard_gates"]
        out["classification_reason"] = out.get(
            "classification_blocking_reasons",
            pd.Series([""] * len(out)),
        ).replace("", "passed_provisional_hard_gate_mapping")
        out["promotion_allowed"] = False
        out["final_model_promoted"] = False
        out["paper_tracking_candidate_only"] = True
        return out

    classifications: list[str] = []
    reasons: list[str] = []
    for row in out.to_dict("records"):
        uses_btc = _bool_value(row.get("uses_btc", False))
        score = _safe_float(row.get("regime_robustness_score"))
        available = int(_safe_float(row.get("regimes_available")))
        worst_dd = _safe_float(row.get("worst_max_drawdown_pct"), -100.0)
        beat_spy = int(_safe_float(row.get("beat_spy_regimes")))
        if available < 2:
            classifications.append("unavailable_insufficient_history")
            reasons.append("fewer_than_two_available_regimes")
        elif worst_dd <= -60.0 or beat_spy == 0:
            classifications.append("rejected_regime_fragile")
            reasons.append("severe_regime_drawdown_or_no_spy_beats")
        elif uses_btc and score >= 45.0:
            classifications.append("provisional_high_caveat_candidate_for_further_research")
            reasons.append("btc_candidate_survived_available_regimes_high_caveat")
        elif not uses_btc and score >= 55.0 and available >= 5 and worst_dd >= -45.0:
            classifications.append("provisional_core_candidate_for_further_research")
            reasons.append("non_btc_candidate_with_broad_regime_score_and_non_severe_drawdown")
        elif score >= 40.0:
            classifications.append("research_only")
            reasons.append("mixed_regime_evidence")
        else:
            classifications.append("rejected_regime_fragile")
            reasons.append("low_regime_robustness_score")
    out["master_strategy_classification"] = classifications
    out["classification_reason"] = reasons
    out["promotion_allowed"] = False
    out["final_model_promoted"] = False
    out["paper_tracking_candidate_only"] = True
    return out


def _plot_heatmap(
    frame: pd.DataFrame,
    *,
    value_col: str,
    title: str,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    available = frame.loc[frame["regime_available"].map(_bool_value)].copy()
    if available.empty:
        path.write_bytes(b"")
        return
    pivot = available.pivot_table(
        index="canonical_candidate_id",
        columns="regime_name",
        values=value_col,
        aggfunc="mean",
    )
    fig, ax = plt.subplots(figsize=(12, max(4, 0.4 * len(pivot))))
    image = ax.imshow(pivot.fillna(0.0), aspect="auto", cmap="RdYlGn")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=7)
    ax.set_title(title)
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_scores(scores: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    if not scores.empty:
        plot_frame = scores.sort_values("rank_regime_robustness").head(12)
        ax.bar(
            plot_frame["canonical_candidate_id"],
            pd.to_numeric(plot_frame["regime_robustness_score"], errors="coerce"),
        )
        ax.tick_params(axis="x", labelrotation=45)
    ax.set_title("Phase 21A Regime Robustness Scores")
    ax.set_ylabel("Score")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _write_dashboard_index(
    *,
    path: Path,
    regimes: pd.DataFrame,
    master_candidates: pd.DataFrame,
    unavailable: pd.DataFrame,
) -> None:
    lines = [
        "# Phase 21A Historical Regime Stress Lab",
        "",
        "**Research/model-selection only. No candidate is promoted.**",
        "",
        "- NO LIVE TRADING",
        "- NO REAL MONEY",
        "- NO BROKER/API",
        "- Phase18/20 safety gates remain mandatory before paper use.",
        "- Full canonical window is context only; it is not double-counted in the primary sub-regime robustness score.",
        "- COVID crash metrics are short-window/directional-only and are not used for Calmar promotion logic.",
        "- Numeric score and hard classification gates are separate: high return scores can still be blocked by drawdown or crash gates.",
        "",
        "## Interpretation",
        "",
        "- SPY/QQQ growth variants are return-strong but regime-fragile when severe drawdown gates are applied.",
        "- GLD/TLT candidates can re-enter as provisional further-research core candidates because they improve regime survivability; this is not a final model promotion.",
        "- BTC candidates are only evaluated in post-inception regimes and remain provisional high-caveat research candidates.",
        "- Phase6 loose_relief is included as the original defensive overlay reference when its verified daily stream is available.",
        "",
        "## Regimes",
        "",
    ]
    for row in regimes.to_dict("records"):
        notes = []
        if _bool_value(row.get("is_full_canonical_context", False)):
            notes.append("context-only")
        if _bool_value(row.get("short_window_directional_only", False)):
            notes.append("short-window/directional-only")
        suffix = f" ({'; '.join(notes)})" if notes else ""
        lines.append(f"- `{row['regime_name']}`: {row['start']} to {row['end']}{suffix}")
    lines.extend(["", "## Provisional Candidate Classifications", ""])
    if master_candidates.empty:
        lines.append("No master candidates were classified.")
    else:
        for row in master_candidates.to_dict("records"):
            lines.append(
                f"- `{row['canonical_candidate_id']}`: "
                f"{row['master_strategy_classification']} "
                f"(score {row['regime_robustness_score']})"
            )
    lines.extend(["", "## Availability Caveats", ""])
    if unavailable.empty:
        lines.append("No unavailable candidate/regime pairs were reported.")
    else:
        lines.append(
            f"{len(unavailable)} candidate/regime pairs were unavailable due to "
            "asset inception, missing data, or insufficient rows."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gate_row(gate_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _empty_outputs(output_dir: Path, dashboard_dir: Path, decision: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for name in [
        "phase21a_regime_metrics.csv",
        "phase21a_candidate_regime_summary.csv",
        "phase21a_regime_robustness_scores.csv",
        "phase21a_regime_robustness_score_components.csv",
        "phase21a_unavailable_candidate_regimes.csv",
        "phase21a_master_strategy_candidates.csv",
    ]:
        outputs[name] = _write_csv(pd.DataFrame(), output_dir / name)
    outputs["summary"] = _write_csv(
        pd.DataFrame([{"phase21a_decision": decision, "all_gates_passed": False}]),
        output_dir / "phase21a_summary.csv",
    )
    outputs["gate_report"] = _write_csv(
        pd.DataFrame([_gate_row("required_equity_curves_available", False)]),
        output_dir / "phase21a_gate_report.csv",
    )
    outputs["conclusion"] = _write_csv(
        pd.DataFrame(
            [
                {
                    "phase21a_decision": decision,
                    "promotion_allowed": False,
                    "live_trading_allowed": False,
                    "real_money_allowed": False,
                    "broker_api_integration_allowed": False,
                }
            ]
        ),
        output_dir / "phase21a_conclusion.csv",
    )
    (dashboard_dir / "index.md").write_text(
        "# Phase 21A Historical Regime Stress Lab\n\nNo metrics available.\n",
        encoding="utf-8",
    )
    return outputs


def save_phase21a_historical_regime_stress_lab(
    *,
    config: dict[str, Any],
    reports_dir: str | Path,
    price_data: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Path]:
    section = _section(config)
    output_dir = Path(
        section.get("output_dir", Path(reports_dir) / "strategy_factory" / "regime_stress")
    )
    dashboard_dir = Path(section.get("dashboard_dir", output_dir / "dashboard"))
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    if not _bool_value(section.get("enabled", False)):
        return _empty_outputs(output_dir, dashboard_dir, "phase21a_disabled")

    reports_path = Path(reports_dir)
    source_finalist_dir = Path(
        section.get(
            "source_finalist_validation_dir",
            reports_path / "strategy_factory" / "finalist_validation",
        )
    )
    phase19b_canonical = _read_csv(source_finalist_dir / "phase19b_canonical_finalists.csv")
    regimes = parse_regime_windows(section)
    candidate_specs = build_phase21a_candidate_specs(
        section=section,
        phase19b_canonical_finalists=phase19b_canonical,
    )
    initial_capital = float(section.get("initial_capital", 10000))
    min_days = int(section.get("min_regime_trading_days", 20))
    candidate_results, reconstruction_unavailable = reconstruct_candidate_results(
        config=config,
        section=section,
        candidate_specs=candidate_specs,
        reports_dir=reports_path,
        price_data=price_data,
    )
    regime_metrics, regime_unavailable = build_regime_metrics(
        candidate_results=candidate_results,
        regimes=regimes,
        initial_capital=initial_capital,
        min_regime_trading_days=min_days,
    )
    unavailable = pd.concat(
        [
            reconstruction_unavailable,
            regime_unavailable,
        ],
        ignore_index=True,
    )
    candidate_summary = build_candidate_regime_summary(regime_metrics)
    score_components = build_regime_robustness_score_components(regime_metrics)
    robustness_scores = score_components.copy()
    master_candidates = classify_master_strategy_candidates(robustness_scores)

    has_unavailable = not unavailable.empty
    live_trading_allowed = _bool_value(section.get("live_trading_allowed", False))
    real_money_allowed = _bool_value(section.get("real_money_allowed", False))
    broker_api_integration_allowed = _bool_value(
        section.get("broker_api_integration_allowed", False)
    )
    gate_report = pd.DataFrame(
        [
            _gate_row("regime_config_loaded", not regimes.empty),
            _gate_row("regime_metrics_written", True),
            _gate_row("candidate_summary_written", True),
            _gate_row("robustness_scores_written", True),
            _gate_row("unavailable_regimes_reported", True),
            _gate_row("master_strategy_candidates_written", True),
            _gate_row("dashboard_index_written", True),
            _gate_row("live_trading_disabled", not live_trading_allowed),
            _gate_row("real_money_disabled", not real_money_allowed),
            _gate_row("broker_api_integration_disabled", not broker_api_integration_allowed),
        ]
    )
    all_gates_passed = bool(gate_report["passed"].map(_bool_value).all())
    if regime_metrics.empty:
        decision = "historical_regime_stress_lab_failed_missing_equity_curves"
    elif has_unavailable:
        decision = "historical_regime_stress_lab_completed_with_unavailable_candidates_no_promotion"
    else:
        decision = "historical_regime_stress_lab_completed_no_promotion"
    if not all_gates_passed:
        decision = "historical_regime_stress_lab_failed_missing_equity_curves"

    summary = pd.DataFrame(
        [
            {
                "phase": "Phase 21A",
                "phase21a_decision": decision,
                "all_gates_passed": all_gates_passed,
                "regimes_tested": len(regimes),
                "candidate_count": len(candidate_specs),
                "computed_metric_rows": int(
                    regime_metrics["regime_available"].map(_bool_value).sum()
                )
                if not regime_metrics.empty
                else 0,
                "unavailable_candidate_regime_rows": len(unavailable),
                "master_candidate_core_count": int(
                    (
                        master_candidates.get(
                            "master_strategy_classification",
                            pd.Series(dtype=str),
                        )
                        .astype(str)
                        .str.startswith("provisional_core")
                    ).sum()
                )
                if not master_candidates.empty
                else 0,
                "master_candidate_high_caveat_count": int(
                    (
                        master_candidates.get(
                            "master_strategy_classification",
                            pd.Series(dtype=str),
                        )
                        == "provisional_high_caveat_candidate_for_further_research"
                    ).sum()
                )
                if not master_candidates.empty
                else 0,
                "promotion_allowed": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "generated_at_utc": _generated_at(),
            }
        ]
    )
    conclusion = pd.DataFrame(
        [
            {
                "phase": "Phase 21A",
                "phase21a_decision": decision,
                "all_gates_passed": all_gates_passed,
                "promotion_allowed": False,
                "final_model_promoted": False,
                "paper_only": True,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
                "notes": (
                    "Historical regime stress research only. No model promotion; "
                    "Phase18/20 safety gates remain mandatory."
                ),
            }
        ]
    )

    outputs: dict[str, Path] = {}
    outputs["summary"] = _write_csv(summary, output_dir / "phase21a_summary.csv")
    outputs["gate_report"] = _write_csv(
        gate_report,
        output_dir / "phase21a_gate_report.csv",
    )
    outputs["conclusion"] = _write_csv(conclusion, output_dir / "phase21a_conclusion.csv")
    outputs["regime_metrics"] = _write_csv(
        regime_metrics,
        output_dir / "phase21a_regime_metrics.csv",
    )
    outputs["candidate_regime_summary"] = _write_csv(
        candidate_summary,
        output_dir / "phase21a_candidate_regime_summary.csv",
    )
    outputs["regime_robustness_scores"] = _write_csv(
        robustness_scores,
        output_dir / "phase21a_regime_robustness_scores.csv",
    )
    outputs["regime_robustness_score_components"] = _write_csv(
        score_components,
        output_dir / "phase21a_regime_robustness_score_components.csv",
    )
    outputs["unavailable_candidate_regimes"] = _write_csv(
        unavailable,
        output_dir / "phase21a_unavailable_candidate_regimes.csv",
    )
    outputs["master_strategy_candidates"] = _write_csv(
        master_candidates,
        output_dir / "phase21a_master_strategy_candidates.csv",
    )

    _write_csv(
        regime_metrics.loc[regime_metrics["regime_available"].map(_bool_value)]
        .sort_values(["regime_name", "total_return_pct"], ascending=[True, False])
        .groupby("regime_name")
        .head(5),
        dashboard_dir / "regime_metrics_top_candidates.csv",
    )
    _write_csv(candidate_summary, dashboard_dir / "candidate_regime_summary.csv")
    _write_csv(robustness_scores, dashboard_dir / "regime_robustness_scores.csv")
    _write_csv(
        score_components,
        dashboard_dir / "regime_robustness_score_components.csv",
    )
    _write_csv(unavailable, dashboard_dir / "unavailable_candidate_regimes.csv")
    _write_csv(master_candidates, dashboard_dir / "master_strategy_candidates.csv")
    _plot_heatmap(
        regime_metrics,
        value_col="total_return_pct",
        title="Phase 21A Regime Total Return (%)",
        path=dashboard_dir / "candidate_regime_return_heatmap.png",
    )
    _plot_heatmap(
        regime_metrics,
        value_col="max_drawdown_pct",
        title="Phase 21A Regime Max Drawdown (%)",
        path=dashboard_dir / "candidate_regime_drawdown_heatmap.png",
    )
    _plot_scores(robustness_scores, dashboard_dir / "regime_robustness_score_bar.png")
    _write_dashboard_index(
        path=dashboard_dir / "index.md",
        regimes=regimes,
        master_candidates=master_candidates,
        unavailable=unavailable,
    )
    outputs["dashboard_index"] = dashboard_dir / "index.md"
    outputs["candidate_regime_return_heatmap"] = (
        dashboard_dir / "candidate_regime_return_heatmap.png"
    )
    outputs["candidate_regime_drawdown_heatmap"] = (
        dashboard_dir / "candidate_regime_drawdown_heatmap.png"
    )
    outputs["regime_robustness_score_bar"] = dashboard_dir / "regime_robustness_score_bar.png"

    print("Wrote Phase 21A historical regime stress lab reports.")
    return outputs
