from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from market_strats.analysis.annual_rebalance_audit import (
    create_annual_rebalance_audit,
    create_annual_rebalance_audit_summary,
    write_annual_rebalance_audit_markdown,
)
from market_strats.analysis.comparison import (
    create_strategy_scorecard,
    create_strategy_verdicts,
    write_scorecard_markdown,
)
from market_strats.analysis.core_satellite_diagnostic import (
    create_core_satellite_diagnostic,
    write_core_satellite_diagnostic_markdown,
)
from market_strats.analysis.cross_asset_diagnostics import (
    create_buy_hold_vs_momentum_diagnostic,
    write_buy_hold_vs_momentum_markdown,
)
from market_strats.analysis.dual_momentum_audit import (
    create_allocation_audit,
    create_cash_reason_summary,
    create_holding_segments,
    write_dual_momentum_audit_markdown,
)
from market_strats.analysis.dual_momentum_opportunity import (
    create_opportunity_cost_segments,
    create_opportunity_cost_summary,
    write_dual_momentum_opportunity_markdown,
)
from market_strats.analysis.expanded_universe_diagnostic import (
    create_expanded_universe_diagnostic,
    write_expanded_universe_diagnostic_markdown,
)
from market_strats.analysis.metrics import calculate_metrics
from market_strats.analysis.momentum_robustness import (
    run_momentum_window_robustness,
    write_momentum_robustness_markdown,
)
from market_strats.analysis.plots import plot_drawdowns, plot_equity_curves
from market_strats.analysis.rebalance_month_sensitivity import (
    run_rebalance_month_sensitivity,
    write_rebalance_month_sensitivity_markdown,
)
from market_strats.analysis.regimes import calculate_regime_metrics, create_regime_summary
from market_strats.analysis.rolling import (
    calculate_rolling_window_metrics,
    create_rolling_summary,
)
from market_strats.analysis.sma_window_robustness import (
    create_sma_window_robustness_summary,
    run_sma_window_robustness,
    write_sma_window_robustness_markdown,
)
from market_strats.analysis.strategy_purpose import (
    classify_strategy_purpose,
    write_strategy_purpose_markdown,
)
from market_strats.data.cash_rates import (
    align_cash_returns_to_price_dates,
    fetch_cash_yield_rates,
    load_cash_rates_from_parquet,
    save_cash_rates_to_parquet,
)
from market_strats.data.fetch_yfinance import (
    fetch_daily_prices,
    load_prices_from_parquet,
    save_prices_to_parquet,
)
from market_strats.data.validation import validate_price_data
from market_strats.strategies.absolute_momentum import run_absolute_momentum_strategy
from market_strats.strategies.buy_and_hold import run_buy_and_hold
from market_strats.strategies.core_satellite import (
    run_annual_rebalanced_core_satellite_strategy,
    run_independent_core_satellite_strategy,
)
from market_strats.strategies.daily_sma_trend import run_daily_sma_trend_strategy
from market_strats.strategies.drawdown_tranche import run_drawdown_tranche_strategy
from market_strats.strategies.dual_momentum import run_dual_momentum_strategy
from market_strats.strategies.sma_trend import run_sma_trend_strategy
from market_strats.strategies.trend_filtered_drawdown import (
    run_trend_filtered_drawdown_strategy,
)
from market_strats.analysis.monthly_sma_window_robustness import (
    create_monthly_sma_window_robustness_summary,
    run_monthly_sma_window_robustness,
    write_monthly_sma_window_robustness_markdown,
)
from market_strats.analysis.candidate_portfolio import run_candidate_portfolio_report
from market_strats.analysis.final_strategy_report import (
    save_final_strategy_decision_report,
)
from market_strats.analysis.finalist_holdout_validation import (
    save_finalist_holdout_validation_report,
)
from market_strats.analysis.final_validation_conclusion import (
    save_final_validation_conclusion,
)
from market_strats.analysis.relative_momentum_report import (
    run_relative_momentum_allocator_report,
)
from market_strats.analysis.relative_momentum_decision_report import (
    save_relative_momentum_variant_decision_report,
)
from market_strats.analysis.relative_momentum_holdout_validation import (
    save_relative_momentum_holdout_validation_report,
)
from market_strats.analysis.relative_momentum_validation_conclusion import (
    save_relative_momentum_validation_conclusion,
)
from market_strats.analysis.relative_momentum_regime_diagnostic import (
    save_relative_momentum_regime_diagnostic,
)
from market_strats.analysis.regime_switch_overlay_report import (
    run_regime_switch_overlay_report,
)
from market_strats.analysis.regime_switch_overlay_audit import (
    save_regime_switch_overlay_audit,
)
from market_strats.analysis.regime_switch_overlay_decision_report import (
    save_regime_switch_overlay_decision_report,
)
from market_strats.analysis.regime_switch_overlay_holdout_validation import (
    save_regime_switch_overlay_holdout_validation_report,
)
from market_strats.analysis.regime_switch_overlay_validation_conclusion import (
    save_regime_switch_overlay_validation_conclusion,
)
from market_strats.analysis.regime_switch_overlay_slippage_sensitivity import (
    save_regime_switch_overlay_slippage_sensitivity,
)
from market_strats.analysis.regime_switch_overlay_cash_sensitivity import (
    save_regime_switch_overlay_cash_sensitivity,
)
from market_strats.analysis.regime_switch_overlay_raw_close_signal_sensitivity import (
    save_regime_switch_overlay_raw_close_signal_sensitivity,
)
from market_strats.analysis.phase3a_robustness_conclusion import (
    save_phase3a_robustness_conclusion,
)
from market_strats.analysis.secondary_data_source_cross_check import (
    save_secondary_data_source_cross_check,
)
from market_strats.analysis.asset_expansion_diagnostic import (
    save_asset_expansion_diagnostic,
)
from market_strats.analysis.asset_expansion_conclusion import (
    save_asset_expansion_conclusion,
)
from market_strats.analysis.eth_quarantine_diagnostic import (
    save_eth_quarantine_diagnostic,
)

def _apply_research_period_filter_to_result(
    result: pd.DataFrame,
    config: dict,
    strategy_name: str,
) -> pd.DataFrame:
    research_period = config.get("research_period", {})
    research_end_date = research_period.get("end_date")

    filtered = result.copy()

    if "date" not in filtered.columns:
        raise ValueError(f"{strategy_name} result has no date column.")

    filtered["date"] = pd.to_datetime(filtered["date"])

    if research_end_date is not None:
        end_timestamp = pd.to_datetime(research_end_date)
        filtered = filtered[filtered["date"] <= end_timestamp].copy()

    filtered = filtered.sort_values("date").reset_index(drop=True)

    if filtered.empty:
        raise ValueError(
            f"{strategy_name} has no rows after applying research-period result filter."
        )

    actual_end_date = filtered["date"].max().date()

    if research_end_date is not None and actual_end_date > pd.to_datetime(
        research_end_date
    ).date():
        raise ValueError(
            f"{strategy_name} result filter failed. "
            f"Expected end <= {research_end_date}, got {actual_end_date}."
        )

    return filtered

