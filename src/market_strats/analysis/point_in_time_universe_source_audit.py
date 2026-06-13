from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE23B_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23b_point_in_time_universe_source_audit"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23b_point_in_time_universe_source_audit_status.csv"
    ),
    "audit_as_of_date": "2026-06-13",
    "required_start_date": "2006-04-28",
    "required_end_date": "2026-05-01",
    "target_universes": ["SP500_POINT_IN_TIME", "NASDAQ100_POINT_IN_TIME"],
    "phase_decision": "phase23b_source_path_identified_acquisition_pending",
    "allow_data_download": False,
    "allow_membership_reconstruction": False,
    "allow_feature_calculation": False,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}

VALID_UNIVERSES = {"SP500_POINT_IN_TIME", "NASDAQ100_POINT_IN_TIME"}
VALID_EVENT_TYPES = {
    "INITIAL_SNAPSHOT",
    "ADD",
    "REMOVE",
    "TICKER_CHANGE",
    "NAME_CHANGE",
    "SHARE_CLASS_CHANGE",
    "MERGER",
    "SPINOFF",
    "DELISTING",
    "BANKRUPTCY",
    "CORRECTION",
}

MEMBERSHIP_EVENT_REQUIRED_COLUMNS = [
    "universe_id",
    "event_id",
    "event_type",
    "announcement_timestamp_utc",
    "effective_date",
    "permanent_security_id",
    "ticker",
    "company_name",
    "source_provider",
    "source_reference",
    "source_retrieved_at_utc",
]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _phase_config(config: dict[str, Any]) -> dict[str, Any]:
    return _deep_merge(
        DEFAULT_PHASE23B_CONFIG,
        config.get("phase23b_point_in_time_universe_source_audit", {}),
    )


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_source_registry() -> pd.DataFrame:
    rows = [
        {
            "source_id": "SPDJI_SPICE",
            "universe": "SP500_POINT_IN_TIME",
            "provider": "S&P Dow Jones Indices",
            "source_name": "SPICE / licensed daily constituent data",
            "source_class": "official_licensed_canonical_candidate",
            "official_provider": True,
            "historical_membership_claimed": "vendor_history_entitlement_to_verify",
            "announcement_effective_dates_available": "entitlement_and_field_audit_required",
            "weights_and_share_counts_available": True,
            "programmatic_access": True,
            "license_or_subscription_required": True,
            "public_free_source": False,
            "permanent_identifier_support": "field_audit_required",
            "intended_use": "preferred_canonical_sp500_membership_source",
            "audit_status": "preferred_pending_commercial_entitlement_and_sample_validation",
            "evidence_reference": (
                "https://www.spglobal.com/spdji/en/documents/methodologies/"
                "methodology-sp-us-indices.pdf"
            ),
        },
        {
            "source_id": "SPDJI_PUBLIC_ANNOUNCEMENTS",
            "universe": "SP500_POINT_IN_TIME",
            "provider": "S&P Dow Jones Indices",
            "source_name": "Public additions/deletions announcements and methodology",
            "source_class": "official_public_event_validation_source",
            "official_provider": True,
            "historical_membership_claimed": False,
            "announcement_effective_dates_available": "recent_events_and_methodology_only",
            "weights_and_share_counts_available": False,
            "programmatic_access": False,
            "license_or_subscription_required": False,
            "public_free_source": True,
            "permanent_identifier_support": "not_sufficient_alone",
            "intended_use": "forward_event_capture_and_secondary_validation",
            "audit_status": "approved_as_validation_only_not_canonical_history",
            "evidence_reference": "https://www.spglobal.com/spdji/",
        },
        {
            "source_id": "NASDAQ_GIW_GIFFD",
            "universe": "NASDAQ100_POINT_IN_TIME",
            "provider": "Nasdaq Global Indexes",
            "source_name": "Global Index Watch / GIFFD licensed index files",
            "source_class": "official_licensed_canonical_candidate",
            "official_provider": True,
            "historical_membership_claimed": "vendor_history_entitlement_to_verify",
            "announcement_effective_dates_available": "entitlement_and_field_audit_required",
            "weights_and_share_counts_available": True,
            "programmatic_access": True,
            "license_or_subscription_required": True,
            "public_free_source": False,
            "permanent_identifier_support": "field_audit_required",
            "intended_use": "preferred_canonical_nasdaq100_membership_source",
            "audit_status": "preferred_pending_commercial_entitlement_and_sample_validation",
            "evidence_reference": "https://indexes.nasdaqomx.com/Index/Overview/NDX",
        },
        {
            "source_id": "NASDAQ_PUBLIC_METHODOLOGY_EVENTS",
            "universe": "NASDAQ100_POINT_IN_TIME",
            "provider": "Nasdaq Global Indexes",
            "source_name": "Public methodology, reconstitution and corporate-action notices",
            "source_class": "official_public_event_validation_source",
            "official_provider": True,
            "historical_membership_claimed": False,
            "announcement_effective_dates_available": "scheduled_rules_and_public_notices",
            "weights_and_share_counts_available": False,
            "programmatic_access": False,
            "license_or_subscription_required": False,
            "public_free_source": True,
            "permanent_identifier_support": "not_sufficient_alone",
            "intended_use": "forward_event_capture_and_secondary_validation",
            "audit_status": "approved_as_validation_only_not_canonical_history",
            "evidence_reference": "https://indexes.nasdaqomx.com/docs/Methodology_NDX.pdf",
        },
        {
            "source_id": "SEC_TICKER_CIK_MAP",
            "universe": "CROSS_UNIVERSE_IDENTIFIER_SUPPORT",
            "provider": "U.S. Securities and Exchange Commission",
            "source_name": "SEC company ticker to CIK mapping",
            "source_class": "official_public_identifier_enrichment",
            "official_provider": True,
            "historical_membership_claimed": False,
            "announcement_effective_dates_available": "not_applicable",
            "weights_and_share_counts_available": False,
            "programmatic_access": True,
            "license_or_subscription_required": False,
            "public_free_source": True,
            "permanent_identifier_support": "CIK_current_mapping_with_history_limits",
            "intended_use": "identifier_enrichment_not_universe_membership",
            "audit_status": "approved_as_identifier_support_only",
            "evidence_reference": "https://www.sec.gov/files/company_tickers.json",
        },
        {
            "source_id": "USER_SUPPLIED_LICENSED_EXPORT",
            "universe": "BOTH_TARGET_UNIVERSES",
            "provider": "Approved licensed vendor export",
            "source_name": "Locally supplied point-in-time membership event file",
            "source_class": "ingestion_contract_not_a_source",
            "official_provider": False,
            "historical_membership_claimed": "depends_on_upstream_vendor",
            "announcement_effective_dates_available": "required_by_import_contract",
            "weights_and_share_counts_available": "optional",
            "programmatic_access": True,
            "license_or_subscription_required": "depends_on_upstream_vendor",
            "public_free_source": False,
            "permanent_identifier_support": "required_by_import_contract",
            "intended_use": "controlled_local_ingestion_after_license_review",
            "audit_status": "schema_ready_source_not_yet_supplied",
            "evidence_reference": "local_file_contract",
        },
    ]
    return pd.DataFrame(rows)


