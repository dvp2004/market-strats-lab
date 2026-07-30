"""Bounded real-source S&P 500 universe qualification orchestration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.universe.calendar import build_monthly_decision_calendar
from market_strats.universe.contracts import (
    CorporateActionEvent,
    SecurityIdentity,
    TickerIdentityInterval,
    UniverseContractError,
    load_source_registry,
    load_universe_contract,
    require_explicit_root,
)
from market_strats.universe.eligibility import evaluate_security_eligibility
from market_strats.universe.hashing import sha256_json
from market_strats.universe.identity import (
    IdentityMap,
    build_security_id,
    normalize_ticker,
    provisional_seed_security_id,
)
from market_strats.universe.membership import (
    active_members,
    build_membership_intervals,
    events_from_membership_snapshots,
)
from market_strats.universe.providers.historical_membership import (
    load_pinned_membership_seed,
    prepare_pinned_repository,
)
from market_strats.universe.providers.sec_edgar import SecEdgarAdapter, SecSnapshot
from market_strats.universe.providers.sp_global import reconcile_bounded_announcements
from market_strats.universe.providers.wikimedia import fetch_pinned_wikimedia_snapshot
from market_strats.universe.providers.yfinance_prices import YFinancePriceAdapter
from market_strats.universe.qualification import build_qualification_summary
from market_strats.universe.reporting import records_to_frame, write_qualification_outputs


def _share_class(ticker: str) -> str | None:
    normalized = normalize_ticker(ticker)
    if "-" not in normalized:
        return None
    return normalized.split("-", maxsplit=1)[1]


def _serializable_snapshot(snapshot: SecSnapshot) -> dict[str, Any]:
    payload = asdict(snapshot)
    payload["raw_path"] = snapshot.raw_path.name
    return payload


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def qualify_free_sp500(
    *,
    contract_path: Path,
    source_registry_path: Path,
    data_root: Path,
    report_root: Path,
    as_of: date,
    sec_user_agent: str,
) -> dict[str, Any]:
    data_root = require_explicit_root(data_root, "data_root")
    report_root = require_explicit_root(report_root, "report_root")
    if data_root == report_root:
        raise UniverseContractError("data_root and report_root must be distinct explicit roots")
    contract = load_universe_contract(contract_path)
    _, sources = load_source_registry(source_registry_path)
    endpoint = date.fromisoformat(str(contract["historical_endpoint"]))
    if as_of != endpoint:
        raise UniverseContractError("as_of must equal the frozen historical_endpoint")
    limits = contract["real_run_limits"]
    raw_root = data_root / "raw"
    source_root = data_root / "sources"
    normalized_root = data_root / "normalized"
    raw_root.mkdir(parents=True, exist_ok=True)
    normalized_root.mkdir(parents=True, exist_ok=True)

    source_failures: list[str] = []
    snapshot_manifest: dict[str, Any] = {
        "contract_id": contract["contract_id"],
        "historical_endpoint": endpoint.isoformat(),
        "sources": {},
    }

    seed_source = sources["hanshof_sp500_membership_seed"]
    seed_repository = source_root / "hanshof_sp500_constituents"
    prepare_pinned_repository(
        repository_url=seed_source.source_url_or_repository,
        destination=seed_repository,
        expected_commit=seed_source.source_revision_or_commit,
    )
    seed = load_pinned_membership_seed(
        repository_root=seed_repository,
        expected_commit=seed_source.source_revision_or_commit,
        expected_hashes={
            "sp_500_historical_components.csv": seed_source.content_sha256,
        },
    )
    snapshot_manifest["sources"][seed_source.source_id] = {
        "source_commit": seed.source_commit,
        "file_hashes": seed.file_hashes,
        "earliest_snapshot_date": seed.snapshots[0][0].isoformat(),
        "latest_snapshot_date": seed.snapshots[-1][0].isoformat(),
        "snapshot_count": len(seed.snapshots),
    }
    if seed.snapshots[-1][0] < endpoint:
        source_failures.append("membership_seed_does_not_reach_historical_endpoint")

    sec_source = sources["sec_edgar_identity"]
    sec_snapshots: list[dict[str, Any]] = []
    sec_rows = []
    try:
        sec_adapter = SecEdgarAdapter(
            user_agent=sec_user_agent,
            raw_root=raw_root / "sec_edgar",
            timeout_seconds=int(limits["request_timeout_seconds"]),
            minimum_request_interval_seconds=float(limits["sec_minimum_request_interval_seconds"]),
        )
        sec_rows, ticker_snapshot = sec_adapter.fetch_company_ticker_mappings()
        sec_snapshots.append(_serializable_snapshot(ticker_snapshot))
    except Exception as error:
        source_failures.append(f"sec_identity_source_unavailable:{type(error).__name__}")
        sec_adapter = None
    sec_by_ticker = {normalize_ticker(row.ticker): row for row in sec_rows}

    identity_map = IdentityMap()
    security_id_by_ticker: dict[str, str] = {}
    unresolved_identity_ids: set[str] = set()
    current_seed_by_ticker = {normalize_ticker(row["symbol"]): row for row in seed.current_rows}
    normalized_first_observed: dict[str, date] = {}
    for ticker, first_observed in seed.first_observed_by_ticker.items():
        normalized = normalize_ticker(ticker)
        normalized_first_observed[normalized] = min(
            first_observed,
            normalized_first_observed.get(normalized, first_observed),
        )
    for normalized, first_observed in sorted(normalized_first_observed.items()):
        sec_mapping = sec_by_ticker.get(normalized)
        seed_current = current_seed_by_ticker.get(normalized)
        if sec_mapping is not None and seed_current is not None:
            security_id = build_security_id(
                namespace="sec_cik_share_class",
                stable_identifier=sec_mapping.cik,
                share_class=_share_class(normalized),
            )
            identity_status = "current_sec_cik_resolved_historical_continuity_unverified"
            cik = sec_mapping.cik
            issuer_name = sec_mapping.name
            exchange = sec_mapping.exchange
        else:
            security_id = provisional_seed_security_id(normalized, first_observed)
            identity_status = "unresolved_historical_seed_identity"
            cik = None
            issuer_name = str(seed_current["security"]) if seed_current is not None else normalized
            exchange = None
            unresolved_identity_ids.add(security_id)
        identity = SecurityIdentity(
            security_id=security_id,
            issuer_name=issuer_name,
            cik=cik,
            share_class=_share_class(normalized),
            identity_status=identity_status,
            source_id=sec_source.source_id if cik else seed_source.source_id,
        )
        identity_map.add_identity(identity)
        identity_map.add_ticker_interval(
            TickerIdentityInterval(
                security_id=security_id,
                ticker=normalized,
                exchange=exchange,
                valid_from=first_observed,
                valid_through=None,
                source_id=identity.source_id,
            )
        )
        security_id_by_ticker[normalized] = security_id

    def resolve_seed_ticker(ticker: str, observed: date) -> str:
        del observed
        return security_id_by_ticker[normalize_ticker(ticker)]

    membership_events = events_from_membership_snapshots(
        ((day, {normalize_ticker(item) for item in tickers}) for day, tickers in seed.snapshots),
        source_id=seed_source.source_id,
        security_id_for_ticker=resolve_seed_ticker,
    )
    membership_intervals, interval_conflicts = build_membership_intervals(membership_events)
    membership_conflicts: list[dict[str, Any]] = list(interval_conflicts)

    wiki_source = sources["wikimedia_sp500_reconciliation"]
    wiki_snapshot = None
    try:
        wiki_snapshot = fetch_pinned_wikimedia_snapshot(
            api_url=wiki_source.source_url_or_repository,
            page_title=str(wiki_source.metadata["page_title"]),
            expected_page_id=int(wiki_source.metadata["page_id"]),
            revision_id=int(wiki_source.source_revision_or_commit),
            expected_revision_sha1=str(wiki_source.metadata["revision_sha1"]),
            raw_root=raw_root / "wikimedia",
            user_agent=sec_user_agent,
            timeout_seconds=int(limits["request_timeout_seconds"]),
        )
        snapshot_manifest["sources"][wiki_source.source_id] = {
            "page_title": wiki_snapshot.page_title,
            "page_id": wiki_snapshot.page_id,
            "revision_id": wiki_snapshot.revision_id,
            "revision_timestamp": wiki_snapshot.revision_timestamp,
            "revision_sha1": wiki_snapshot.revision_sha1,
            "retrieval_timestamp": wiki_snapshot.retrieval_timestamp,
            "content_sha256": wiki_snapshot.content_hash,
        }
        wiki_symbols = {
            normalize_ticker(row.get("symbol", ""))
            for row in wiki_snapshot.current_constituents
            if row.get("symbol")
        }
        seed_symbols = {normalize_ticker(item) for item in seed.snapshots[-1][1]}
        for ticker in sorted(seed_symbols ^ wiki_symbols):
            membership_conflicts.append(
                {
                    "effective_date": endpoint.isoformat(),
                    "ticker": ticker,
                    "conflict_type": (
                        "seed_only_at_latest_available_snapshot"
                        if ticker in seed_symbols
                        else "wikimedia_only_at_frozen_endpoint_revision"
                    ),
                    "primary_source": seed_source.source_id,
                    "secondary_source": wiki_source.source_id,
                }
            )
    except Exception as error:
        source_failures.append(f"wikimedia_reconciliation_unavailable:{type(error).__name__}")

    sp_source = sources["sp_global_bounded_announcements"]
    samples = list(sp_source.metadata["sample_rule"]["announcements"])
    sample_rows = reconcile_bounded_announcements(
        samples=samples,
        raw_root=raw_root / "sp_global",
        user_agent=sec_user_agent,
        timeout_seconds=int(limits["request_timeout_seconds"]),
    )
    seed_event_keys = {
        (row.effective_date.isoformat(), row.action.value, normalize_ticker(row.ticker))
        for row in membership_events
    }
    sample_reconciliation: list[dict[str, Any]] = []
    for row in sample_rows:
        seed_matches = tuple(
            ticker
            for ticker in row.expected_tickers
            if (row.effective_date, "addition", normalize_ticker(ticker)) in seed_event_keys
        )
        passed = row.status == "passed" and seed_matches == row.expected_tickers
        sample_reconciliation.append(
            {
                **asdict(row),
                "seed_matched_tickers": seed_matches,
                "reconciliation_pass": passed,
            }
        )
    snapshot_manifest["sources"][sp_source.source_id] = {
        "sample_rule_id": sp_source.metadata["sample_rule"]["rule_id"],
        "sample_count": len(sample_rows),
        "announcements": [
            {
                "sample_id": row.sample_id,
                "publication_date": row.publication_date,
                "effective_date": row.effective_date,
                "content_sha256": row.content_sha256,
                "status": row.status,
            }
            for row in sample_rows
        ],
    }

    if sec_adapter is not None:
        current_ciks = sorted(
            {row.cik for row in sec_rows if normalize_ticker(row.ticker) in current_seed_by_ticker}
        )
        for cik in current_ciks[: int(limits["maximum_sec_submission_ciks"])]:
            try:
                _, submission_snapshot = sec_adapter.fetch_submission_history(cik)
                sec_snapshots.append(_serializable_snapshot(submission_snapshot))
            except Exception as error:
                source_failures.append(f"sec_submission_history_unavailable:{type(error).__name__}")
    snapshot_manifest["sources"][sec_source.source_id] = {
        "mapping_count": len(sec_rows),
        "snapshots": sec_snapshots,
    }

    price_source = sources["yfinance_daily_prices"]
    price_adapter = YFinancePriceAdapter(
        raw_root=raw_root / "yfinance",
        maximum_attempts=int(limits["maximum_attempts"]),
        retry_delay_seconds=float(limits["retry_delay_seconds"]),
    )
    sample_tickers = ["SPY", *sorted(current_seed_by_ticker)]
    sample_tickers = list(dict.fromkeys(sample_tickers))[: int(limits["maximum_price_tickers"])]
    price_rows_by_security: dict[str, list[dict[str, Any]]] = defaultdict(list)
    price_results: dict[str, Any] = {}
    corporate_actions: list[CorporateActionEvent] = []
    for ticker in sample_tickers:
        first_observed = seed.first_observed_by_ticker.get(ticker, date(1996, 1, 2))
        result = price_adapter.fetch(
            provider_ticker=ticker,
            start=first_observed,
            end=endpoint,
        )
        security_id = security_id_by_ticker.get(ticker)
        price_results[ticker] = {
            "status": result.status,
            "retrieved_at_utc": result.retrieved_at_utc,
            "request_parameters": result.request_parameters,
            "snapshot_sha256": result.snapshot_sha256,
            "row_count": len(result.rows),
            "package_version": result.package_version,
        }
        if security_id is None:
            continue
        for raw in result.rows:
            price_rows_by_security[security_id].append({"security_id": security_id, **raw})
        for index, action in enumerate(result.actions):
            corporate_actions.append(
                CorporateActionEvent(
                    event_id=sha256_json(
                        {
                            "ticker": ticker,
                            "snapshot": result.snapshot_sha256,
                            "index": index,
                            "action": action,
                        }
                    )[:24],
                    security_id=security_id,
                    provider_ticker=ticker,
                    action_type=str(action["action_type"]),
                    effective_date=action["effective_date"],
                    value=action["value"],
                    source_id=price_source.source_id,
                    snapshot_sha256=str(result.snapshot_sha256),
                )
            )
    snapshot_manifest["sources"][price_source.source_id] = {
        "bounded_ticker_limit": int(limits["maximum_price_tickers"]),
        "requested_tickers": sample_tickers,
        "results": price_results,
    }

    price_coverage: list[dict[str, Any]] = []
    for security_id, identity in sorted(identity_map.identities.items()):
        rows = price_rows_by_security.get(security_id, [])
        status = "available" if rows else "not_covered_by_bounded_free_price_audit"
        price_coverage.append(
            {
                "security_id": security_id,
                "cik": identity.cik,
                "status": status,
                "first_session": rows[0]["session_date"] if rows else None,
                "last_session": rows[-1]["session_date"] if rows else None,
                "session_count": len(rows),
                "provider_source_id": price_source.source_id,
            }
        )

    removed_ids = {
        row.security_id for row in membership_intervals if row.effective_through is not None
    }
    delisting_coverage = [
        {
            "security_id": security_id,
            "requires_outcome": True,
            "outcome_status": "unresolved_free_source_delisting_treatment",
            "zero_imputation_used": False,
        }
        for security_id in sorted(removed_ids)
    ]

    calendar = build_monthly_decision_calendar(
        start=date.fromisoformat(str(contract["historical_start"])),
        end=endpoint,
        exchange_calendar=str(contract["exchange_calendar"]),
        same_close_execution=str(contract["same_close_execution"]),
    )
    eligibility_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    qualified_dates: list[date] = []
    conflict_ids = {str(row.get("security_id", "")) for row in membership_conflicts}
    for calendar_row in calendar.to_dict(orient="records"):
        decision_date = calendar_row["decision_date"]
        execution_date = calendar_row["execution_date"]
        members = active_members(membership_intervals, decision_date)
        date_results = []
        for security_id in sorted(members):
            result = evaluate_security_eligibility(
                security_id=security_id,
                decision_date=decision_date,
                execution_date=execution_date,
                price_rows=price_rows_by_security.get(security_id, []),
                identity_resolved=security_id not in unresolved_identity_ids,
                membership_conflict=security_id in conflict_ids,
                delisting_outcome_required=security_id in removed_ids,
                delisting_outcome_resolved=False,
                minimum_history_sessions=int(contract["minimum_price_history_sessions"]),
                liquidity_window_sessions=int(contract["liquidity_window_sessions"]),
                minimum_median_dollar_volume_usd=float(
                    contract["minimum_median_daily_dollar_volume_usd"]
                ),
                minimum_decision_close_usd=float(contract["minimum_decision_close_usd"]),
            )
            date_results.append(result)
            eligibility_rows.append(asdict(result))
            for reason in result.reason_codes:
                exclusions.append(
                    {
                        "decision_date": decision_date,
                        "security_id": security_id,
                        "reason_code": reason,
                    }
                )
        if date_results and all(row.eligible for row in date_results):
            qualified_dates.append(decision_date)

    sample_passed = sum(bool(row["reconciliation_pass"]) for row in sample_reconciliation)
    sample_failed = len(sample_reconciliation) - sample_passed
    blocking_reasons = [
        *source_failures,
        *(
            ["historical_security_identity_continuity_unresolved"]
            if unresolved_identity_ids
            else []
        ),
        *(["membership_sources_do_not_fully_reconcile"] if membership_conflicts else []),
        *(["independent_announcement_sample_failed"] if sample_failed else []),
        *(
            ["bounded_free_price_audit_does_not_cover_all_historical_members"]
            if any(row["status"] != "available" for row in price_coverage)
            else []
        ),
        *(["historical_delisting_outcomes_unresolved"] if delisting_coverage else []),
    ]
    summary = build_qualification_summary(
        earliest_qualified_decision_date=min(qualified_dates) if qualified_dates else None,
        latest_qualified_decision_date=max(qualified_dates) if qualified_dates else None,
        monthly_decision_dates=len(qualified_dates),
        unique_securities=len(identity_map.identities),
        additions_covered=sum(row.action.value == "addition" for row in membership_events),
        removals_covered=sum(row.action.value == "removal" for row in membership_events),
        unresolved_membership_conflicts=len(membership_conflicts),
        unresolved_identity_mappings=len(unresolved_identity_ids),
        price_coverage_failures=sum(row["status"] != "available" for row in price_coverage),
        delisting_treatment_failures=len(delisting_coverage),
        sampled_reconciliations_passed=sample_passed,
        sampled_reconciliations_failed=sample_failed,
        source_coverage_failures=len(source_failures),
        source_terms_failures=0,
        segment_minimums=contract["evaluation_segment_minimum_monthly_decisions"],
        blocking_reasons=blocking_reasons,
    )
    summary["total_scheduled_monthly_decision_dates"] = len(calendar)
    summary["membership_seed_coverage_start"] = seed.snapshots[0][0].isoformat()
    summary["membership_seed_coverage_end"] = seed.snapshots[-1][0].isoformat()
    summary["price_tickers_requested"] = len(sample_tickers)

    source_licence_audit = {
        "total_data_cost_usd": 0,
        "paid_sources_used": False,
        "sources": [
            {
                "source_id": source.source_id,
                "cost_classification": source.cost_classification,
                "licence_or_terms_classification": source.licence_or_terms_classification,
                "permitted_local_use": source.permitted_local_use,
                "redistribution_status": source.redistribution_status,
            }
            for source in sources.values()
        ],
    }
    tables = {
        "security_identity_map.parquet": records_to_frame(list(identity_map.identities.values())),
        "ticker_identity_intervals.parquet": records_to_frame(identity_map.ticker_intervals),
        "membership_events.parquet": records_to_frame(membership_events),
        "membership_intervals.parquet": records_to_frame(membership_intervals),
        "membership_source_conflicts.parquet": (
            records_to_frame(membership_conflicts)
            if membership_conflicts
            else _empty_frame(
                [
                    "effective_date",
                    "ticker",
                    "security_id",
                    "conflict_type",
                    "primary_source",
                    "secondary_source",
                ]
            )
        ),
        "membership_sample_reconciliation.parquet": records_to_frame(sample_reconciliation),
        "corporate_action_events.parquet": records_to_frame(
            corporate_actions,
            columns=[
                "event_id",
                "security_id",
                "provider_ticker",
                "action_type",
                "effective_date",
                "value",
                "source_id",
                "snapshot_sha256",
            ],
        ),
        "price_coverage.parquet": records_to_frame(price_coverage),
        "delisting_coverage.parquet": records_to_frame(delisting_coverage),
        "monthly_decision_calendar.parquet": calendar,
        "decision_date_eligibility.parquet": records_to_frame(eligibility_rows),
        "exclusions_with_reason_codes.parquet": records_to_frame(exclusions),
    }
    output_paths = write_qualification_outputs(
        report_root=report_root,
        source_snapshot_manifest=snapshot_manifest,
        source_licence_audit=source_licence_audit,
        tables=tables,
        qualification_summary=summary,
    )
    return {
        "summary": summary,
        "output_paths": output_paths,
        "source_snapshot_manifest": snapshot_manifest,
        "source_licence_audit": source_licence_audit,
    }