def _apply_research_period_filter(
    prices: pd.DataFrame,
    config: dict,
    ticker: str,
) -> pd.DataFrame:
    research_period = config.get("research_period", {})
    research_end_date = research_period.get("end_date")

    filtered = prices.copy()
    filtered["date"] = pd.to_datetime(filtered["date"])

    raw_max_date = filtered["date"].max().date()

    if research_end_date is not None:
        end_timestamp = pd.to_datetime(research_end_date)

        filtered = filtered[filtered["date"] <= end_timestamp].copy()

        if filtered.empty:
            raise ValueError(
                f"{ticker} has no price data on or before research_period.end_date="
                f"{research_end_date}. Raw max date was {raw_max_date}."
            )

        filtered_max_date = filtered["date"].max().date()

        if filtered_max_date > end_timestamp.date():
            raise ValueError(
                f"{ticker} research period filter failed. "
                f"Expected max date <= {end_timestamp.date()}, "
                f"got {filtered_max_date}."
            )

        print(
            f"{ticker}: research period filter applied. "
            f"raw_max_date={raw_max_date}, filtered_max_date={filtered_max_date}"
        )

    return filtered.sort_values("date").reset_index(drop=True)

def _preserve_price_data_for_outputs(price_data: pd.DataFrame) -> pd.DataFrame:
    """Return a clean copy of raw price data for downstream diagnostics.

    Strategy result frames usually retain only adjusted close and derived fields.
    Phase 3 raw-close signal sensitivity needs access to the original raw close,
    so the unmodified price dataframe is preserved in ``ticker_outputs``.

    Preferred schema:
    - date
    - close       raw/unadjusted close from Yahoo
    - adj_close   adjusted close used for return calculations

    If older cached data does not contain ``close``, this function keeps the run
    alive by falling back to ``adj_close`` and marking the row as not truly raw.
    Freshly downloaded ETF files should contain a real ``close`` column because
    ``fetch_yfinance.py`` maps Yahoo ``Close`` to ``close``.
    """

    preserved = price_data.copy()
    preserved["date"] = pd.to_datetime(preserved["date"])
    preserved = preserved.sort_values("date").reset_index(drop=True)

    required_columns = {"date", "adj_close"}
    missing_columns = required_columns - set(preserved.columns)

    if missing_columns:
        raise ValueError(
            f"Price data missing required columns before preserving output: "
            f"{sorted(missing_columns)}"
        )

    if "close" not in preserved.columns:
        preserved["close"] = preserved["adj_close"]
        preserved["raw_close_available"] = False
    else:
        preserved["raw_close_available"] = True

    preserved["close"] = preserved["close"].astype(float)
    preserved["adj_close"] = preserved["adj_close"].astype(float)

    return preserved

