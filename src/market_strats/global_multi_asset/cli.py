from __future__ import annotations

import argparse
from pathlib import Path

from market_strats.global_multi_asset.availability_audit import run_gma0_availability_audit
from market_strats.global_multi_asset.config import load_config
from market_strats.global_multi_asset.gma1a_config import load_gma1a_config
from market_strats.global_multi_asset.gma1a_market_bundle import run_gma1a_market_data_foundation


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
