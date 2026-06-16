from __future__ import annotations

import argparse
from pathlib import Path

from market_strats.global_multi_asset.availability_audit import run_gma0_availability_audit
from market_strats.global_multi_asset.config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global Multi-Asset Alpha isolated CLI")
    parser.add_argument("--config", required=True, help="Path to GMA-0 feasibility YAML config")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit-availability", help="Run GMA-0 availability audit")
    audit.add_argument(
        "--offline-fixtures",
        default=None,
        help="Directory of deterministic CSV fixtures keyed by provider symbol",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "audit-availability":
        fixtures = Path(args.offline_fixtures) if args.offline_fixtures else None
        result = run_gma0_availability_audit(config=config, offline_fixtures=fixtures)
        print(f"GMA-0 decision: {result.decision}")
        return 0 if result.decision.startswith("gma0_feasible") else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
