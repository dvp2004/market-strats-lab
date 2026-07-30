"""Installed CLI for point-in-time stock-universe qualification."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from market_strats.universe.contracts import UniverseContractError
from market_strats.universe.pipeline import qualify_free_sp500


def _date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-strats-universe")
    commands = parser.add_subparsers(dest="command", required=True)
    qualify = commands.add_parser(
        "qualify-free-sp500",
        help="Run the bounded zero-cost S&P 500 point-in-time universe qualification.",
    )
    qualify.add_argument("--contract", type=Path, required=True)
    qualify.add_argument("--source-registry", type=Path, required=True)
    qualify.add_argument("--data-root", type=Path, required=True)
    qualify.add_argument("--report-root", type=Path, required=True)
    qualify.add_argument("--as-of", type=_date, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = qualify_free_sp500(
            contract_path=args.contract,
            source_registry_path=args.source_registry,
            data_root=args.data_root,
            report_root=args.report_root,
            as_of=args.as_of,
            sec_user_agent=os.environ.get("SEC_USER_AGENT"),
        )
    except UniverseContractError as error:
        print(f"qualification_incomplete: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    summary = result["summary"]
    print(f"verdict: {summary['verdict']}")
    print(
        f"membership_seed_coverage: {summary['membership_seed_coverage_start']} through "
        f"{summary['membership_seed_coverage_end']}"
    )
    print(f"unique_securities: {summary['unique_securities']}")
    print(f"qualified_monthly_decision_dates: {summary['monthly_decision_dates']}")
    print("blocking_reasons:")
    for reason in summary["blocking_reasons"]:
        print(f"  {reason}")
    print("output_paths:")
    for name, path in result["output_paths"].items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
