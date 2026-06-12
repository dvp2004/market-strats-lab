from pathlib import Path

import numpy as np
import pandas as pd

import market_strats.run_backtest as run_backtest
from market_strats.analysis.dynamic_multi_asset_opportunity_engine import (
    DEFAULT_UNIVERSE,
    _cap_and_redistribute,
    build_feature_store,
    compute_opportunity_scores,
    load_asset_prices,
    save_phase22a_dynamic_multi_asset_opportunity_engine,
)


def _write_price(root: Path, symbol: str, dates: pd.DatetimeIndex, drift: float) -> None:
    output_dir = root / "data" / "fresh" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    values = 100.0 * (1.0 + drift + np.sin(np.arange(len(dates)) / 20) * 0.001).cumprod()
    pd.DataFrame(
        {
            "date": dates,
            "open": values,
            "high": values * 1.01,
            "low": values * 0.99,
            "close": values,
            "adj_close": values,
            "volume": 1000,
        }
    ).to_parquet(output_dir / f"{symbol}.parquet", index=False)


def _write_benchmark_equity(root: Path, dates: pd.DatetimeIndex) -> None:
    output_dir = (
        root
        / "reports"
        / "paper_trading"
        / "regime_informed_tracking"
        / "performance"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    benchmark_names = [
        "SPY Buy & Hold Benchmark",
        "phase6b_loose_relief_execution_realistic_overlay",
        "canonical_spy_qqq_gld_tlt_50_30_10_10",
        "canonical_inverse_vol_63d_btc_usd_qqq_spy",
        "canonical_spy_qqq_60_40",
    ]
    for index, name in enumerate(benchmark_names):
        values = 10_000 * (1.0 + 0.00025 + index * 0.00001) ** np.arange(len(dates))
        for date, value in zip(dates, values):
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "canonical_candidate_id": name,
                    "portfolio_value": value,
                }
            )
    pd.DataFrame(rows).to_csv(
        output_dir / "regime_informed_historical_daily_equity.csv",
        index=False,
    )


def _fixture_root(tmp_path: Path) -> Path:
    dates = pd.bdate_range("2020-01-01", periods=520)
    for symbol, drift in {
        "SPY": 0.0004,
        "QQQ": 0.00055,
        "TLT": 0.0001,
        "GLD": 0.0002,
        "USO": 0.0003,
        "BTC-USD": 0.0008,
    }.items():
        _write_price(tmp_path, symbol, dates, drift)
    _write_benchmark_equity(tmp_path, dates)
    return tmp_path


def _config(tmp_path: Path) -> dict:
    return {
        "phase22a_dynamic_multi_asset_opportunity_engine": {
            "enabled": True,
            "output_dir": str(tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"),
            "dashboard_dir": str(tmp_path / "reports" / "paper_trading" / "dashboard"),
            "starting_cash": 10_000,
            "transaction_cost_bps_cases": [0, 10, 25],
            "max_single_asset_weight": 0.50,
            "max_btc_weight": 0.05,
            "max_oil_weight": 0.10,
            "max_commodity_weight": 0.20,
            "paper_only": True,
            "live_trading_allowed": False,
            "real_money_allowed": False,
            "broker_api_integration_allowed": False,
            "promotion_allowed": False,
        }
    }


def test_asset_universe_availability_and_feature_store_outputs(tmp_path):
    root = _fixture_root(tmp_path)
    prices, availability = load_asset_prices(root, DEFAULT_UNIVERSE)
    feature_store = build_feature_store(prices)
    scores = compute_opportunity_scores(feature_store)

    assert {"SPY", "QQQ", "BTC-USD", "CASH"}.issubset(set(availability["symbol"]))
    assert not feature_store.empty
    assert not scores.empty
    assert "macro_score" in feature_store.columns
    assert "opportunity_score" in scores.columns


def test_features_do_not_use_future_prices(tmp_path):
    root = _fixture_root(tmp_path)
    prices, _availability = load_asset_prices(root, ["SPY", "QQQ", "CASH"])
    original = build_feature_store(prices)
    changed = prices.copy()
    changed.loc[changed.index[-1], "QQQ"] *= 10
    changed_features = build_feature_store(changed)
    check_date = prices.index[-2]
    original_row = original.loc[
        (pd.to_datetime(original["date"]) == check_date) & (original["symbol"] == "QQQ"),
        "return_63d",
    ].iloc[0]
    changed_row = changed_features.loc[
        (pd.to_datetime(changed_features["date"]) == check_date)
        & (changed_features["symbol"] == "QQQ"),
        "return_63d",
    ].iloc[0]
    assert original_row == changed_row


def test_weight_caps_are_respected():
    raw = pd.Series({"SPY": 10.0, "QQQ": 8.0, "BTC-USD": 5.0, "USO": 4.0, "GLD": 4.0})

    weights = _cap_and_redistribute(
        raw,
        max_single_asset_weight=0.50,
        max_btc_weight=0.05,
        max_oil_weight=0.10,
        max_commodity_weight=0.20,
    )

    assert weights.sum() <= 1.000001
    assert weights.get("BTC-USD", 0.0) <= 0.05
    assert weights.get("USO", 0.0) <= 0.10
    assert weights.max() <= 0.50
    assert weights.reindex(["GLD", "SLV", "DBC", "USO"]).fillna(0.0).sum() <= 0.20


def test_phase22a_outputs_charts_benchmarks_and_safety_flags(tmp_path):
    _fixture_root(tmp_path)

    outputs = save_phase22a_dynamic_multi_asset_opportunity_engine(
        config=_config(tmp_path),
        reports_dir=tmp_path / "reports",
    )

    output_dir = tmp_path / "reports" / "strategy_factory" / "dynamic_opportunity_engine"
    assert (output_dir / "phase22a_asset_universe_availability.csv").exists()
    assert (output_dir / "phase22a_feature_store_panel.csv").exists()
    assert (output_dir / "phase22a_feature_store_latest.csv").exists()
    assert (output_dir / "phase22a_opportunity_scores.csv").exists()
    assert (output_dir / "phase22a_transaction_cost_sensitivity.csv").exists()
    assert (output_dir / "phase22a_benchmark_comparison.csv").exists()
    assert (output_dir / "visuals" / "phase22a_equity_curves.png").exists()
    assert not outputs["metrics"].empty
    comparison_names = set(outputs["comparison"]["strategy_name"])
    assert "SPY Buy & Hold Benchmark" in comparison_names
    assert "canonical_spy_qqq_60_40" in comparison_names
    assert "canonical_inverse_vol_63d_btc_usd_qqq_spy" in comparison_names
    assert set(outputs["transaction_cost_sensitivity"]["transaction_cost_bps"]) == {0, 10, 25}
    summary = outputs["summary"].iloc[0]
    assert not summary["promotion_allowed"]
    assert not summary["live_trading_allowed"]
    assert not summary["real_money_allowed"]
    assert not summary["broker_api_integration_allowed"]


def test_phase22a_focused_runner_flag_exists_and_daily_runner_skips_phase22a():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    assert "--phase22a-only" in source
    assert "_run_phase22a_dynamic_multi_asset_opportunity_engine(" in source
    daily_start = source.index("def _run_daily_paper_workflow")
    daily_end = source.index("def main()")
    daily_source = source[daily_start:daily_end]
    assert "phase22a_dynamic_multi_asset_opportunity_engine" not in daily_source
