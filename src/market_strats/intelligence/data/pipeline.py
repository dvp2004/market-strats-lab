"""MI-1 market-data refresh pipeline."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from market_strats.intelligence.contracts import (
    AvailabilityAuditRow,
    CorporateActionEvent,
    DataQualityEvent,
    InstrumentRegistryEntry,
    MarketEodBar,
    RawSnapshotManifest,
)
from market_strats.intelligence.data.availability import (
    SUPPORTED_EVIDENCE_LEVELS,
    is_decision_panel_eligible,
    session_cutoff_to_utc,
)
from market_strats.intelligence.data.registry import load_instrument_registry, load_yaml
from market_strats.intelligence.data.snapshot import write_raw_snapshot
from market_strats.intelligence.data.source import EodMarketDataSource, SourceInstrumentData
from market_strats.intelligence.quality.coverage import build_coverage_audit
from market_strats.intelligence.quality.validation import DataQualityError, validate_market_eod_bars
from market_strats.intelligence.reporting.reports import (
    write_availability_reports,
    write_coverage_reports,
)

ADJUSTMENT_BASIS = "vendor_adjusted_close_separate_not_point_in_time_truth"


@dataclass(frozen=True)
class MarketDataSourceConfig:
    source_id: str
    source_name: str
    adapter: str
    requires_api_key: bool
    publication_permission: str
    availability_evidence_level: str
    availability_rule_id: str
    session_close_availability_assumption: str
    contractual_assumption_approved: bool
    auto_adjust: bool
    actions: bool


@dataclass(frozen=True)
class Mi2DecisionRules:
    allowed_evidence_levels: set[str]
    contractual_assumption_requires_explicit_approval: bool
    minimum_common_history_sessions: int


@dataclass(frozen=True)
class RefreshResult:
    run_id: str
    source_name: str
    evidence_level: str
    snapshot_count: int
    bar_count: int
    corporate_action_count: int
    common_research_start_date: date | None
    common_research_start_blocked_reason: str
    decision_panel_availability_pass: bool
    output_paths: dict[str, str]


def load_source_config(path: Path) -> MarketDataSourceConfig:
    config = load_yaml(path)
    source = config["source"]
    assumption = source.get("contractual_assumption", {})
    rule = source["availability_rule"]
    yfinance = source.get("yfinance", {})
    evidence_level = str(source["availability_evidence_level"])
    if evidence_level not in SUPPORTED_EVIDENCE_LEVELS:
        raise ValueError(f"Unsupported source evidence level: {evidence_level}")
    return MarketDataSourceConfig(
        source_id=str(source["source_id"]),
        source_name=str(source["source_name"]),
        adapter=str(source["adapter"]),
        requires_api_key=bool(source["requires_api_key"]),
        publication_permission=str(source["publication_permission"]),
        availability_evidence_level=evidence_level,
        availability_rule_id=str(rule["rule_id"]),
        session_close_availability_assumption=str(rule["session_close_availability_assumption"]),
        contractual_assumption_approved=(
            str(assumption.get("status", "")).lower() == "approved"
            and bool(assumption.get("approved_for_mi1_research", False))
        ),
        auto_adjust=bool(yfinance.get("auto_adjust", False)),
        actions=bool(yfinance.get("actions", True)),
    )


def load_mi2_decision_rules(path: Path) -> Mi2DecisionRules:
    config = load_yaml(path)
    decision = config["decision_and_execution"]
    research_start = config["research_start_date"]
    return Mi2DecisionRules(
        allowed_evidence_levels=set(decision["allowed_evidence_levels"]),
        contractual_assumption_requires_explicit_approval=bool(
            decision["contractual_assumption_requires_explicit_approval"]
        ),
        minimum_common_history_sessions=int(research_start["minimum_common_history_sessions"]),
    )


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def _is_missing(value: Any) -> bool:
    return value is None or value != value


def _coerce_float(value: Any) -> float:
    if _is_missing(value):
        return float("nan")
    return float(value)


def _coerce_int(value: Any) -> int:
    if _is_missing(value):
        return -1
    return int(value)


def _event_id(*parts: object) -> str:
    return sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def transform_source_data(
    *,
    run_id: str,
    source_data: SourceInstrumentData,
    instruments_by_source_symbol: dict[str, InstrumentRegistryEntry],
    source_config: MarketDataSourceConfig,
    retrieved_at_utc: datetime,
    snapshot_id: str,
) -> tuple[list[MarketEodBar], list[CorporateActionEvent], list[DataQualityEvent]]:
    bars: list[MarketEodBar] = []
    actions: list[CorporateActionEvent] = []
    events: list[DataQualityEvent] = []

    for row in source_data.bars:
        source_symbol = str(row.get("source_symbol", source_data.instrument.source_symbol)).upper()
        instrument = instruments_by_source_symbol.get(source_symbol)
        if instrument is None:
            events.append(
                DataQualityEvent(
                    run_id=run_id,
                    severity="fatal",
                    event_type="unmapped_source_row",
                    instrument_id=None,
                    session_date=None,
                    message=f"Source symbol cannot map to fixed registry: {source_symbol}",
                    source="source_transform",
                )
            )
            continue
        session_date = _coerce_date(row["session_date"])
        available_at_utc = session_cutoff_to_utc(
            session_date,
            source_config.session_close_availability_assumption,
        )
        bars.append(
            MarketEodBar(
                instrument_id=instrument.instrument_id,
                session_date=session_date,
                open_raw=_coerce_float(row.get("open")),
                high_raw=_coerce_float(row.get("high")),
                low_raw=_coerce_float(row.get("low")),
                close_raw=_coerce_float(row.get("close")),
                volume_raw=_coerce_int(row.get("volume")),
                vendor_adjusted_close=None
                if _is_missing(row.get("adj_close"))
                else _coerce_float(row.get("adj_close")),
                adjustment_basis=ADJUSTMENT_BASIS,
                available_at_utc=available_at_utc,
                availability_evidence_level=source_config.availability_evidence_level,
                availability_rule_id=source_config.availability_rule_id,
                retrieved_at_utc=retrieved_at_utc,
                snapshot_id=snapshot_id,
            )
        )

    action_rows = [("dividend", row) for row in source_data.dividends] + [
        ("split", row) for row in source_data.splits
    ]
    for action_type, row in action_rows:
        source_symbol = str(row.get("source_symbol", source_data.instrument.source_symbol)).upper()
        instrument = instruments_by_source_symbol.get(source_symbol)
        session_date = _coerce_date(row["session_date"])
        if instrument is None:
            events.append(
                DataQualityEvent(
                    run_id=run_id,
                    severity="fatal",
                    event_type="unmapped_source_row",
                    instrument_id=None,
                    session_date=session_date,
                    message=(
                        f"Corporate action source symbol cannot map to registry: {source_symbol}"
                    ),
                    source="source_transform",
                )
            )
            continue
        available_at_utc = session_cutoff_to_utc(
            session_date,
            source_config.session_close_availability_assumption,
        )
        value = _coerce_float(row.get("value"))
        actions.append(
            CorporateActionEvent(
                event_id=_event_id(
                    instrument.instrument_id, session_date, action_type, value, snapshot_id
                ),
                instrument_id=instrument.instrument_id,
                session_date=session_date,
                action_type=action_type,
                value=value,
                source_name=source_data.source_name,
                available_at_utc=available_at_utc,
                availability_evidence_level=source_config.availability_evidence_level,
                availability_rule_id=source_config.availability_rule_id,
                retrieved_at_utc=retrieved_at_utc,
                snapshot_id=snapshot_id,
            )
        )
    return bars, actions, events


def build_availability_audit(
    *,
    bars: list[MarketEodBar],
    source_config: MarketDataSourceConfig,
    mi2_rules: Mi2DecisionRules,
) -> list[AvailabilityAuditRow]:
    rows: list[AvailabilityAuditRow] = []
    approval = (
        source_config.contractual_assumption_approved
        if mi2_rules.contractual_assumption_requires_explicit_approval
        else True
    )
    for bar in bars:
        decision_timestamp_utc = session_cutoff_to_utc(
            bar.session_date,
            source_config.session_close_availability_assumption,
        )
        eligible, failure_reason = is_decision_panel_eligible(
            evidence_level=bar.availability_evidence_level,
            available_at_utc=bar.available_at_utc,
            decision_timestamp_utc=decision_timestamp_utc,
            allowed_evidence_levels=mi2_rules.allowed_evidence_levels,
            contractual_assumption_approved=approval,
        )
        rows.append(
            AvailabilityAuditRow(
                decision_timestamp_utc=decision_timestamp_utc,
                dataset_row_id=f"{bar.instrument_id}|{bar.session_date.isoformat()}",
                available_at_utc=bar.available_at_utc,
                availability_evidence_level=bar.availability_evidence_level,
                eligible=eligible,
                failure_reason=failure_reason,
            )
        )
    return rows


def _table_value(value: Any) -> Any:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True, default=str)
    return value


def _records_frame(records: list[Any], columns: list[str]) -> pd.DataFrame:
    rows = [
        {key: _table_value(value) for key, value in asdict(record).items()} for record in records
    ]
    return pd.DataFrame(rows, columns=columns)


def _write_parquet(path: Path, records: list[Any], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _records_frame(records, columns).to_parquet(path, index=False)


def _manifest_columns() -> list[str]:
    return [
        "snapshot_id",
        "source_name",
        "dataset_name",
        "request_parameters",
        "retrieved_at_utc",
        "content_sha256",
        "parser_version",
        "raw_path",
        "publication_permission",
        "availability_evidence_level",
    ]


def _bar_columns() -> list[str]:
    return [
        "instrument_id",
        "session_date",
        "open_raw",
        "high_raw",
        "low_raw",
        "close_raw",
        "volume_raw",
        "vendor_adjusted_close",
        "adjustment_basis",
        "available_at_utc",
        "availability_evidence_level",
        "availability_rule_id",
        "retrieved_at_utc",
        "snapshot_id",
    ]


def _action_columns() -> list[str]:
    return [
        "event_id",
        "instrument_id",
        "session_date",
        "action_type",
        "value",
        "source_name",
        "available_at_utc",
        "availability_evidence_level",
        "availability_rule_id",
        "retrieved_at_utc",
        "snapshot_id",
    ]


def _coverage_columns() -> list[str]:
    return [
        "run_id",
        "instrument_id",
        "first_observed_session",
        "last_observed_session",
        "eligible_sessions",
        "missing_sessions",
        "coverage_ratio",
        "continuous_history_sessions",
        "start_date_eligible",
        "notes",
    ]


def _availability_columns() -> list[str]:
    return [
        "decision_timestamp_utc",
        "dataset_row_id",
        "available_at_utc",
        "availability_evidence_level",
        "eligible",
        "failure_reason",
    ]


def _quality_columns() -> list[str]:
    return [
        "run_id",
        "severity",
        "event_type",
        "instrument_id",
        "session_date",
        "message",
        "source",
    ]


def refresh_mi1_market_data(
    *,
    universe_config: Path,
    source_config_path: Path,
    mi2_registry_config: Path,
    data_root: Path,
    report_root: Path,
    start: date,
    end: date | None,
    adapter: EodMarketDataSource,
) -> RefreshResult:
    retrieved_at_utc = datetime.now(UTC)
    run_id = f"mi1_{retrieved_at_utc.strftime('%Y%m%dT%H%M%SZ')}"
    source_config = load_source_config(source_config_path)
    mi2_rules = load_mi2_decision_rules(mi2_registry_config)
    instruments = load_instrument_registry(universe_config)
    instruments_by_source_symbol = {
        instrument.source_symbol: instrument for instrument in instruments
    }

    source_batches = adapter.fetch_eod(instruments, start, end)
    manifests: list[RawSnapshotManifest] = []
    bars: list[MarketEodBar] = []
    actions: list[CorporateActionEvent] = []
    quality_events: list[DataQualityEvent] = []

    for source_data in source_batches:
        manifest = write_raw_snapshot(
            source_data=source_data,
            raw_root=data_root / "raw",
            retrieved_at_utc=retrieved_at_utc,
            publication_permission=source_config.publication_permission,
            availability_evidence_level=source_config.availability_evidence_level,
        )
        manifests.append(manifest)
        batch_bars, batch_actions, batch_events = transform_source_data(
            run_id=run_id,
            source_data=source_data,
            instruments_by_source_symbol=instruments_by_source_symbol,
            source_config=source_config,
            retrieved_at_utc=retrieved_at_utc,
            snapshot_id=manifest.snapshot_id,
        )
        bars.extend(batch_bars)
        actions.extend(batch_actions)
        quality_events.extend(batch_events)

    fatal_transform_events = [event for event in quality_events if event.severity == "fatal"]
    if fatal_transform_events:
        raise DataQualityError(quality_events)
    quality_events.extend(validate_market_eod_bars(run_id, bars))

    observed_end = max((bar.session_date for bar in bars), default=start)
    coverage_end = end or observed_end
    coverage_rows, coverage_events, common_start, blocked_reason = build_coverage_audit(
        run_id=run_id,
        instruments=instruments,
        bars=bars,
        start=start,
        end=coverage_end,
        minimum_common_history_sessions=mi2_rules.minimum_common_history_sessions,
    )
    quality_events.extend(coverage_events)

    availability_rows = build_availability_audit(
        bars=bars,
        source_config=source_config,
        mi2_rules=mi2_rules,
    )
    decision_panel_pass = bool(availability_rows) and all(row.eligible for row in availability_rows)

    manifest_path = data_root / "manifests" / "raw_snapshot_manifest.parquet"
    bar_path = data_root / "normalized" / "market_eod_bar.parquet"
    action_path = data_root / "normalized" / "corporate_action_event.parquet"
    coverage_path = data_root / "normalized" / "coverage_audit.parquet"
    availability_path = data_root / "normalized" / "availability_audit.parquet"
    decision_availability_path = (
        data_root / "normalized" / "decision_panel_availability_audit.parquet"
    )
    quality_path = data_root / "normalized" / "data_quality_event.parquet"

    _write_parquet(manifest_path, manifests, _manifest_columns())
    _write_parquet(bar_path, bars, _bar_columns())
    _write_parquet(action_path, actions, _action_columns())
    _write_parquet(coverage_path, coverage_rows, _coverage_columns())
    _write_parquet(availability_path, availability_rows, _availability_columns())
    _write_parquet(decision_availability_path, availability_rows, _availability_columns())
    _write_parquet(quality_path, quality_events, _quality_columns())

    evidence_counts = Counter(bar.availability_evidence_level for bar in bars)
    coverage_md, coverage_json = write_coverage_reports(
        report_root=report_root,
        run_id=run_id,
        rows=coverage_rows,
        common_research_start_date=common_start,
        blocked_reason=blocked_reason,
        evidence_counts=evidence_counts,
    )
    availability_md, availability_json = write_availability_reports(
        report_root=report_root,
        run_id=run_id,
        rows=availability_rows,
    )

    output_paths = {
        "raw_root": str(data_root / "raw"),
        "raw_snapshot_manifest": str(manifest_path),
        "market_eod_bar": str(bar_path),
        "corporate_action_event": str(action_path),
        "coverage_audit": str(coverage_path),
        "availability_audit": str(availability_path),
        "decision_panel_availability_audit": str(decision_availability_path),
        "data_quality_event": str(quality_path),
        "coverage_report_md": str(coverage_md),
        "coverage_report_json": str(coverage_json),
        "availability_report_md": str(availability_md),
        "availability_report_json": str(availability_json),
    }
    return RefreshResult(
        run_id=run_id,
        source_name=source_config.source_name,
        evidence_level=source_config.availability_evidence_level,
        snapshot_count=len(manifests),
        bar_count=len(bars),
        corporate_action_count=len(actions),
        common_research_start_date=common_start,
        common_research_start_blocked_reason=blocked_reason,
        decision_panel_availability_pass=decision_panel_pass,
        output_paths=output_paths,
    )
