from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from market_strats.global_multi_asset.availability_audit import run_gma0_availability_audit
from market_strats.global_multi_asset.config import load_config
from market_strats.global_multi_asset.gma1a_config import load_gma1a_config
from market_strats.global_multi_asset.gma1a_market_bundle import run_gma1a_market_data_foundation
from market_strats.global_multi_asset.gma1b_config import load_gma1b_config
from market_strats.global_multi_asset.gma1b_macro_cash import (
    run_gma1b_live_diagnostic,
    run_gma1b_macro_cash_foundation,
)
from market_strats.global_multi_asset.gma2_config import load_gma2_config
from market_strats.global_multi_asset.gma2_replay import run_gma2_replay_foundation
from market_strats.global_multi_asset.gma3a_config import load_gma3a_config
from market_strats.global_multi_asset.gma3a_manual_fills import validate_gma3a_manual_fills
from market_strats.global_multi_asset.gma3a_paper_readiness import (
    TARGET_ASSETS,
    GMA3APaperReadinessResult,
    run_gma3a_paper_readiness,
)
from market_strats.global_multi_asset.gma3a_post_endpoint_refresh import run_gma3a_post_endpoint_refresh
from market_strats.global_multi_asset.gma3a_tournament import run_gma3a_transparent_tournament


def _print_progress(message: str) -> None:
    print(message, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global Multi-Asset Alpha isolated CLI")
    parser.add_argument("--config", required=True, help="Path to GMA config YAML")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit-availability", help="Run GMA-0 availability audit")
    audit.add_argument(
        "--offline-fixtures",
        default=None,
        help="Directory of deterministic CSV fixtures keyed by provider symbol",
    )
    subparsers.add_parser(
        "build-data-foundation",
        help="Run GMA-1A canonical market-data foundation",
    )
    macro = subparsers.add_parser(
        "build-macro-cash-foundation",
        help="Run GMA-1B point-in-time macro/cash foundation",
    )
    macro.add_argument(
        "--live",
        action="store_true",
        help="Explicitly run official FRED/ALFRED live retrieval; default is offline fixture-safe mode",
    )
    macro.add_argument(
        "--live-diagnose",
        action="store_true",
        help="Run a diagnostic-only production-path live request for one configured series",
    )
    macro.add_argument(
        "--live-diagnose-all",
        action="store_true",
        help="Run diagnostic-only production-path live requests for all configured series",
    )
    macro.add_argument(
        "--series-id",
        default=None,
        help="Configured FRED series id for --live-diagnose",
    )
    subparsers.add_parser(
        "build-replay-foundation",
        help="Run GMA-2 point-in-time replay foundation",
    )
    subparsers.add_parser(
        "run-transparent-tournament",
        help="Run GMA-3A transparent strategy tournament and paper portfolio V0",
    )
    subparsers.add_parser(
        "refresh-post-endpoint-market",
        help="Refresh GMA-3A-only post-endpoint market data for paper packet generation",
    )
    subparsers.add_parser(
        "paper-readiness",
        help="Summarize whether current GMA outputs can produce a manual TradingView paper packet",
    )
    subparsers.add_parser(
        "daily-paper-cycle",
        help="Refresh GMA post-endpoint data, regenerate tournament reports, then run paper readiness",
    )
    validate_fills = subparsers.add_parser(
        "validate-manual-fills",
        help="Validate user-entered TradingView paper fills against the active GMA packet",
    )
    validate_fills.add_argument("--fills", required=True, help="Path to user-entered manual fill CSV")
    return parser


def _read_readiness_summary(result: GMA3APaperReadinessResult) -> dict[str, object]:
    summary = pd.read_csv(result.summary_path)
    if summary.empty:
        return {}
    return dict(summary.iloc[0])


def _print_readiness_status(result: GMA3APaperReadinessResult) -> None:
    row = _read_readiness_summary(result)
    manual_entry_sheet_path = result.output_root / "gma3a_manual_tradingview_entry_sheet.md"
    packet_path = result.output_root / "gma3a_tradingview_order_packet.csv"
    print("GMA-3A paper-readiness compact status:")
    for symbol in TARGET_ASSETS:
        latest = row.get(f"{symbol}_latest_finalized_date", "")
        print(f"  {symbol} latest finalized post-endpoint date: {latest}")
    print(f"  GMA decision date: {row.get('decision_date', '')}")
    print(f"  expected execution date: {row.get('expected_execution_date', '')}")
    print(f"  readiness status: {result.readiness_status}")
    print(f"  execution status: {result.execution_status}")
    print(f"  target blocking reason: {result.blocking_reason}")
    print(f"  order packet row count: {result.order_packet_rows}")
    print(f"  manual TradingView entry active: {result.manual_tradingview_entry_active}")
    print(f"  manual TradingView entry sheet: {manual_entry_sheet_path}")
    print(f"  order packet: {packet_path}")
    print(f"  paper-readiness markdown report: {result.markdown_path}")
    print("  safety flags:")
    print(f"    paper_only = {row.get('paper_only', '')}")
    print(f"    live_trading_allowed = {row.get('live_trading_allowed', '')}")
    print(f"    real_money_allowed = {row.get('real_money_allowed', '')}")
    print(f"    broker_api_integration_allowed = {row.get('broker_api_integration_allowed', '')}")
    print(f"    ml_portfolio_influence = {row.get('ml_portfolio_influence', '')}")
    if result.manual_tradingview_entry_active:
        print("manual TradingView paper entry active")
        print("manual paper only")
        print("no live trading")
        print("no broker API")
        print("no automatic submission")
    else:
        print("GMA manual TradingView paper entry is blocked.")
        if result.blocking_reason:
            print(f"Blocker: {result.blocking_reason}")
        print("No instruction to trade is active.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit-availability":
        config = load_config(args.config)
        fixtures = Path(args.offline_fixtures) if args.offline_fixtures else None
        result = run_gma0_availability_audit(config=config, offline_fixtures=fixtures)
        print(f"GMA-0 decision: {result.decision}")
        return 0 if result.decision.startswith("gma0_feasible") else 2
    if args.command == "build-data-foundation":
        config = load_gma1a_config(args.config)
        result = run_gma1a_market_data_foundation(config)
        print(f"GMA-1A decision: {result.decision}")
        if result.warnings:
            for w in result.warnings:
                print(f"  warning: {w}")
        return 0 if result.decision.startswith("gma1a_feasible") else 2
    if args.command == "build-macro-cash-foundation":
        config = load_gma1b_config(args.config)
        diagnostic_mode_count = sum(bool(flag) for flag in [args.live, args.live_diagnose, args.live_diagnose_all])
        if diagnostic_mode_count > 1:
            print("GMA-1B decision: gma1b_blocked_provider_limitations")
            print("  warning: choose only one of --live, --live-diagnose, --live-diagnose-all")
            return 2
        if bool(args.live_diagnose):
            if not args.series_id:
                print("GMA-1B decision: gma1b_live_diagnostic_failed")
                print("  warning: --series-id is required with --live-diagnose")
                return 2
            result = run_gma1b_live_diagnostic(
                config,
                series_id=args.series_id,
                progress_callback=_print_progress,
            )
            print(f"GMA-1B decision: {result.decision}")
            if result.warnings:
                for w in result.warnings:
                    print(f"  warning: {w}")
            return 0 if result.decision.endswith("passed_ineligible_for_canonical_selection") else 2
        if bool(args.live_diagnose_all):
            result = run_gma1b_live_diagnostic(
                config,
                all_series=True,
                progress_callback=_print_progress,
            )
            print(f"GMA-1B decision: {result.decision}")
            if result.warnings:
                for w in result.warnings:
                    print(f"  warning: {w}")
            return 0 if result.decision.endswith("passed_ineligible_for_canonical_selection") else 2
        try:
            result = run_gma1b_macro_cash_foundation(config, live=bool(args.live))
        except RuntimeError as exc:
            print("GMA-1B decision: gma1b_blocked_provider_limitations")
            print(f"  warning: {exc}")
            return 2
        print(f"GMA-1B decision: {result.decision}")
        if result.warnings:
            for w in result.warnings:
                print(f"  warning: {w}")
        if bool(args.live):
            return 0 if result.decision.startswith("gma1b_feasible") else 2
        return 0 if result.decision.startswith("gma1b_feasible") or result.decision == "gma1b_live_data_incomplete" else 2
    if args.command == "build-replay-foundation":
        config = load_gma2_config(args.config)
        result = run_gma2_replay_foundation(config)
        print(f"GMA-2 decision: {result.decision}")
        if result.replay_hash:
            print(f"GMA-2 replay hash: {result.replay_hash}")
        if result.warnings:
            for w in result.warnings:
                print(f"  warning: {w}")
        return 0 if result.decision.startswith("gma2_feasible") else 2
    if args.command == "run-transparent-tournament":
        config = load_gma3a_config(args.config)
        result = run_gma3a_transparent_tournament(config)
        print(f"GMA-3A decision: {result.decision}")
        print(f"GMA-3A order packet rows: {result.order_packet_rows}")
        if result.warnings:
            for w in result.warnings:
                print(f"  warning: {w}")
        return 0 if not result.decision.startswith("gma3a_blocked") else 2
    if args.command == "refresh-post-endpoint-market":
        config = load_gma3a_config(args.config)
        result = run_gma3a_post_endpoint_refresh(config)
        print(f"GMA-3A post-endpoint refresh decision: {result.decision}")
        print(f"GMA-3A refreshed symbols: {','.join(result.refreshed_symbols)}")
        if result.warnings:
            for w in result.warnings:
                print(f"  warning: {w}")
        return 0 if result.decision == "gma3a_post_endpoint_refresh_completed" else 2
    if args.command == "paper-readiness":
        config = load_gma3a_config(args.config)
        result = run_gma3a_paper_readiness(config)
        _print_readiness_status(result)
        return 0
    if args.command == "daily-paper-cycle":
        config = load_gma3a_config(args.config)
        print("GMA daily paper cycle: refresh-post-endpoint-market")
        refresh_result = run_gma3a_post_endpoint_refresh(config)
        print(f"  refresh decision: {refresh_result.decision}")
        print(f"  refreshed symbols: {','.join(refresh_result.refreshed_symbols)}")
        if refresh_result.warnings:
            for warning in refresh_result.warnings:
                print(f"  refresh warning: {warning}")
        print("GMA daily paper cycle: run-transparent-tournament")
        tournament_result = run_gma3a_transparent_tournament(config)
        print(f"  tournament decision: {tournament_result.decision}")
        print(f"  tournament order packet rows: {tournament_result.order_packet_rows}")
        if tournament_result.warnings:
            for warning in tournament_result.warnings:
                print(f"  tournament warning: {warning}")
        print("GMA daily paper cycle: paper-readiness")
        readiness_result = run_gma3a_paper_readiness(config)
        _print_readiness_status(readiness_result)
        return 0
    if args.command == "validate-manual-fills":
        config = load_gma3a_config(args.config)
        result = validate_gma3a_manual_fills(config, Path(args.fills))
        print(f"GMA manual fill validation status: {'valid' if result.session_valid else 'blocked'}")
        print(f"GMA manual fill accepted rows: {result.accepted_rows}")
        print(f"GMA manual fill rejected rows: {result.rejected_rows}")
        if result.blocking_reason:
            print(f"GMA manual fill blocker: {result.blocking_reason}")
        print(f"GMA manual fill summary: {result.summary_path}")
        print(f"GMA manual fill row validation: {result.row_validation_path}")
        print(f"GMA manual fill reconciliation: {result.reconciliation_path}")
        print("manual paper only")
        print("no live trading")
        print("no broker API")
        print("no automatic submission")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