def load_config(config_path: str | Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def get_tickers(config: dict) -> list[str]:
    if "tickers" in config and config["tickers"]:
        return [str(ticker).upper() for ticker in config["tickers"]]

    if "ticker" in config and config["ticker"]:
        return [str(config["ticker"]).upper()]

    raise ValueError("Config must contain either 'ticker' or 'tickers'")


def get_dual_momentum_pairs(config: dict) -> list[dict]:
    pairs = config.get("dual_momentum_pairs", [])
    validated_pairs = []

    for pair in pairs:
        name = str(pair["name"])
        assets = [str(asset).upper() for asset in pair["assets"]]

        if len(assets) != 2:
            raise ValueError(f"Dual momentum pair {name} must contain exactly 2 assets")

        validated_pairs.append({"name": name, "assets": assets})

    return validated_pairs


def get_core_satellite_config(config: dict) -> dict | None:
    core_satellite_config = config.get("core_satellite")

    if not core_satellite_config:
        return None

    if not bool(core_satellite_config.get("enabled", False)):
        return None

    ticker = str(core_satellite_config["ticker"]).upper()
    core_weight = float(core_satellite_config["core_weight"])
    satellite_weight = float(core_satellite_config["satellite_weight"])
    rebalance_mode = str(core_satellite_config["rebalance_mode"])

    if rebalance_mode != "independent_sleeves":
        raise ValueError("Only independent_sleeves rebalance_mode is supported for now")

    if round(core_weight + satellite_weight, 10) != 1.0:
        raise ValueError("core_weight + satellite_weight must equal 1")

    return {
        "ticker": ticker,
        "core_weight": core_weight,
        "satellite_weight": satellite_weight,
        "satellite_strategy": str(core_satellite_config["satellite_strategy"]),
        "rebalance_mode": rebalance_mode,
    }


def make_safe_filename(value: str) -> str:
    return (
        value.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def get_or_fetch_prices(ticker: str, config: dict) -> pd.DataFrame:
    ticker = ticker.upper()
    processed_dir = Path("data/processed")
    price_path = processed_dir / f"{ticker}.parquet"

    if price_path.exists():
        print(f"Loading existing data from {price_path}")
        prices = load_prices_from_parquet(ticker, processed_dir)
    else:
        print(f"Fetching {ticker} data from yfinance")
        prices = fetch_daily_prices(
            ticker=ticker,
            start_date=config["start_date"],
            end_date=config.get("end_date"),
        )
        save_path = save_prices_to_parquet(prices, ticker, processed_dir)
        print(f"Saved data to {save_path}")

    validate_price_data(prices, ticker)
    return prices


def get_or_fetch_cash_returns(config: dict, price_dates: pd.Series) -> pd.Series:
    use_cash_yield = bool(config.get("use_cash_yield", False))

    if not use_cash_yield:
        return pd.Series(0.0, index=pd.to_datetime(price_dates), name="cash_return")

    cash_ticker = config["cash_ticker"]
    processed_dir = Path("data/processed")
    safe_ticker = cash_ticker.replace("^", "")
    cash_path = processed_dir / f"{safe_ticker.upper()}_cash_rates.parquet"

    if cash_path.exists():
        print(f"Loading existing cash yield data from {cash_path}")
        cash_rates = load_cash_rates_from_parquet(cash_ticker, processed_dir)
    else:
        print(f"Fetching cash yield data from yfinance: {cash_ticker}")
        cash_rates = fetch_cash_yield_rates(
            ticker=cash_ticker,
            start_date=config["start_date"],
            end_date=config.get("end_date"),
        )
        save_path = save_cash_rates_to_parquet(cash_rates, cash_ticker, processed_dir)
        print(f"Saved cash yield data to {save_path}")

    return align_cash_returns_to_price_dates(cash_rates, price_dates)


def save_annual_rebalance_audit_reports(
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    ticker: str,
    reports_dir: Path,
) -> tuple[Path | None, Path | None, Path | None]:
    if audit.empty:
        return None, None, None

    audit_path = reports_dir / f"{ticker}_annual_rebalance_audit.csv"
    summary_path = reports_dir / f"{ticker}_annual_rebalance_audit_summary.csv"
    markdown_path = reports_dir / f"{ticker}_annual_rebalance_audit.md"

    audit.to_csv(audit_path, index=False)
    summary.to_csv(summary_path, index=False)
    write_annual_rebalance_audit_markdown(
        audit=audit,
        summary=summary,
        output_path=markdown_path,
    )

    return audit_path, summary_path, markdown_path


def run_backtest_for_ticker(
    ticker: str,
    config: dict,
    reports_dir: Path,
) -> dict[str, pd.DataFrame]:
    print(f"\n{'=' * 100}")
    print(f"Running strategy suite for {ticker}")
    print(f"{'=' * 100}")

    initial_capital = float(config["initial_capital"])
    sma_months = int(config["sma_months"])
    sma_days = int(config["sma_days"])
    momentum_months = int(config["momentum_months"])
    slippage_bps = float(config["slippage_bps"])

    drawdown_base_allocation = float(config["drawdown_base_allocation"])
    drawdown_tranche_allocation = float(config["drawdown_tranche_allocation"])
    drawdown_levels = [float(level) for level in config["drawdown_levels"]]
    trend_filtered_drawdown_off_allocation = float(
        config["trend_filtered_drawdown_off_allocation"]
    )

    core_satellite_config = get_core_satellite_config(config)

    core_satellite_strategy_name: str | None = None
    annual_rebalanced_core_satellite_strategy_name: str | None = None
    core_satellite_diagnostic_df = pd.DataFrame()
    core_satellite_diagnostic_path: Path | None = None
    core_satellite_diagnostic_markdown_path: Path | None = None

    annual_rebalance_audit_df = pd.DataFrame()
    annual_rebalance_audit_summary_df = pd.DataFrame()
    annual_rebalance_audit_path: Path | None = None
    annual_rebalance_audit_summary_path: Path | None = None
    annual_rebalance_audit_markdown_path: Path | None = None

    rebalance_month_sensitivity_df = pd.DataFrame()
    rebalance_month_sensitivity_path: Path | None = None
    rebalance_month_sensitivity_markdown_path: Path | None = None

    sma_window_robustness_df = pd.DataFrame()
    sma_window_robustness_summary_df = pd.DataFrame()
    sma_window_robustness_path: Path | None = None
    sma_window_robustness_summary_path: Path | None = None
    sma_window_robustness_markdown_path: Path | None = None

    monthly_sma_window_robustness_df = pd.DataFrame()
    monthly_sma_window_robustness_summary_df = pd.DataFrame()
    monthly_sma_window_robustness_path = None
    monthly_sma_window_robustness_summary_path = None
    monthly_sma_window_robustness_markdown_path = None

    prices = get_or_fetch_prices(ticker, config)
    prices = _apply_research_period_filter(prices=prices, config=config, ticker=ticker)

    preserved_price_data = _preserve_price_data_for_outputs(prices)
    cash_returns = get_or_fetch_cash_returns(config, prices["date"])

    actual_start_date = pd.to_datetime(prices["date"]).min().date()
    actual_end_date = pd.to_datetime(prices["date"]).max().date()
    print(f"{ticker} available test period: {actual_start_date} to {actual_end_date}")

    buy_hold = run_buy_and_hold(
        prices=prices,
        initial_capital=initial_capital,
        cash_returns=cash_returns,
    )
    sma_trend = run_sma_trend_strategy(
        prices=prices,
        initial_capital=initial_capital,
        sma_months=sma_months,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )
    daily_sma_trend = run_daily_sma_trend_strategy(
        prices=prices,
        initial_capital=initial_capital,
        sma_days=sma_days,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )
    absolute_momentum = run_absolute_momentum_strategy(
        prices=prices,
        initial_capital=initial_capital,
        momentum_months=momentum_months,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )
    drawdown_tranche = run_drawdown_tranche_strategy(
        prices=prices,
        initial_capital=initial_capital,
        base_allocation=drawdown_base_allocation,
        tranche_allocation=drawdown_tranche_allocation,
        drawdown_levels=drawdown_levels,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )
    trend_filtered_drawdown = run_trend_filtered_drawdown_strategy(
        prices=prices,
        initial_capital=initial_capital,
        base_allocation=drawdown_base_allocation,
        tranche_allocation=drawdown_tranche_allocation,
        drawdown_levels=drawdown_levels,
        momentum_months=momentum_months,
        trend_off_allocation=trend_filtered_drawdown_off_allocation,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )

    results = {
        "Buy and Hold": buy_hold,
        f"{sma_months}-Month SMA": sma_trend,
        f"{sma_days}-Day SMA": daily_sma_trend,
        f"{momentum_months}-Month Absolute Momentum": absolute_momentum,
        "Drawdown Tranche": drawdown_tranche,
        "Trend-Filtered Drawdown": trend_filtered_drawdown,
    }

    if core_satellite_config is not None and ticker == core_satellite_config["ticker"]:
        core_weight = core_satellite_config["core_weight"]
        satellite_weight = core_satellite_config["satellite_weight"]

        core_satellite_strategy_name = (
            f"{int(core_weight * 100)}/{int(satellite_weight * 100)} "
            "Core-Satellite SPY B&H + 12M Momentum"
        )
        annual_rebalanced_core_satellite_strategy_name = (
            f"{int(core_weight * 100)}/{int(satellite_weight * 100)} "
            "Annual Rebalanced Core-Satellite SPY B&H + 12M Momentum"
        )

        core_satellite = run_independent_core_satellite_strategy(
            core_result=buy_hold,
            satellite_result=absolute_momentum,
            initial_capital=initial_capital,
            core_weight=core_weight,
            satellite_weight=satellite_weight,
            strategy_name=core_satellite_strategy_name,
        )
        annual_rebalanced_core_satellite = run_annual_rebalanced_core_satellite_strategy(
            core_result=buy_hold,
            satellite_result=absolute_momentum,
            initial_capital=initial_capital,
            core_weight=core_weight,
            satellite_weight=satellite_weight,
            strategy_name=annual_rebalanced_core_satellite_strategy_name,
            slippage_bps=slippage_bps,
        )

        annual_rebalance_audit_df = create_annual_rebalance_audit(
            result=annual_rebalanced_core_satellite,
            strategy_name=annual_rebalanced_core_satellite_strategy_name,
        )
        annual_rebalance_audit_summary_df = create_annual_rebalance_audit_summary(
            annual_rebalance_audit_df
        )

        results[core_satellite_strategy_name] = core_satellite
        results[annual_rebalanced_core_satellite_strategy_name] = (
            annual_rebalanced_core_satellite
        )

        rebalance_months = [
            int(month)
            for month in config.get(
                "rebalance_month_sensitivity_months",
                [3, 6, 9, 12],
            )
        ]

        rebalance_month_sensitivity_df = run_rebalance_month_sensitivity(
            core_result=buy_hold,
            satellite_result=absolute_momentum,
            initial_capital=initial_capital,
            core_weight=core_weight,
            satellite_weight=satellite_weight,
            slippage_bps=slippage_bps,
            rebalance_months=rebalance_months,
        )

        rebalance_month_sensitivity_path = (
            reports_dir / f"{ticker}_rebalance_month_sensitivity.csv"
        )
        rebalance_month_sensitivity_markdown_path = (
            reports_dir / f"{ticker}_rebalance_month_sensitivity.md"
        )

        rebalance_month_sensitivity_df.to_csv(
            rebalance_month_sensitivity_path,
            index=False,
        )
        write_rebalance_month_sensitivity_markdown(
            sensitivity=rebalance_month_sensitivity_df,
            output_path=rebalance_month_sensitivity_markdown_path,
        )

    sma_window_robustness_config = config.get("sma_window_robustness", {})

    if (
        sma_window_robustness_config.get("enabled", False)
        and ticker == str(sma_window_robustness_config.get("ticker", "")).upper()
    ):
        robustness_sma_days = [
            int(value) for value in sma_window_robustness_config["sma_days"]
        ]

        sma_window_robustness_df = run_sma_window_robustness(
            ticker=ticker,
            prices=prices,
            buy_hold_result=buy_hold,
            initial_capital=initial_capital,
            sma_days=robustness_sma_days,
            slippage_bps=slippage_bps,
            cash_returns=cash_returns,
        )

        sma_window_robustness_summary_df = create_sma_window_robustness_summary(
            sma_window_robustness_df,
            anchor_sma_days=int(sma_window_robustness_config.get("anchor_sma_days", 200)),
        )

        sma_window_robustness_path = (
            reports_dir / f"{ticker}_sma_window_robustness.csv"
        )
        sma_window_robustness_summary_path = (
            reports_dir / f"{ticker}_sma_window_robustness_summary.csv"
        )
        sma_window_robustness_markdown_path = (
            reports_dir / f"{ticker}_sma_window_robustness.md"
        )

        sma_window_robustness_df.to_csv(sma_window_robustness_path, index=False)
        sma_window_robustness_summary_df.to_csv(
            sma_window_robustness_summary_path,
            index=False,
        )
        write_sma_window_robustness_markdown(
            robustness=sma_window_robustness_df,
            summary=sma_window_robustness_summary_df,
            output_path=sma_window_robustness_markdown_path,
        )

    monthly_sma_window_robustness_config = config.get(
        "monthly_sma_window_robustness",
        {},
    )

    if (
        monthly_sma_window_robustness_config.get("enabled", False)
        and ticker == monthly_sma_window_robustness_config.get("ticker")
    ):
        robustness_sma_months = [
            int(value)
            for value in monthly_sma_window_robustness_config["sma_months"]
        ]

        monthly_sma_window_robustness_df = run_monthly_sma_window_robustness(
            ticker=ticker,
            prices=prices,
            buy_hold_result=buy_hold,
            initial_capital=initial_capital,
            sma_months=robustness_sma_months,
            slippage_bps=slippage_bps,
            cash_returns=cash_returns,
        )

        monthly_sma_window_robustness_summary_df = (
            create_monthly_sma_window_robustness_summary(
                monthly_sma_window_robustness_df,
                anchor_sma_months=10,
            )
        )

        monthly_sma_window_robustness_path = (
            reports_dir / f"{ticker}_monthly_sma_window_robustness.csv"
        )
        monthly_sma_window_robustness_summary_path = (
            reports_dir / f"{ticker}_monthly_sma_window_robustness_summary.csv"
        )
        monthly_sma_window_robustness_markdown_path = (
            reports_dir / f"{ticker}_monthly_sma_window_robustness.md"
        )

        monthly_sma_window_robustness_df.to_csv(
            monthly_sma_window_robustness_path,
            index=False,
        )
        monthly_sma_window_robustness_summary_df.to_csv(
            monthly_sma_window_robustness_summary_path,
            index=False,
        )
        write_monthly_sma_window_robustness_markdown(
            robustness=monthly_sma_window_robustness_df,
            summary=monthly_sma_window_robustness_summary_df,
            output_path=monthly_sma_window_robustness_markdown_path,
        )

    metrics_df = pd.DataFrame(
        [
            calculate_metrics(result, strategy_name)
            for strategy_name, result in results.items()
        ]
    )
    metrics_df.insert(0, "ticker", ticker)

    metrics_path = reports_dir / f"{ticker}_strategy_comparison_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    equity_plot_path = reports_dir / f"{ticker}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"{ticker}_drawdowns.png"
    plot_equity_curves(results, equity_plot_path)
    plot_drawdowns(results, drawdown_plot_path)

    regime_metrics_df = calculate_regime_metrics(results)
    regime_metrics_df.insert(0, "ticker", ticker)

    regime_summary_df = create_regime_summary(regime_metrics_df)
    if not regime_summary_df.empty and "ticker" not in regime_summary_df.columns:
        regime_summary_df.insert(0, "ticker", ticker)

    regime_metrics_path = reports_dir / f"{ticker}_regime_metrics.csv"
    regime_summary_path = reports_dir / f"{ticker}_regime_summary.csv"
    regime_metrics_df.to_csv(regime_metrics_path, index=False)
    regime_summary_df.to_csv(regime_summary_path, index=False)

    rolling_metrics_df = calculate_rolling_window_metrics(results)
    rolling_metrics_df.insert(0, "ticker", ticker)

    rolling_summary_df = create_rolling_summary(rolling_metrics_df)
    if not rolling_summary_df.empty and "ticker" not in rolling_summary_df.columns:
        rolling_summary_df.insert(0, "ticker", ticker)

    rolling_metrics_path = reports_dir / f"{ticker}_rolling_metrics.csv"
    rolling_summary_path = reports_dir / f"{ticker}_rolling_summary.csv"
    rolling_metrics_df.to_csv(rolling_metrics_path, index=False)
    rolling_summary_df.to_csv(rolling_summary_path, index=False)

    strategy_scorecard_df = create_strategy_scorecard(
        full_period_metrics=metrics_df.drop(columns=["ticker"]),
        rolling_summary=rolling_summary_df.drop(columns=["ticker"])
        if "ticker" in rolling_summary_df.columns
        else rolling_summary_df,
    )
    strategy_scorecard_df = create_strategy_verdicts(strategy_scorecard_df)
    strategy_scorecard_df.insert(0, "ticker", ticker)

    strategy_scorecard_path = reports_dir / f"{ticker}_strategy_scorecard.csv"
    strategy_scorecard_markdown_path = reports_dir / f"{ticker}_strategy_scorecard.md"
    strategy_scorecard_df.to_csv(strategy_scorecard_path, index=False)
    write_scorecard_markdown(
        strategy_scorecard_df.drop(columns=["ticker"]),
        strategy_scorecard_markdown_path,
    )

    strategy_purpose_df = classify_strategy_purpose(
        metrics=metrics_df,
        rolling_summary=rolling_summary_df,
    )
    strategy_purpose_path = reports_dir / f"{ticker}_strategy_purpose_classification.csv"
    strategy_purpose_markdown_path = (
        reports_dir / f"{ticker}_strategy_purpose_classification.md"
    )
    strategy_purpose_df.to_csv(strategy_purpose_path, index=False)
    write_strategy_purpose_markdown(strategy_purpose_df, strategy_purpose_markdown_path)

    if core_satellite_strategy_name is not None:
        core_satellite_diagnostic_df = create_core_satellite_diagnostic(
            metrics=metrics_df.drop(columns=["ticker"]),
            rolling_summary=rolling_summary_df.drop(columns=["ticker"])
            if "ticker" in rolling_summary_df.columns
            else rolling_summary_df,
            core_satellite_strategy=core_satellite_strategy_name,
            annual_rebalanced_core_satellite_strategy=(
                annual_rebalanced_core_satellite_strategy_name
            ),
        )
        core_satellite_diagnostic_path = (
            reports_dir / f"{ticker}_core_satellite_diagnostic.csv"
        )
        core_satellite_diagnostic_markdown_path = (
            reports_dir / f"{ticker}_core_satellite_diagnostic.md"
        )
        core_satellite_diagnostic_df.to_csv(core_satellite_diagnostic_path, index=False)
        write_core_satellite_diagnostic_markdown(
            diagnostic=core_satellite_diagnostic_df,
            output_path=core_satellite_diagnostic_markdown_path,
        )

    (
        annual_rebalance_audit_path,
        annual_rebalance_audit_summary_path,
        annual_rebalance_audit_markdown_path,
    ) = save_annual_rebalance_audit_reports(
        audit=annual_rebalance_audit_df,
        summary=annual_rebalance_audit_summary_df,
        ticker=ticker,
        reports_dir=reports_dir,
    )

    momentum_robustness_months = [
        int(month) for month in config.get("momentum_robustness_months", [])
    ]
    momentum_robustness_path: Path | None = None
    momentum_robustness_rolling_path: Path | None = None
    momentum_robustness_markdown_path: Path | None = None

    if momentum_robustness_months:
        momentum_robustness_df, momentum_robustness_rolling_df, _ = (
            run_momentum_window_robustness(
                prices=prices,
                initial_capital=initial_capital,
                lookback_months=momentum_robustness_months,
                slippage_bps=slippage_bps,
                cash_returns=cash_returns,
            )
        )
        momentum_robustness_df.insert(0, "ticker", ticker)
        momentum_robustness_rolling_df.insert(0, "ticker", ticker)

        momentum_robustness_path = reports_dir / f"{ticker}_momentum_robustness.csv"
        momentum_robustness_rolling_path = (
            reports_dir / f"{ticker}_momentum_robustness_rolling_summary.csv"
        )
        momentum_robustness_markdown_path = (
            reports_dir / f"{ticker}_momentum_robustness.md"
        )
        momentum_robustness_df.to_csv(momentum_robustness_path, index=False)
        momentum_robustness_rolling_df.to_csv(
            momentum_robustness_rolling_path,
            index=False,
        )
        write_momentum_robustness_markdown(
            momentum_robustness_df.drop(columns=["ticker"]),
            momentum_robustness_markdown_path,
        )
    else:
        momentum_robustness_df = pd.DataFrame()

    print("\nFull-period strategy comparison:")
    print(metrics_df.to_string(index=False))

    print("\nRolling-window summary:")
    print(rolling_summary_df.to_string(index=False))

    print("\nStrategy scorecard:")
    print(
        strategy_scorecard_df[
            [
                "composite_rank",
                "ticker",
                "strategy",
                "composite_score",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
                "trade_count",
                "verdict",
            ]
        ].to_string(index=False)
    )

    print("\nStrategy purpose classification:")
    print(
        strategy_purpose_df[
            [
                "ticker",
                "strategy",
                "purpose_classification",
                "wealth_test_pass",
                "pending_validation",
                "cagr_pct",
                "buy_hold_cagr_pct",
                "cagr_delta_vs_buy_hold_pct_points",
                "drawdown_improvement_vs_buy_hold_pct_points",
                "classification_note",
            ]
        ].to_string(index=False)
    )

    if not core_satellite_diagnostic_df.empty:
        print("\nCore-satellite diagnostic:")
        print(core_satellite_diagnostic_df.to_string(index=False))

    if not annual_rebalance_audit_df.empty:
        print("\nAnnual rebalance audit summary:")
        print(annual_rebalance_audit_summary_df.to_string(index=False))

        print("\nAnnual rebalance audit:")
        print(annual_rebalance_audit_df.to_string(index=False))

    if not rebalance_month_sensitivity_df.empty:
        print("\nRebalance-month sensitivity:")
        print(rebalance_month_sensitivity_df.to_string(index=False))

    if not sma_window_robustness_df.empty:
        print("\nSMA window robustness:")
        print(sma_window_robustness_df.to_string(index=False))

        print("\nSMA window robustness summary:")
        print(sma_window_robustness_summary_df.to_string(index=False))

    if not momentum_robustness_df.empty:
        print("\nMomentum-window robustness:")
        print(
            momentum_robustness_df[
                [
                    "ticker",
                    "lookback_months",
                    "end_value",
                    "cagr_pct",
                    "max_drawdown_pct",
                    "sharpe",
                    "trade_count",
                    "rolling_3y_worst_cagr_pct",
                    "rolling_5y_worst_cagr_pct",
                ]
            ].to_string(index=False)
        )

    if not monthly_sma_window_robustness_df.empty:
        print("\nMonthly SMA window robustness:")
        print(monthly_sma_window_robustness_df.to_string(index=False))

        print("\nMonthly SMA window robustness summary:")
        print(monthly_sma_window_robustness_summary_df.to_string(index=False))    

    print(f"\nSaved full-period metrics to: {metrics_path}")
    print(f"Saved regime metrics to: {regime_metrics_path}")
    print(f"Saved regime summary to: {regime_summary_path}")
    print(f"Saved rolling metrics to: {rolling_metrics_path}")
    print(f"Saved rolling summary to: {rolling_summary_path}")
    print(f"Saved strategy scorecard to: {strategy_scorecard_path}")
    print(f"Saved strategy scorecard report to: {strategy_scorecard_markdown_path}")
    print(f"Saved strategy purpose classification to: {strategy_purpose_path}")
    print(
        "Saved strategy purpose classification report to: "
        f"{strategy_purpose_markdown_path}"
    )
    print(f"Saved equity curve chart to: {equity_plot_path}")
    print(f"Saved drawdown chart to: {drawdown_plot_path}")

    if core_satellite_diagnostic_path is not None:
        print(f"Saved core-satellite diagnostic to: {core_satellite_diagnostic_path}")
        print(
            "Saved core-satellite diagnostic report to: "
            f"{core_satellite_diagnostic_markdown_path}"
        )

    if annual_rebalance_audit_path is not None:
        print(f"Saved annual rebalance audit to: {annual_rebalance_audit_path}")
        print(
            "Saved annual rebalance audit summary to: "
            f"{annual_rebalance_audit_summary_path}"
        )
        print(
            "Saved annual rebalance audit report to: "
            f"{annual_rebalance_audit_markdown_path}"
        )

    if rebalance_month_sensitivity_path is not None:
        print(
            "Saved rebalance-month sensitivity to: "
            f"{rebalance_month_sensitivity_path}"
        )
        print(
            "Saved rebalance-month sensitivity report to: "
            f"{rebalance_month_sensitivity_markdown_path}"
        )

    if sma_window_robustness_path is not None:
        print(f"Saved SMA window robustness to: {sma_window_robustness_path}")
        print(
            "Saved SMA window robustness summary to: "
            f"{sma_window_robustness_summary_path}"
        )
        print(
            "Saved SMA window robustness report to: "
            f"{sma_window_robustness_markdown_path}"
        )

    if momentum_robustness_path is not None:
        print(f"Saved momentum robustness to: {momentum_robustness_path}")
        print(
            "Saved momentum robustness rolling summary to: "
            f"{momentum_robustness_rolling_path}"
        )
        print(f"Saved momentum robustness report to: {momentum_robustness_markdown_path}")

    if not monthly_sma_window_robustness_df.empty:
        print("\nMonthly SMA window robustness:")
        print(monthly_sma_window_robustness_df.to_string(index=False))

        print("\nMonthly SMA window robustness summary:")
        print(monthly_sma_window_robustness_summary_df.to_string(index=False))

    return {
        "data": preserved_price_data,
        "price_data": preserved_price_data,
        "cash_returns": cash_returns,
        "metrics": metrics_df,
        "regime_summary": regime_summary_df,
        "rolling_summary": rolling_summary_df,
        "scorecard": strategy_scorecard_df,
        "momentum_robustness": momentum_robustness_df,
        "core_satellite_diagnostic": core_satellite_diagnostic_df,
        "strategy_purpose": strategy_purpose_df,
        "annual_rebalance_audit": annual_rebalance_audit_df,
        "annual_rebalance_audit_summary": annual_rebalance_audit_summary_df,
        "rebalance_month_sensitivity": rebalance_month_sensitivity_df,
        "sma_window_robustness": sma_window_robustness_df,
        "sma_window_robustness_summary": sma_window_robustness_summary_df,
        "monthly_sma_window_robustness": monthly_sma_window_robustness_df,
        "monthly_sma_window_robustness_summary": monthly_sma_window_robustness_summary_df,
        "strategy_results": results,
    }


def write_cross_asset_summaries(
    ticker_outputs: dict[str, dict[str, pd.DataFrame]],
    reports_dir: Path,
) -> None:
    full_metrics = []
    scorecards = []
    rolling_summaries = []
    momentum_robustness = []

    for outputs in ticker_outputs.values():
        if not outputs["metrics"].empty:
            full_metrics.append(outputs["metrics"])

        if not outputs["scorecard"].empty:
            scorecards.append(outputs["scorecard"])

        if not outputs["rolling_summary"].empty:
            rolling_summaries.append(outputs["rolling_summary"])

        if not outputs["momentum_robustness"].empty:
            momentum_robustness.append(outputs["momentum_robustness"])

    combined_metrics = (
        pd.concat(full_metrics, ignore_index=True) if full_metrics else pd.DataFrame()
    )
    combined_scorecards = (
        pd.concat(scorecards, ignore_index=True) if scorecards else pd.DataFrame()
    )
    combined_rolling = (
        pd.concat(rolling_summaries, ignore_index=True)
        if rolling_summaries
        else pd.DataFrame()
    )

    if not combined_metrics.empty:
        combined_metrics.to_csv(
            reports_dir / "cross_asset_strategy_comparison_metrics.csv",
            index=False,
        )

    if not combined_scorecards.empty:
        combined_scorecards.to_csv(
            reports_dir / "cross_asset_strategy_scorecards.csv",
            index=False,
        )

    if not combined_rolling.empty:
        combined_rolling.to_csv(
            reports_dir / "cross_asset_rolling_summaries.csv",
            index=False,
        )

    if not combined_metrics.empty and not combined_scorecards.empty:
        expanded_diagnostic = create_expanded_universe_diagnostic(
            metrics=combined_metrics,
            scorecards=combined_scorecards,
        )
        expanded_diagnostic_path = reports_dir / "expanded_universe_diagnostic.csv"
        expanded_diagnostic_markdown_path = (
            reports_dir / "expanded_universe_diagnostic.md"
        )
        expanded_diagnostic.to_csv(expanded_diagnostic_path, index=False)
        write_expanded_universe_diagnostic_markdown(
            diagnostic=expanded_diagnostic,
            output_path=expanded_diagnostic_markdown_path,
        )

        print("\nExpanded universe diagnostic:")
        print(expanded_diagnostic.to_string(index=False))
        print(f"Saved expanded universe diagnostic to: {expanded_diagnostic_path}")
        print(
            "Saved expanded universe diagnostic report to: "
            f"{expanded_diagnostic_markdown_path}"
        )

    if not combined_metrics.empty and not combined_rolling.empty:
        strategy_purpose = classify_strategy_purpose(
            metrics=combined_metrics,
            rolling_summary=combined_rolling,
        )
        strategy_purpose_path = (
            reports_dir / "cross_asset_strategy_purpose_classification.csv"
        )
        strategy_purpose_markdown_path = (
            reports_dir / "cross_asset_strategy_purpose_classification.md"
        )
        strategy_purpose.to_csv(strategy_purpose_path, index=False)
        write_strategy_purpose_markdown(
            classifications=strategy_purpose,
            output_path=strategy_purpose_markdown_path,
        )

        print("\nCross-asset strategy purpose classification:")
        print(strategy_purpose.to_string(index=False))
        print(
            "Saved cross-asset strategy purpose classification to: "
            f"{strategy_purpose_path}"
        )
        print(
            "Saved cross-asset strategy purpose classification report to: "
            f"{strategy_purpose_markdown_path}"
        )

    if not combined_metrics.empty and not combined_rolling.empty:
        diagnostic = create_buy_hold_vs_momentum_diagnostic(
            metrics=combined_metrics,
            rolling_summary=combined_rolling,
        )
        diagnostic_path = reports_dir / "cross_asset_buy_hold_vs_12m_momentum.csv"
        diagnostic_markdown_path = (
            reports_dir / "cross_asset_buy_hold_vs_12m_momentum.md"
        )
        diagnostic.to_csv(diagnostic_path, index=False)
        write_buy_hold_vs_momentum_markdown(diagnostic, diagnostic_markdown_path)

        print(f"Saved cross-asset diagnostic to: {diagnostic_path}")
        print(f"Saved cross-asset diagnostic report to: {diagnostic_markdown_path}")

    if momentum_robustness:
        combined_momentum_robustness = pd.concat(momentum_robustness, ignore_index=True)
        combined_momentum_robustness.to_csv(
            reports_dir / "cross_asset_momentum_robustness.csv",
            index=False,
        )

    print("\nCross-asset summary files saved into reports/")
    print("Do not compare scorecard numbers across tickers as universal rankings.")
    print("Use each ticker scorecard to rank strategies within that ticker only.")


def run_dual_momentum_pair(
    pair: dict,
    config: dict,
    reports_dir: Path,
) -> dict[str, pd.DataFrame]:
    pair_name = str(pair["name"])
    asset_a, asset_b = pair["assets"]
    safe_pair_name = make_safe_filename(pair_name)

    print(f"\n{'=' * 100}")
    print(f"Running dual momentum pair: {pair_name} ({asset_a} vs {asset_b})")
    print(f"{'=' * 100}")

    initial_capital = float(config["initial_capital"])
    momentum_months = int(config["momentum_months"])
    slippage_bps = float(config["slippage_bps"])

    asset_a_prices = get_or_fetch_prices(asset_a, config)
    asset_b_prices = get_or_fetch_prices(asset_b, config)

    offensive_prices = get_or_fetch_prices(asset_a, config)
    offensive_prices = _apply_research_period_filter(
        prices=offensive_prices,
        config=config,
        ticker=asset_a,
    )

    defensive_prices = get_or_fetch_prices(asset_b, config)
    defensive_prices = _apply_research_period_filter(
        prices=defensive_prices,
        config=config,
        ticker=asset_b,
    )

    common_dates = sorted(
        set(pd.to_datetime(asset_a_prices["date"])).intersection(
            set(pd.to_datetime(asset_b_prices["date"]))
        )
    )

    if not common_dates:
        raise ValueError(f"No overlapping dates for {asset_a} and {asset_b}")

    asset_a_common = asset_a_prices[
        pd.to_datetime(asset_a_prices["date"]).isin(common_dates)
    ].copy()
    asset_b_common = asset_b_prices[
        pd.to_datetime(asset_b_prices["date"]).isin(common_dates)
    ].copy()

    cash_returns = get_or_fetch_cash_returns(
        config=config,
        price_dates=pd.Series(common_dates),
    )

    start_date = pd.to_datetime(common_dates[0]).date()
    end_date = pd.to_datetime(common_dates[-1]).date()
    print(f"{pair_name} common test period: {start_date} to {end_date}")

    asset_a_common = _apply_research_period_filter(
        prices=asset_a_common,
        config=config,
        ticker=asset_a,
    )

    asset_b_common = _apply_research_period_filter(
        prices=asset_b_common,
        config=config,
        ticker=asset_b,
    )

    common_dates = sorted(
        set(pd.to_datetime(asset_a_common["date"]))
        .intersection(set(pd.to_datetime(asset_b_common["date"])))
    )

    asset_a_common = asset_a_common[
        pd.to_datetime(asset_a_common["date"]).isin(common_dates)
    ].copy()

    asset_b_common = asset_b_common[
        pd.to_datetime(asset_b_common["date"]).isin(common_dates)
    ].copy()

    buy_hold_a = run_buy_and_hold(
        prices=asset_a_common,
        initial_capital=initial_capital,
        cash_returns=cash_returns,
    )
    buy_hold_a = _apply_research_period_filter_to_result(
        result=buy_hold_a,
        config=config,
        strategy_name=f"Buy and Hold {asset_a}",
    )

    buy_hold_b = run_buy_and_hold(
        prices=asset_b_common,
        initial_capital=initial_capital,
        cash_returns=cash_returns,
    )
    buy_hold_b = _apply_research_period_filter_to_result(
        result=buy_hold_b,
        config=config,
        strategy_name=f"Buy and Hold {asset_b}",
    )

    dual_momentum = run_dual_momentum_strategy(
        asset_a_prices=asset_a_common,
        asset_b_prices=asset_b_common,
        asset_a_name=asset_a,
        asset_b_name=asset_b,
        initial_capital=initial_capital,
        momentum_months=momentum_months,
        slippage_bps=slippage_bps,
        cash_returns=cash_returns,
    )
    dual_momentum = _apply_research_period_filter_to_result(
        result=dual_momentum,
        config=config,
        strategy_name=f"Dual Momentum {asset_a}/{asset_b}",
    )

    expected_end = pd.to_datetime(config["research_period"]["end_date"]).date()

    for name, frame in {
        f"Buy and Hold {asset_a}": buy_hold_a,
        f"Buy and Hold {asset_b}": buy_hold_b,
        f"Dual Momentum {asset_a}/{asset_b}": dual_momentum,
    }.items():
        max_date = pd.to_datetime(frame["date"]).max().date()

        if max_date > expected_end:
            raise ValueError(
                f"{name} still exceeds research end date. "
                f"Expected <= {expected_end}, got {max_date}."
            )

    dual_strategy_name = f"Dual Momentum {asset_a}/{asset_b}"
    results = {
        f"Buy and Hold {asset_a}": buy_hold_a,
        f"Buy and Hold {asset_b}": buy_hold_b,
        dual_strategy_name: dual_momentum,
    }

    metrics_df = pd.DataFrame(
        [
            calculate_metrics(buy_hold_a, f"Buy and Hold {asset_a}"),
            calculate_metrics(buy_hold_b, f"Buy and Hold {asset_b}"),
            calculate_metrics(dual_momentum, dual_strategy_name),
        ]
    )
    metrics_df.insert(0, "pair", pair_name)

    rolling_metrics_df = calculate_rolling_window_metrics(results)
    rolling_metrics_df.insert(0, "pair", pair_name)

    rolling_summary_df = create_rolling_summary(rolling_metrics_df)
    if not rolling_summary_df.empty and "pair" not in rolling_summary_df.columns:
        rolling_summary_df.insert(0, "pair", pair_name)

    strategy_scorecard_df = create_strategy_scorecard(
        full_period_metrics=metrics_df.drop(columns=["pair"]),
        rolling_summary=rolling_summary_df.drop(columns=["pair"])
        if "pair" in rolling_summary_df.columns
        else rolling_summary_df,
    )
    strategy_scorecard_df = create_strategy_verdicts(strategy_scorecard_df)
    strategy_scorecard_df.insert(0, "pair", pair_name)

    holding_segments_df = create_holding_segments(
        result=dual_momentum,
        pair_name=pair_name,
    )
    allocation_audit_df = create_allocation_audit(
        result=dual_momentum,
        pair_name=pair_name,
    )
    cash_reason_summary_df = create_cash_reason_summary(
        result=dual_momentum,
        pair_name=pair_name,
    )
    opportunity_segments_df = create_opportunity_cost_segments(
        result=dual_momentum,
        pair_name=pair_name,
    )
    opportunity_summary_df = create_opportunity_cost_summary(opportunity_segments_df)

    metrics_path = reports_dir / f"dual_momentum_{safe_pair_name}_metrics.csv"
    rolling_path = reports_dir / f"dual_momentum_{safe_pair_name}_rolling_summary.csv"
    scorecard_path = reports_dir / f"dual_momentum_{safe_pair_name}_scorecard.csv"
    scorecard_md_path = reports_dir / f"dual_momentum_{safe_pair_name}_scorecard.md"
    equity_plot_path = reports_dir / f"dual_momentum_{safe_pair_name}_equity_curves.png"
    drawdown_plot_path = reports_dir / f"dual_momentum_{safe_pair_name}_drawdowns.png"
    holding_segments_path = (
        reports_dir / f"dual_momentum_{safe_pair_name}_holding_segments.csv"
    )
    allocation_audit_path = (
        reports_dir / f"dual_momentum_{safe_pair_name}_allocation_audit.csv"
    )
    cash_reason_summary_path = (
        reports_dir / f"dual_momentum_{safe_pair_name}_cash_reason_summary.csv"
    )
    audit_markdown_path = reports_dir / (
        f"dual_momentum_{safe_pair_name}_allocation_audit.md"
    )
    opportunity_segments_path = (
        reports_dir / f"dual_momentum_{safe_pair_name}_opportunity_cost.csv"
    )
    opportunity_summary_path = (
        reports_dir / f"dual_momentum_{safe_pair_name}_opportunity_summary.csv"
    )
    opportunity_markdown_path = (
        reports_dir / f"dual_momentum_{safe_pair_name}_opportunity_cost.md"
    )

    metrics_df.to_csv(metrics_path, index=False)
    rolling_summary_df.to_csv(rolling_path, index=False)
    strategy_scorecard_df.to_csv(scorecard_path, index=False)
    write_scorecard_markdown(
        strategy_scorecard_df.drop(columns=["pair"]),
        scorecard_md_path,
    )
    holding_segments_df.to_csv(holding_segments_path, index=False)
    allocation_audit_df.to_csv(allocation_audit_path, index=False)
    cash_reason_summary_df.to_csv(cash_reason_summary_path, index=False)
    write_dual_momentum_audit_markdown(
        allocation_audit=allocation_audit_df,
        holding_segments=holding_segments_df,
        cash_summary=cash_reason_summary_df,
        output_path=audit_markdown_path,
    )
    opportunity_segments_df.to_csv(opportunity_segments_path, index=False)
    opportunity_summary_df.to_csv(opportunity_summary_path, index=False)
    write_dual_momentum_opportunity_markdown(
        opportunity_segments=opportunity_segments_df,
        opportunity_summary=opportunity_summary_df,
        output_path=opportunity_markdown_path,
    )
    plot_equity_curves(results, equity_plot_path)
    plot_drawdowns(results, drawdown_plot_path)

    print("\nDual momentum full-period comparison:")
    print(metrics_df.to_string(index=False))

    print("\nDual momentum rolling summary:")
    print(rolling_summary_df.to_string(index=False))

    print("\nDual momentum scorecard:")
    print(
        strategy_scorecard_df[
            [
                "composite_rank",
                "pair",
                "strategy",
                "composite_score",
                "cagr_pct",
                "max_drawdown_pct",
                "sharpe",
                "trade_count",
                "verdict",
            ]
        ].to_string(index=False)
    )

    print("\nDual momentum allocation audit:")
    print(allocation_audit_df.to_string(index=False))

    print("\nDual momentum cash reason summary:")
    print(cash_reason_summary_df.to_string(index=False))

    print("\nDual momentum worst holding segments:")
    print(
        holding_segments_df.sort_values("segment_return_pct")
        .head(10)
        .to_string(index=False)
    )

    print("\nDual momentum opportunity-cost summary:")
    print(opportunity_summary_df.to_string(index=False))

    print("\nDual momentum worst missed-opportunity segments:")
    print(
        opportunity_segments_df.sort_values(
            "missed_return_vs_best_pct_points",
            ascending=False,
        )
        .head(10)
        .to_string(index=False)
    )

    print(f"\nSaved dual momentum metrics to: {metrics_path}")
    print(f"Saved dual momentum rolling summary to: {rolling_path}")
    print(f"Saved dual momentum scorecard to: {scorecard_path}")
    print(f"Saved dual momentum scorecard report to: {scorecard_md_path}")
    print(f"Saved dual momentum equity curve chart to: {equity_plot_path}")
    print(f"Saved dual momentum drawdown chart to: {drawdown_plot_path}")
    print(f"Saved dual momentum holding segments to: {holding_segments_path}")
    print(f"Saved dual momentum allocation audit to: {allocation_audit_path}")
    print(f"Saved dual momentum cash reason summary to: {cash_reason_summary_path}")
    print(f"Saved dual momentum allocation audit report to: {audit_markdown_path}")
    print(f"Saved dual momentum opportunity-cost segments to: {opportunity_segments_path}")
    print(f"Saved dual momentum opportunity-cost summary to: {opportunity_summary_path}")
    print(f"Saved dual momentum opportunity-cost report to: {opportunity_markdown_path}")

    return {
        "metrics": metrics_df,
        "rolling_summary": rolling_summary_df,
        "scorecard": strategy_scorecard_df,
        "holding_segments": holding_segments_df,
        "allocation_audit": allocation_audit_df,
        "cash_reason_summary": cash_reason_summary_df,
        "opportunity_segments": opportunity_segments_df,
        "opportunity_summary": opportunity_summary_df,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    config = load_config(args.config)
    tickers = get_tickers(config)

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    ticker_outputs: dict[str, dict[str, pd.DataFrame]] = {}

    for ticker in tickers:
        ticker_outputs[ticker] = run_backtest_for_ticker(
            ticker=ticker,
            config=config,
            reports_dir=reports_dir,
        )

    if len(ticker_outputs) > 1:
        write_cross_asset_summaries(ticker_outputs, reports_dir)
        run_candidate_portfolio_report(
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )
        relative_momentum_outputs = run_relative_momentum_allocator_report(
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )
        save_relative_momentum_variant_decision_report(reports_dir)
        save_relative_momentum_holdout_validation_report(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )
        save_relative_momentum_validation_conclusion(reports_dir)

        save_relative_momentum_regime_diagnostic(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        overlay_outputs = run_regime_switch_overlay_report(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_regime_switch_overlay_audit(
            overlay_outputs=overlay_outputs,
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_regime_switch_overlay_decision_report(reports_dir)

        save_regime_switch_overlay_holdout_validation_report(
            overlay_outputs=overlay_outputs,
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_regime_switch_overlay_validation_conclusion(reports_dir)

        save_regime_switch_overlay_slippage_sensitivity(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_regime_switch_overlay_cash_sensitivity(
            overlay_outputs=overlay_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_regime_switch_overlay_raw_close_signal_sensitivity(
            relative_momentum_outputs=relative_momentum_outputs,
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_phase3a_robustness_conclusion(reports_dir)

        save_asset_expansion_diagnostic(
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_asset_expansion_conclusion(reports_dir)

        save_eth_quarantine_diagnostic(
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

        save_secondary_data_source_cross_check(
            ticker_outputs=ticker_outputs,
            config=config,
            reports_dir=reports_dir,
        )

    save_final_strategy_decision_report(reports_dir)

    save_finalist_holdout_validation_report(
        ticker_outputs=ticker_outputs,
        config=config,
        reports_dir=reports_dir,
    )

    dual_momentum_pairs = get_dual_momentum_pairs(config)

    for pair in dual_momentum_pairs:
        run_dual_momentum_pair(
            pair=pair,
            config=config,
            reports_dir=reports_dir,
        )
        
    save_final_validation_conclusion(reports_dir)


if __name__ == "__main__":
    main()