def build_source_scorecard(source_registry: pd.DataFrame) -> pd.DataFrame:
    frame = source_registry.copy()
    frame["authority_score"] = frame["official_provider"].astype(int) * 3
    frame["history_score"] = frame["historical_membership_claimed"].map(
        {True: 3, False: 0}
    ).fillna(1)
    frame["automation_score"] = frame["programmatic_access"].astype(int) * 2
    frame["timestamp_score"] = frame["announcement_effective_dates_available"].map(
        {
            "entitlement_and_field_audit_required": 1,
            "recent_events_and_methodology_only": 1,
            "scheduled_rules_and_public_notices": 1,
            "required_by_import_contract": 2,
            "not_applicable": 0,
        }
    ).fillna(0)
    frame["identifier_score"] = frame["permanent_identifier_support"].map(
        {
            "field_audit_required": 1,
            "not_sufficient_alone": 0,
            "CIK_current_mapping_with_history_limits": 1,
            "required_by_import_contract": 2,
        }
    ).fillna(0)
    frame["audit_score"] = frame[
        [
            "authority_score",
            "history_score",
            "automation_score",
            "timestamp_score",
            "identifier_score",
        ]
    ].sum(axis=1)
    frame["canonical_ready_now"] = False
    frame["canonical_blocking_reason"] = frame["source_class"].map(
        {
            "official_licensed_canonical_candidate": (
                "commercial entitlement, historical coverage, identifiers, and sample fields "
                "must be verified"
            ),
            "official_public_event_validation_source": (
                "public notices are not a guaranteed complete point-in-time history"
            ),
            "official_public_identifier_enrichment": (
                "identifier mapping does not establish index membership"
            ),
            "ingestion_contract_not_a_source": "upstream licensed data has not been supplied",
        }
    )
    return frame.sort_values(
        ["canonical_ready_now", "audit_score", "source_id"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_membership_event_schema() -> pd.DataFrame:
    rows = [
        ("universe_id", "string", True, "SP500_POINT_IN_TIME or NASDAQ100_POINT_IN_TIME"),
        ("event_id", "string", True, "provider-stable event identifier or deterministic hash"),
        ("event_type", "string", True, "membership or identity event type"),
        (
            "announcement_timestamp_utc",
            "timestamp",
            True,
            "when the event first became public; separate from effective date",
        ),
        ("effective_date", "date", True, "first market date on which membership changes"),
        ("permanent_security_id", "string", True, "stable share-line identity"),
        ("permanent_company_id", "string", False, "stable issuer identity"),
        ("share_class_id", "string", False, "stable share-class identity"),
        ("ticker", "string", True, "ticker valid for the event/effective period"),
        ("company_name", "string", True, "company name supplied by source"),
        ("membership_action", "string", True, "ADD, REMOVE, HOLD, or IDENTITY_ONLY"),
        ("reason", "string", False, "reconstitution, merger, bankruptcy, migration, etc."),
        ("index_weight", "float", False, "official weight when licensed source supplies it"),
        ("source_provider", "string", True, "upstream source/provider"),
        ("source_reference", "string", True, "source record, file, URL, or vendor key"),
        (
            "source_retrieved_at_utc",
            "timestamp",
            True,
            "immutable ingestion/retrieval timestamp",
        ),
        ("source_revision", "string", False, "provider revision or correction identifier"),
        ("license_class", "string", True, "licensed, public-validation, or internal-derived"),
        ("is_canonical", "boolean", True, "true only after source approval and validation"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_membership_interval_schema() -> pd.DataFrame:
    rows = [
        ("universe_id", "string", True),
        ("permanent_security_id", "string", True),
        ("ticker", "string", True),
        ("membership_start_date", "date", True),
        ("membership_end_date", "date", False),
        ("known_from_timestamp_utc", "timestamp", True),
        ("addition_event_id", "string", True),
        ("removal_event_id", "string", False),
        ("source_provider", "string", True),
        ("source_revision", "string", False),
        ("is_canonical", "boolean", True),
    ]
    frame = pd.DataFrame(rows, columns=["column", "dtype", "required"])
    frame["description"] = [
        "target point-in-time universe",
        "stable tradable share-line identity",
        "ticker valid during interval",
        "inclusive membership start date",
        "exclusive membership end date; blank while active",
        "earliest timestamp the interval was knowable",
        "event that opened the interval",
        "event that closed the interval",
        "approved upstream provider",
        "provider correction/version",
        "false for provisional or validation-only records",
    ]
    return frame


def build_reconstruction_rules() -> pd.DataFrame:
    rows = [
        (
            "R1",
            "knowledge_time_before_effective_time",
            "No model may use an addition/removal before announcement_timestamp_utc.",
        ),
        (
            "R2",
            "effective_membership_only",
            (
                "A security enters or exits the tradable universe on effective_date, "
                "not announcement date."
            ),
        ),
        (
            "R3",
            "stable_identity",
            "Ticker changes must not create a new economic security without an identity event.",
        ),
        (
            "R4",
            "share_class_deduplication",
            (
                "Cross-index overlap is deduplicated by permanent share-line identifier, "
                "not ticker text."
            ),
        ),
        (
            "R5",
            "failed_security_retention",
            "Delisted, bankrupt, acquired, and removed securities remain in historical records.",
        ),
        (
            "R6",
            "provider_corrections_versioned",
            "Corrections append a revision; prior raw records remain immutable.",
        ),
        (
            "R7",
            "initial_snapshot_required",
            "Event replay must begin from an approved snapshot on or before required_start_date.",
        ),
        (
            "R8",
            "no_public_archive_completeness_assumption",
            (
                "Public press-release archives are validation feeds unless completeness "
                "is demonstrated."
            ),
        ),
        (
            "R9",
            "canonical_endpoint_pinned",
            "Research reconstruction ends at the configured canonical endpoint.",
        ),
        (
            "R10",
            "raw_and_derived_separation",
            "Raw provider files, normalized events, and derived intervals are stored separately.",
        ),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "rule", "requirement"])


def build_validation_plan() -> pd.DataFrame:
    rows = [
        ("V1", "schema completeness", "all required event columns present and nonblank"),
        ("V2", "timestamp ordering", "announcement timestamp is not after effective date"),
        ("V3", "event uniqueness", "event_id unique within universe and source revision"),
        ("V4", "identity continuity", "ticker/name changes preserve permanent identity"),
        ("V5", "interval integrity", "no overlapping active intervals for a security/universe"),
        (
            "V6",
            "event replay",
            "daily membership reconstructed deterministically from snapshot/events",
        ),
        (
            "V7",
            "constituent counts",
            "counts reconcile to provider rules and documented exceptions",
        ),
        (
            "V8",
            "public notice cross-check",
            "sample additions/removals match official announcements",
        ),
        ("V9", "failed-name retention", "removed/delisted/bankrupt securities remain queryable"),
        ("V10", "endpoint coverage", "coverage spans required start through pinned end date"),
        ("V11", "license provenance", "every canonical row has documented permitted research use"),
        ("V12", "immutable raw archive", "checksums and retrieval timestamps preserved"),
    ]
    return pd.DataFrame(rows, columns=["test_id", "test", "acceptance_rule"])


def build_acquisition_plan(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "action": "Request S&P DJI historical constituent sample and entitlement terms",
            "universe": "SP500_POINT_IN_TIME",
            "required_evidence": (
                "coverage dates; announcement/effective fields; stable IDs; deletions; "
                "corrections; "
                "research redistribution restrictions"
            ),
            "status": "pending",
        },
        {
            "priority": 2,
            "action": "Request Nasdaq GIW/GIFFD historical NDX sample and entitlement terms",
            "universe": "NASDAQ100_POINT_IN_TIME",
            "required_evidence": (
                "coverage dates; components; advance events; stable IDs; corporate actions; "
                "historical corrections"
            ),
            "status": "pending",
        },
        {
            "priority": 3,
            "action": "Load vendor samples through the Phase23B event schema validator",
            "universe": "BOTH_TARGET_UNIVERSES",
            "required_evidence": "zero critical schema and timestamp failures",
            "status": "blocked_by_sample_acquisition",
        },
        {
            "priority": 4,
            "action": "Cross-check event samples against official public announcements",
            "universe": "BOTH_TARGET_UNIVERSES",
            "required_evidence": "sample additions/removals and effective dates reconcile",
            "status": "blocked_by_sample_acquisition",
        },
        {
            "priority": 5,
            "action": "Approve one canonical source path per universe",
            "universe": "BOTH_TARGET_UNIVERSES",
            "required_evidence": (
                f"continuous coverage {phase_config['required_start_date']} through "
                f"{phase_config['required_end_date']} and legal approval"
            ),
            "status": "not_started",
        },
    ]
    return pd.DataFrame(rows)


def build_scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    controls = {
        "data_download_allowed": phase_config["allow_data_download"],
        "membership_reconstruction_allowed": phase_config[
            "allow_membership_reconstruction"
        ],
        "feature_calculation_allowed": phase_config["allow_feature_calculation"],
        "model_training_allowed": phase_config["allow_model_training"],
        "backtest_allowed": phase_config["allow_backtest"],
        "paper_orders_allowed": phase_config["allow_paper_orders"],
        "live_trading_allowed": phase_config["allow_live_trading"],
        "real_money_allowed": phase_config["allow_real_money"],
        "broker_api_integration_allowed": phase_config["allow_broker_api"],
        "promotion_allowed": phase_config["allow_promotion"],
    }
    return pd.DataFrame(
        [
            {
                "control": name,
                "allowed": bool(value),
                "required_state": False,
                "passed": not bool(value),
            }
            for name, value in controls.items()
        ]
    )


def build_empty_membership_event_template() -> pd.DataFrame:
    schema = build_membership_event_schema()
    return pd.DataFrame(columns=schema["column"].tolist())


def validate_membership_event_frame(events: pd.DataFrame) -> pd.DataFrame:
    missing_columns = sorted(set(MEMBERSHIP_EVENT_REQUIRED_COLUMNS) - set(events.columns))
    rows: list[dict[str, Any]] = [
        _gate(
            "required_columns_present",
            not missing_columns,
            "missing=" + ";".join(missing_columns),
        )
    ]
    if missing_columns:
        report = pd.DataFrame(rows)
        report["all_gates_passed"] = False
        return report

    working = events.copy()
    required_nonblank = working[MEMBERSHIP_EVENT_REQUIRED_COLUMNS].fillna("").astype(str)
    nonblank = bool(required_nonblank.apply(lambda column: column.str.strip().ne("")).all().all())
    rows.append(_gate("required_values_nonblank", nonblank, f"rows={len(working)}"))

    universe_valid = bool(working["universe_id"].isin(VALID_UNIVERSES).all())
    rows.append(
        _gate(
            "universe_ids_valid",
            universe_valid,
            ";".join(sorted(set(working["universe_id"].astype(str)))),
        )
    )

    event_types_valid = bool(working["event_type"].isin(VALID_EVENT_TYPES).all())
    rows.append(
        _gate(
            "event_types_valid",
            event_types_valid,
            ";".join(sorted(set(working["event_type"].astype(str)))),
        )
    )

    announcement = pd.to_datetime(
        working["announcement_timestamp_utc"], utc=True, errors="coerce"
    )
    effective = pd.to_datetime(working["effective_date"], utc=True, errors="coerce")
    timestamps_parse = bool(announcement.notna().all() and effective.notna().all())
    rows.append(_gate("timestamps_parse", timestamps_parse, f"rows={len(working)}"))

    ordering_valid = bool((announcement <= effective).all()) if timestamps_parse else False
    rows.append(
        _gate(
            "announcement_not_after_effective_date",
            ordering_valid,
            "point-in-time knowledge ordering",
        )
    )

    unique_events = not bool(working.duplicated(["universe_id", "event_id"]).any())
    rows.append(_gate("event_ids_unique_within_universe", unique_events, f"rows={len(working)}"))

    canonical_safe = True
    if "is_canonical" in working.columns and bool(working["is_canonical"].fillna(False).any()):
        canonical_rows = working.loc[working["is_canonical"].fillna(False).astype(bool)]
        if "license_class" not in canonical_rows.columns:
            canonical_safe = False
        else:
            canonical_safe = bool(
                canonical_rows["license_class"].astype(str).eq("licensed").all()
            )
    rows.append(
        _gate(
            "canonical_rows_require_licensed_provenance",
            canonical_safe,
            "canonical rows must be licensed",
        )
    )

    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def build_gate_report(
    *,
    phase_config: dict[str, Any],
    source_registry: pd.DataFrame,
    source_scorecard: pd.DataFrame,
    event_schema: pd.DataFrame,
    interval_schema: pd.DataFrame,
    reconstruction_rules: pd.DataFrame,
    validation_plan: pd.DataFrame,
    acquisition_plan: pd.DataFrame,
    scope_boundary: pd.DataFrame,
) -> pd.DataFrame:
    target_universes = set(phase_config["target_universes"])
    official_candidates = set(
        source_registry.loc[
            source_registry["source_class"].eq("official_licensed_canonical_candidate"),
            "universe",
        ]
    )
    gates = [
        _gate("phase_enabled", bool(phase_config["enabled"]), "Phase23B explicitly enabled"),
        _gate(
            "both_target_universes_have_official_candidates",
            target_universes.issubset(official_candidates),
            ";".join(sorted(official_candidates)),
        ),
        _gate(
            "no_unaudited_source_marked_canonical_ready",
            not bool(source_scorecard["canonical_ready_now"].any()),
            "source acquisition and sample validation still pending",
        ),
        _gate(
            "event_schema_has_knowledge_and_effective_time",
            {
                "announcement_timestamp_utc",
                "effective_date",
                "permanent_security_id",
            }.issubset(set(event_schema["column"])),
            f"columns={len(event_schema)}",
        ),
        _gate(
            "interval_schema_defined",
            len(interval_schema) >= 10,
            f"columns={len(interval_schema)}",
        ),
        _gate(
            "reconstruction_rules_complete",
            len(reconstruction_rules) >= 10,
            f"rules={len(reconstruction_rules)}",
        ),
        _gate(
            "validation_plan_complete",
            len(validation_plan) >= 12,
            f"tests={len(validation_plan)}",
        ),
        _gate(
            "acquisition_plan_defined",
            len(acquisition_plan) >= 5,
            f"actions={len(acquisition_plan)}",
        ),
        _gate(
            "research_only_boundary_enforced",
            bool(scope_boundary["passed"].all()),
            f"controls={len(scope_boundary)}",
        ),
    ]
    report = pd.DataFrame(gates)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def build_summary(
    *, phase_config: dict[str, Any], gate_report: pd.DataFrame, source_scorecard: pd.DataFrame
) -> pd.DataFrame:
    execution_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    universe_data_ready = bool(source_scorecard["canonical_ready_now"].any())
    return pd.DataFrame(
        [
            {
                "phase": "Phase 23B",
                "phase23b_decision": (
                    phase_config["phase_decision"]
                    if execution_passed and not universe_data_ready
                    else "phase23b_source_audit_blocked"
                    if not execution_passed
                    else "phase23b_canonical_source_ready"
                ),
                "phase_execution_gates_passed": execution_passed,
                "all_gates_passed": execution_passed,
                "universe_data_ready": universe_data_ready,
                "canonical_sources_ready_count": int(
                    source_scorecard["canonical_ready_now"].sum()
                ),
                "official_canonical_candidates_count": int(
                    source_scorecard["source_class"]
                    .eq("official_licensed_canonical_candidate")
                    .sum()
                ),
                "required_start_date": phase_config["required_start_date"],
                "required_end_date": phase_config["required_end_date"],
                "model_training_allowed": False,
                "backtest_allowed": False,
                "next_phase": (
                    "Phase 23C — fundamental data source and filing-lag audit; "
                    "Phase23B acquisition remains blocking for stock backtests"
                ),
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def build_conclusion(summary: pd.DataFrame) -> pd.DataFrame:
    row = summary.iloc[0]
    return pd.DataFrame(
        [
            {
                "verdict": (
                    "Phase 23B passed as a source audit: official licensed source paths are "
                    "identified for both universes, but no canonical historical membership "
                    "dataset is approved yet."
                    if bool(row["phase_execution_gates_passed"])
                    else "Phase 23B failed: the source audit or safety boundary is incomplete."
                ),
                "universe_data_ready": bool(row["universe_data_ready"]),
                "allowed_next_step": (
                    "request licensed samples and audit fundamentals in parallel"
                ),
                "blocked_next_step": (
                    "individual-stock feature panel, model training, historical stock selection "
                    "backtest, paper orders, live trading, real money, broker API"
                ),
            }
        ]
    )


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    titles = {
        "source_registry": "Source Registry",
        "source_scorecard": "Source Scorecard",
        "membership_event_schema": "Membership Event Schema",
        "membership_interval_schema": "Derived Membership Interval Schema",
        "reconstruction_rules": "Reconstruction Rules",
        "validation_plan": "Validation Plan",
        "acquisition_plan": "Acquisition Plan",
        "scope_boundary": "Phase Boundary",
        "gate_report": "Gate Report",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    lines = [
        "# Phase 23B — Point-in-Time Universe Source Audit",
        "",
        "This phase audits source paths and defines the import/reconstruction contract for "
        "historical S&P 500 and Nasdaq-100 membership. It does not download proprietary data, "
        "reconstruct memberships, calculate stock features, train models, or create orders.",
        "",
    ]
    for key, title in titles.items():
        lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23b_point_in_time_universe_source_audit(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    phase_config = _phase_config(config)
    if not phase_config["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    root_reports = Path(reports_dir)
    configured_output = Path(str(phase_config["output_dir"]))

    if configured_output.is_absolute():
        output_dir = configured_output
    elif configured_output.parts and configured_output.parts[0].lower() == "reports":
        output_dir = root_reports.joinpath(*configured_output.parts[1:])
    else:
        output_dir = root_reports / configured_output

    output_dir.mkdir(parents=True, exist_ok=True)

    source_registry = build_source_registry()
    source_scorecard = build_source_scorecard(source_registry)
    event_schema = build_membership_event_schema()
    interval_schema = build_membership_interval_schema()
    reconstruction_rules = build_reconstruction_rules()
    validation_plan = build_validation_plan()
    acquisition_plan = build_acquisition_plan(phase_config)
    scope_boundary = build_scope_boundary(phase_config)
    gate_report = build_gate_report(
        phase_config=phase_config,
        source_registry=source_registry,
        source_scorecard=source_scorecard,
        event_schema=event_schema,
        interval_schema=interval_schema,
        reconstruction_rules=reconstruction_rules,
        validation_plan=validation_plan,
        acquisition_plan=acquisition_plan,
        scope_boundary=scope_boundary,
    )
    summary = build_summary(
        phase_config=phase_config,
        gate_report=gate_report,
        source_scorecard=source_scorecard,
    )
    conclusion = build_conclusion(summary)

    outputs = {
        "source_registry": source_registry,
        "source_scorecard": source_scorecard,
        "membership_event_schema": event_schema,
        "membership_interval_schema": interval_schema,
        "reconstruction_rules": reconstruction_rules,
        "validation_plan": validation_plan,
        "acquisition_plan": acquisition_plan,
        "scope_boundary": scope_boundary,
        "gate_report": gate_report,
        "summary": summary,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23b_{name}.csv", index=False)

    build_empty_membership_event_template().to_csv(
        output_dir / "phase23b_membership_event_import_template.csv", index=False
    )
    _write_markdown(outputs, output_dir / "phase23b_point_in_time_universe_source_audit.md")

    dashboard_path = Path(str(phase_config["dashboard_status_path"]))
    if not dashboard_path.is_absolute():
        if dashboard_path.parts and dashboard_path.parts[0].lower() == "reports":
            dashboard_path = root_reports.joinpath(*dashboard_path.parts[1:])
        else:
            dashboard_path = root_reports / dashboard_path
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23b_universe_source_audit_status_written"
    dashboard["notes"] = (
        "Source paths identified; licensed historical constituent samples and legal approval "
        "remain required before reconstruction or model training."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23B point-in-time universe source audit reports.")
    return outputs
