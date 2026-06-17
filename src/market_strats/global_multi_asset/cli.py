from __future__ import annotations

import argparse
from pathlib import Path

from market_strats.global_multi_asset.availability_audit import run_gma0_availability_audit
from market_strats.global_multi_asset.config import load_config
from market_strats.global_multi_asset.gma1a_config import load_gma1a_config
from market_strats.global_multi_asset.gma1a_market_bundle import run_gma1a_market_data_foundation
from market_strats.global_multi_asset.gma1b_config import load_gma1b_config
from market_strats.global_multi_asset.gma1b_macro_cash import (
    run_gma1b_live_diagnostic,
    run_gma1b_macro_cash_foundation,
)


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
    return parser


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
