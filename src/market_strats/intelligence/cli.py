"""Command-line entry points for Market Intelligence Lab."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from pathlib import Path

from market_strats.intelligence.data.adapter_yfinance import YFinanceEodAdapter
from market_strats.intelligence.data.pipeline import load_source_config, refresh_mi1_market_data
from market_strats.intelligence.mi2.technical_baseline import run_mi2_technical_baseline
from market_strats.intelligence.mi3.macro_vintage_forecast import run_mi3_macro_vintage_forecast
from market_strats.intelligence.mi4.tree_technical_comparator import (
    run_mi4_tree_technical_comparator,
)
from market_strats.intelligence.mi5.fomc_event_text import run_mi5_fomc_event_text_foundation
from market_strats.intelligence.mi6.bls_release_qualification import (
    run_mi6_bls_release_qualification,
)
from market_strats.intelligence.mi7.sec_edgar_8k_qualification import (
    run_mi7_sec_edgar_8k_acceptance_qualification,
)
from market_strats.intelligence.mi8.outcome_maturity import run_outcome_maturity
from market_strats.intelligence.mi8.shadow_record import run_shadow_record
from market_strats.intelligence.quality.validation import DataQualityError


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-strats-intelligence")
    subparsers = parser.add_subparsers(dest="command")

    refresh = subparsers.add_parser(
        "refresh-mi1-market-data",
        help="Refresh research-only MI-1 daily ETF EOD market data.",
    )
    refresh.add_argument("--universe-config", type=Path, required=True)
    refresh.add_argument("--source-config", type=Path, required=True)
    refresh.add_argument("--data-root", type=Path, required=True)
    refresh.add_argument("--report-root", type=Path, required=True)
    refresh.add_argument("--start", type=_parse_date, required=True)
    refresh.add_argument(
        "--end",
        type=_parse_date,
        default=None,
        help="Optional inclusive end date. Omit to let the source adapter request latest data.",
    )
    refresh.add_argument(
        "--mi2-registry-config",
        type=Path,
        default=Path("configs/intelligence/mi2_research_registry.yaml"),
    )
    mi2 = subparsers.add_parser(
        "run-mi2-technical-baseline",
        help="Run the research-only MI-2 technical baseline from local MI-1 outputs.",
    )
    mi2.add_argument("--mi1-data-root", type=Path, required=True)
    mi2.add_argument("--mi2-data-root", type=Path, required=True)
    mi2.add_argument("--report-root", type=Path, required=True)
    mi2.add_argument(
        "--mi2-registry-config",
        type=Path,
        default=Path("configs/intelligence/mi2_research_registry.yaml"),
    )
    mi3 = subparsers.add_parser(
        "run-mi3-macro-vintage-forecast",
        help="Run the research-only MI-3 vintage-aware macro forecast comparison.",
    )
    mi3.add_argument("--mi1-data-root", type=Path, required=True)
    mi3.add_argument("--mi2-data-root", type=Path, required=True)
    mi3.add_argument("--mi3-data-root", type=Path, required=True)
    mi3.add_argument("--report-root", type=Path, required=True)
    mi3.add_argument(
        "--macro-config",
        type=Path,
        default=Path("configs/intelligence/macro_series_mi3.yaml"),
    )
    mi3.add_argument(
        "--mi2-registry-config",
        type=Path,
        default=Path("configs/intelligence/mi2_research_registry.yaml"),
    )
    mi4 = subparsers.add_parser(
        "run-mi4-tree-technical-comparator",
        help="Run the research-only MI-4 fixed tree technical comparator.",
    )
    mi4.add_argument("--mi2-data-root", type=Path, required=True)
    mi4.add_argument("--mi4-data-root", type=Path, required=True)
    mi4.add_argument("--report-root", type=Path, required=True)
    mi4.add_argument(
        "--mi2-registry-config",
        type=Path,
        default=Path("configs/intelligence/mi2_research_registry.yaml"),
    )
    mi4.add_argument(
        "--universe-config",
        type=Path,
        default=Path("configs/intelligence/universe_mi1.yaml"),
    )
    mi5 = subparsers.add_parser(
        "run-mi5-fomc-event-text-foundation",
        help="Run the research-only MI-5 FOMC event/text foundation.",
    )
    mi5.add_argument("--mi1-data-root", type=Path, required=True)
    mi5.add_argument("--mi5-data-root", type=Path, required=True)
    mi5.add_argument("--report-root", type=Path, required=True)
    mi5.add_argument(
        "--event-source-config",
        type=Path,
        default=Path("configs/intelligence/event_source_mi5.yaml"),
    )
    mi5.add_argument(
        "--universe-config",
        type=Path,
        default=Path("configs/intelligence/universe_mi1.yaml"),
    )
    mi6 = subparsers.add_parser(
        "run-mi6-bls-release-qualification",
        help="Run the research-only MI-6 BLS release source qualification.",
    )
    mi6.add_argument("--mi6-data-root", type=Path, required=True)
    mi6.add_argument("--report-root", type=Path, required=True)
    mi6.add_argument(
        "--event-source-config",
        type=Path,
        default=Path("configs/intelligence/event_source_mi6.yaml"),
    )
    mi7 = subparsers.add_parser(
        "run-mi7-sec-edgar-8k-acceptance-qualification",
        help="Run the research-only MI-7 SEC EDGAR 8-K acceptance source qualification.",
    )
    mi7.add_argument("--mi7-data-root", type=Path, required=True)
    mi7.add_argument("--report-root", type=Path, required=True)
    mi7.add_argument(
        "--issuer-panel-config",
        type=Path,
        default=Path("configs/intelligence/sec_issuer_panel_mi7.yaml"),
    )
    mi8 = subparsers.add_parser(
        "run-mi8-shadow-record",
        help="Run MI-8 frozen ETF shadow-prediction protocol.",
    )
    mi8.add_argument(
        "--mode", type=str, required=True, choices=["historical-replay", "prospective-shadow"]
    )
    mi8.add_argument("--start-date", type=str, default="auto")
    mi8.add_argument("--end-date", type=str, default="auto")
    mi8.add_argument("--mi1-data-root", type=Path, required=True)
    mi8.add_argument("--mi8-data-root", type=Path, required=True)
    mi8.add_argument("--report-root", type=Path, required=True)

    mi8_mature = subparsers.add_parser(
        "mature-mi8-shadow-outcomes",
        help="Process outcome maturity for existing MI-8 prediction batches.",
    )
    mi8_mature.add_argument("--mi1-data-root", type=Path, required=True)
    mi8_mature.add_argument("--mi8-data-root", type=Path, required=True)
    mi8_mature.add_argument("--report-root", type=Path, required=True)
    mi8_mature.add_argument("--as-of-timestamp", type=str, default=None)
    return parser


def format_data_quality_error(error: DataQualityError, raw_root: Path) -> str:
    event_counts = Counter(event.event_type for event in error.events)
    lines = [
        "MI-1 refresh failed closed during data-quality validation.",
        "validation_event_counts:",
    ]
    for event_type, count in sorted(event_counts.items()):
        lines.append(f"  {event_type}: {count}")
    lines.append("validation_examples:")
    for event in error.events[:10]:
        session = "" if event.session_date is None else event.session_date.isoformat()
        instrument = event.instrument_id or ""
        lines.append(
            f"  {event.severity} {event.event_type} "
            f"instrument_id={instrument} session_date={session} message={event.message}"
        )
    lines.append(f"local_raw_snapshot_path: {raw_root}")
    lines.append("Raw provider payloads are local-only and are not printed by this command.")
    return "\n".join(lines)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "run-mi2-technical-baseline":
        result = run_mi2_technical_baseline(
            mi1_data_root=args.mi1_data_root,
            mi2_data_root=args.mi2_data_root,
            report_root=args.report_root,
            registry_path=args.mi2_registry_config,
        )
        print("mi1_provenance:")
        for name, value in result.mi1_provenance.items():
            print(f"  {name}: {value}")
        print(f"derived_research_start_date: {result.research_start_date}")
        print(
            "walk_forward_validation: "
            f"{result.validation_start_date} through {result.validation_end_date}"
        )
        print(f"untouched_holdout: {result.holdout_start_date} through {result.holdout_end_date}")
        print(f"feature_row_count: {result.feature_row_count}")
        print(f"target_row_count: {result.target_row_count}")
        print(f"strategy_count: {result.strategy_count}")
        print(f"model_count: {result.model_count}")
        print("output_paths:")
        for name, path in result.output_paths.items():
            print(f"  {name}: {path}")
        print("scoreboard_summary:")
        for row in result.scoreboard_summary:
            print(
                "  "
                f"{row['evaluation_layer']} | {row['strategy_model_name']} | "
                f"{row['evaluation_segment']} | pass={row['promotion_criteria_pass']}"
            )
        return

    if args.command == "run-mi3-macro-vintage-forecast":
        result = run_mi3_macro_vintage_forecast(
            mi1_data_root=args.mi1_data_root,
            mi2_data_root=args.mi2_data_root,
            mi3_data_root=args.mi3_data_root,
            report_root=args.report_root,
            macro_config_path=args.macro_config,
            registry_path=args.mi2_registry_config,
        )
        print("source_provenance:")
        for name, value in result.source_provenance.items():
            print(f"  {name}: {value}")
        print(f"macro_series_count: {result.macro_series_count}")
        print(f"macro_availability_evidence_level: {result.macro_availability_evidence_level}")
        print("vintage_capabilities:")
        for row in result.vintage_capabilities:
            print(
                "  "
                f"{row['series_id']} | "
                f"vintage_start_date={row['vintage_start_date']} | "
                f"vintage_end_date={row['vintage_end_date']} | "
                f"requested_effective_realtime_start="
                f"{row['requested_effective_realtime_start']} | "
                f"requested_effective_realtime_end={row['requested_effective_realtime_end']}"
            )
        print(f"macro_eligible_research_start_date: {result.macro_eligible_start_date}")
        print(
            "walk_forward_validation: "
            f"{result.validation_start_date} through {result.validation_end_date}"
        )
        print(f"untouched_holdout: {result.holdout_start_date} through {result.holdout_end_date}")
        print("row_counts:")
        for name, count in result.row_counts.items():
            print(f"  {name}: {count}")
        print(f"model_count: {result.model_count}")
        print("output_paths:")
        for name, path in result.output_paths.items():
            print(f"  {name}: {path}")
        print("forecast_scoreboard_summary:")
        for row in result.scoreboard_summary:
            print(
                "  "
                f"{row['model_name']} | {row['segment']} | mae={row['mae']} | "
                f"rank_corr={row['rank_correlation']} | {row['promotion_status']}"
            )
        return

    if args.command == "run-mi4-tree-technical-comparator":
        result = run_mi4_tree_technical_comparator(
            mi2_data_root=args.mi2_data_root,
            mi4_data_root=args.mi4_data_root,
            report_root=args.report_root,
            registry_path=args.mi2_registry_config,
            universe_config_path=args.universe_config,
        )
        print("mi2_input_provenance:")
        for name, value in result.mi2_input_provenance.items():
            print(f"  {name}: {value}")
        print(f"research_start_date: {result.research_start_date}")
        print(
            "walk_forward_validation: "
            f"{result.validation_start_date} through {result.validation_end_date}"
        )
        print(f"untouched_holdout: {result.holdout_start_date} through {result.holdout_end_date}")
        print("fixed_random_forest_constants:")
        for name, value in result.fixed_random_forest_constants.items():
            print(f"  {name}: {value}")
        print(f"comparison_row_set_sha256: {result.comparison_row_set_sha256}")
        print("prediction_counts:")
        for name, count in result.prediction_counts.items():
            print(f"  {name}: {count}")
        print("output_paths:")
        for name, path in result.output_paths.items():
            print(f"  {name}: {path}")
        print("forecast_scoreboard_summary:")
        for row in result.scoreboard_summary:
            print(
                "  "
                f"{row['model_name']} | {row['segment']} | mae={row['mae']} | "
                f"rank_corr={row['rank_correlation']} | {row['promotion_status']}"
            )
        return

    if args.command == "run-mi5-fomc-event-text-foundation":
        result = run_mi5_fomc_event_text_foundation(
            mi1_data_root=args.mi1_data_root,
            mi5_data_root=args.mi5_data_root,
            report_root=args.report_root,
            config_path=args.event_source_config,
            universe_config_path=args.universe_config,
        )
        print("mi1_input_provenance:")
        for name, value in result.mi1_input_provenance.items():
            print(f"  {name}: {value}")
        print(f"archive_source_id: {result.archive_source_id}")
        print(
            "discovered_coverage: "
            f"{result.discovered_coverage_start} through {result.discovered_coverage_end}"
        )
        print(f"statement_count: {result.statement_count}")
        print(f"resolved_publication_date_count: {result.resolved_publication_date_count}")
        print(f"excluded_event_count: {result.excluded_event_count}")
        print(f"availability_evidence_level: {result.availability_evidence_level}")
        print(f"lexical_descriptor_row_count: {result.lexical_descriptor_row_count}")
        print(f"usable_statement_count: {result.usable_statement_count}")
        print(
            f"standalone_predictive_model_eligible: {result.standalone_predictive_model_eligible}"
        )
        print(f"event_window_row_count: {result.event_window_row_count}")
        print("output_paths:")
        for name, path in result.output_paths.items():
            print(f"  {name}: {path}")
        return

    if args.command == "run-mi6-bls-release-qualification":
        result = run_mi6_bls_release_qualification(
            mi6_data_root=args.mi6_data_root,
            report_root=args.report_root,
            config_path=args.event_source_config,
        )
        print(f"source_id: {result.source_id}")
        print(f"source_access_status: {result.source_access_status}")
        if result.source_access_diagnostics:
            print("source_access_diagnostics:")
            for name, value in result.source_access_diagnostics.items():
                print(f"  {name}: {value}")
        print("release_type_counts:")
        for name, count in result.release_type_counts.items():
            print(f"  {name}: {count}")
        print(f"usable_timestamped_event_count: {result.usable_timestamped_event_count}")
        print(f"earliest_usable_timestamp: {result.earliest_usable_timestamp}")
        print(f"latest_usable_timestamp: {result.latest_usable_timestamp}")
        print(
            f"qualified_for_later_forecast_research: {result.qualified_for_later_forecast_research}"
        )
        print("qualification_reasons:")
        for reason in result.qualification_reasons:
            print(f"  {reason}")
        print("output_paths:")
        for name, path in result.output_paths.items():
            print(f"  {name}: {path}")
        return

    if args.command == "run-mi7-sec-edgar-8k-acceptance-qualification":
        result = run_mi7_sec_edgar_8k_acceptance_qualification(
            mi7_data_root=args.mi7_data_root,
            report_root=args.report_root,
            config_path=args.issuer_panel_config,
        )
        print(f"source_id: {result.source_id}")
        print(f"source_access_status: {result.source_access_status}")
        print(f"configured_issuer_count: {result.configured_issuer_count}")
        print(f"eligible_8k_event_count: {result.eligible_8k_event_count}")
        print(f"earliest_acceptance_timestamp: {result.earliest_acceptance_timestamp}")
        print(f"latest_acceptance_timestamp: {result.latest_acceptance_timestamp}")
        print(
            "qualified_for_later_next_session_event_research: "
            f"{result.qualified_for_later_next_session_event_research}"
        )
        print("qualification_reasons:")
        for reason in result.qualification_reasons:
            print(f"  {reason}")
        print("output_paths:")
        for name, path in result.output_paths.items():
            print(f"  {name}: {path}")
        return

    if args.command == "run-mi8-shadow-record":
        run_shadow_record(
            mode=args.mode,
            start_date=args.start_date,
            end_date=args.end_date,
            mi1_data_root=args.mi1_data_root,
            mi8_data_root=args.mi8_data_root,
            report_root=args.report_root,
        )
        print("MI-8 shadow recording completed.")
        return

    if args.command == "mature-mi8-shadow-outcomes":
        run_outcome_maturity(
            mi1_data_root=args.mi1_data_root,
            mi8_data_root=args.mi8_data_root,
            report_root=args.report_root,
            as_of_timestamp=args.as_of_timestamp,
        )
        print("MI-8 outcome maturity completed.")
        return

    if args.command != "refresh-mi1-market-data":
        print("Market Intelligence Lab: MI-0 complete; MI-1 market-data command available.")
        return

    source_config = load_source_config(args.source_config)
    if source_config.adapter != "yfinance":
        raise SystemExit(f"Unsupported MI-1 source adapter: {source_config.adapter}")
    adapter = YFinanceEodAdapter(
        auto_adjust=source_config.auto_adjust,
        actions=source_config.actions,
    )
    try:
        result = refresh_mi1_market_data(
            universe_config=args.universe_config,
            source_config_path=args.source_config,
            mi2_registry_config=args.mi2_registry_config,
            data_root=args.data_root,
            report_root=args.report_root,
            start=args.start,
            end=args.end,
            adapter=adapter,
        )
    except DataQualityError as error:
        raise SystemExit(format_data_quality_error(error, args.data_root / "raw")) from error

    print(f"run_id: {result.run_id}")
    print(f"source: {result.source_name}")
    print(f"availability_evidence_level: {result.evidence_level}")
    print(f"snapshot_count: {result.snapshot_count}")
    print(f"bar_count: {result.bar_count}")
    print(f"corporate_action_count: {result.corporate_action_count}")
    if result.common_research_start_date is None:
        print(
            "coverage_common_research_start_date: BLOCKED "
            f"({result.common_research_start_blocked_reason})"
        )
    else:
        print(f"coverage_common_research_start_date: {result.common_research_start_date}")
    print(
        "decision_panel_availability: "
        f"{'PASS' if result.decision_panel_availability_pass else 'FAIL'}"
    )
    print("output_paths:")
    for name, path in result.output_paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
