from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE23C_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23c_fundamental_data_source_audit"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23c_fundamental_data_source_audit_status.csv"
    ),
    "audit_as_of_date": "2026-06-13",
    "required_start_date": "2006-04-28",
    "standardized_xbrl_start_date": "2009-01-01",
    "required_end_date": "2026-05-01",
    "primary_jurisdiction": "US_SEC_FILERS",
    "phase_decision": "phase23c_sec_edgar_contract_ready_acquisition_pending",
    "conservative_processing_delay_minutes": 5,
    "allow_data_download": False,
    "allow_fundamental_panel_build": False,
    "allow_feature_calculation": False,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}

VALID_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "8-K",
    "8-K/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A",
    "6-K",
    "6-K/A",
}

FUNDAMENTAL_FACT_REQUIRED_COLUMNS = [
    "cik",
    "accession_number",
    "form",
    "filing_date",
    "accepted_timestamp_utc",
    "knowledge_timestamp_utc",
    "report_period_end",
    "taxonomy",
    "concept",
    "unit",
    "value",
    "source_provider",
    "source_reference",
    "source_retrieved_at_utc",
    "source_revision",
    "is_amendment",
    "license_class",
    "is_canonical",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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
        DEFAULT_PHASE23C_CONFIG,
        config.get("phase23c_fundamental_data_source_audit", {}),
    )


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def _resolve_configured_path(
    *, configured_path: str | Path, reports_dir: str | Path
) -> Path:
    """Resolve a configured output path without creating reports/reports.

    Paths beginning with ``reports`` are anchored at the supplied reports root.
    Other relative paths are interpreted underneath that root. The implementation
    uses ``Path.parts`` and is therefore safe on Windows and POSIX systems.
    """

    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


# ---------------------------------------------------------------------------
# Audit registries and contracts
# ---------------------------------------------------------------------------


def build_source_registry() -> pd.DataFrame:
    rows = [
        {
            "source_id": "SEC_SUBMISSIONS_API",
            "provider": "U.S. Securities and Exchange Commission",
            "source_name": "EDGAR submissions API and bulk submissions archive",
            "source_class": "official_public_filing_metadata_canonical_candidate",
            "official_provider": True,
            "programmatic_access": True,
            "historical_filings_available": True,
            "accepted_timestamp_available": True,
            "accession_number_available": True,
            "amended_filings_available": True,
            "standardized_facts_available": False,
            "custom_tags_available": False,
            "bulk_download_available": True,
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "canonical filing metadata, accepted timestamps, form history, "
                "and amendment sequencing"
            ),
            "audit_status": "approved_contract_source_download_not_run_in_phase23c",
            "evidence_reference": (
                "https://www.sec.gov/search-filings/"
                "edgar-application-programming-interfaces"
            ),
        },
        {
            "source_id": "SEC_XBRL_COMPANYFACTS",
            "provider": "U.S. Securities and Exchange Commission",
            "source_name": "EDGAR XBRL Company Facts API and companyfacts bulk archive",
            "source_class": "official_public_standardized_fact_canonical_candidate",
            "official_provider": True,
            "programmatic_access": True,
            "historical_filings_available": True,
            "accepted_timestamp_available": "join_to_accession_metadata",
            "accession_number_available": True,
            "amended_filings_available": True,
            "standardized_facts_available": True,
            "custom_tags_available": False,
            "bulk_download_available": True,
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "efficient standardized US-GAAP/IFRS fact extraction joined to filing metadata"
            ),
            "audit_status": "approved_contract_source_concept_and_context_audit_pending",
            "evidence_reference": (
                "https://www.sec.gov/search-filings/"
                "edgar-application-programming-interfaces"
            ),
        },
        {
            "source_id": "SEC_INLINE_XBRL_FILING_ARCHIVE",
            "provider": "U.S. Securities and Exchange Commission",
            "source_name": "Original filing documents and inline XBRL instance files",
            "source_class": "official_public_as_filed_document_canonical_candidate",
            "official_provider": True,
            "programmatic_access": True,
            "historical_filings_available": True,
            "accepted_timestamp_available": "join_to_submissions_or_index_headers",
            "accession_number_available": True,
            "amended_filings_available": True,
            "standardized_facts_available": True,
            "custom_tags_available": True,
            "bulk_download_available": "daily_and_quarterly_archive_paths",
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "exact as-filed facts, contexts, dimensions, custom tags, and filing-version audit"
            ),
            "audit_status": "approved_contract_source_parser_pilot_pending",
            "evidence_reference": "https://www.sec.gov/Archives/edgar/data/",
        },
        {
            "source_id": "SEC_8K_EARNINGS_RELEASE_EXHIBITS",
            "provider": "U.S. Securities and Exchange Commission",
            "source_name": "8-K/6-K earnings release exhibits",
            "source_class": "official_public_supplemental_event_source",
            "official_provider": True,
            "programmatic_access": True,
            "historical_filings_available": True,
            "accepted_timestamp_available": True,
            "accession_number_available": True,
            "amended_filings_available": True,
            "standardized_facts_available": False,
            "custom_tags_available": False,
            "bulk_download_available": "filing_archive_access",
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "early earnings-event features kept separate from audited periodic filing facts"
            ),
            "audit_status": "supplemental_only_exhibit_parser_and_item_filter_pending",
            "evidence_reference": "https://www.sec.gov/edgar/search/",
        },
        {
            "source_id": "LICENSED_NORMALIZED_FUNDAMENTALS",
            "provider": "Approved commercial fundamentals vendor",
            "source_name": "Point-in-time normalized fundamentals with filing history",
            "source_class": "licensed_enrichment_or_validation_candidate",
            "official_provider": False,
            "programmatic_access": True,
            "historical_filings_available": "vendor_entitlement_to_verify",
            "accepted_timestamp_available": "field_audit_required",
            "accession_number_available": "field_audit_required",
            "amended_filings_available": "vintage_history_required",
            "standardized_facts_available": True,
            "custom_tags_available": "vendor_specific",
            "bulk_download_available": True,
            "license_or_subscription_required": True,
            "public_free_source": False,
            "intended_use": (
                "cross-check, normalized concept mapping, non-US expansion, or licensed fallback"
            ),
            "audit_status": "not_approved_until_vintage_timestamp_and_license_audit",
            "evidence_reference": "commercial_vendor_contract_and_data_dictionary",
        },
        {
            "source_id": "CURRENT_WEBSITE_FUNDAMENTALS",
            "provider": "Unversioned finance website or current snapshot API",
            "source_name": "Current/latest fundamental snapshot",
            "source_class": "prohibited_for_historical_canonical_features",
            "official_provider": False,
            "programmatic_access": "varies",
            "historical_filings_available": False,
            "accepted_timestamp_available": False,
            "accession_number_available": False,
            "amended_filings_available": False,
            "standardized_facts_available": True,
            "custom_tags_available": False,
            "bulk_download_available": "varies",
            "license_or_subscription_required": "varies",
            "public_free_source": "varies",
            "intended_use": "current-data sanity checks only",
            "audit_status": "blocked_for_historical_training_due_to_revision_and_lookahead_risk",
            "evidence_reference": "not_applicable",
        },
    ]
    return pd.DataFrame(rows)


def build_source_scorecard(source_registry: pd.DataFrame) -> pd.DataFrame:
    frame = source_registry.copy()
    frame["authority_score"] = frame["official_provider"].astype(bool).astype(int) * 3
    frame["automation_score"] = frame["programmatic_access"].map(
        {True: 2, False: 0, "varies": 1}
    ).fillna(1)
    frame["timestamp_score"] = frame["accepted_timestamp_available"].map(
        {True: 3, False: 0, "join_to_accession_metadata": 2,
         "join_to_submissions_or_index_headers": 2, "field_audit_required": 1}
    ).fillna(0)
    frame["version_score"] = frame["amended_filings_available"].map(
        {True: 2, False: 0, "vintage_history_required": 1}
    ).fillna(0)
    frame["fact_score"] = frame["standardized_facts_available"].astype(bool).astype(int) * 2
    frame["audit_score"] = frame[
        [
            "authority_score",
            "automation_score",
            "timestamp_score",
            "version_score",
            "fact_score",
        ]
    ].sum(axis=1)
    frame["source_contract_ready"] = frame["source_id"].isin(
        {
            "SEC_SUBMISSIONS_API",
            "SEC_XBRL_COMPANYFACTS",
            "SEC_INLINE_XBRL_FILING_ARCHIVE",
        }
    )
    frame["canonical_data_ready_now"] = False
    frame["canonical_blocking_reason"] = frame["source_id"].map(
        {
            "SEC_SUBMISSIONS_API": (
                "bulk/API acquisition, checksum archive, identifier join, and coverage validation pending"
            ),
            "SEC_XBRL_COMPANYFACTS": (
                "concept/context harmonization and accession-time joins pending"
            ),
            "SEC_INLINE_XBRL_FILING_ARCHIVE": (
                "as-filed parser, dimensions, custom-tag mapping, and amendment replay pending"
            ),
            "SEC_8K_EARNINGS_RELEASE_EXHIBITS": (
                "supplemental event parser and item/exhibit filters pending"
            ),
            "LICENSED_NORMALIZED_FUNDAMENTALS": (
                "license, vintage history, accepted-time fields, and sample validation pending"
            ),
            "CURRENT_WEBSITE_FUNDAMENTALS": (
                "unversioned current snapshots create restatement and lookahead risk"
            ),
        }
    )
    return frame.sort_values(
        ["source_contract_ready", "audit_score", "source_id"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_filing_event_schema() -> pd.DataFrame:
    rows = [
        ("cik", "string", True, "10-digit SEC central index key"),
        ("accession_number", "string", True, "stable SEC filing identifier"),
        ("form", "string", True, "10-K, 10-Q, 8-K, 20-F, 40-F, 6-K, or amendment"),
        ("filing_date", "date", True, "SEC filing date"),
        (
            "accepted_timestamp_utc",
            "timestamp",
            True,
            "EDGAR acceptance/dissemination timestamp used as the primary knowledge clock",
        ),
        (
            "knowledge_timestamp_utc",
            "timestamp",
            True,
            "accepted timestamp plus configured conservative processing delay",
        ),
        ("report_period_end", "date", True, "period of report; never used as availability time"),
        ("fiscal_year", "integer", False, "issuer fiscal year"),
        ("fiscal_period", "string", False, "FY, Q1, Q2, Q3, or issuer-specific period"),
        ("primary_document", "string", False, "filing document filename"),
        ("is_inline_xbrl", "boolean", False, "inline XBRL indicator"),
        ("is_amendment", "boolean", True, "true for /A filing forms"),
        ("amends_accession_number", "string", False, "original filing when determinable"),
        ("source_provider", "string", True, "SEC or approved licensed source"),
        ("source_reference", "string", True, "archive URL or immutable vendor record"),
        ("source_retrieved_at_utc", "timestamp", True, "local acquisition time"),
        ("source_revision", "string", True, "raw-file checksum or vendor vintage identifier"),
        ("license_class", "string", True, "public_official or licensed"),
        ("is_canonical", "boolean", True, "approved for point-in-time feature construction"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_fundamental_fact_schema() -> pd.DataFrame:
    rows = [
        ("cik", "string", True, "issuer identity"),
        ("accession_number", "string", True, "filing version identity"),
        ("form", "string", True, "source filing form"),
        ("filing_date", "date", True, "source filing date"),
        ("accepted_timestamp_utc", "timestamp", True, "filing acceptance timestamp"),
        ("knowledge_timestamp_utc", "timestamp", True, "earliest model availability"),
        ("report_period_end", "date", True, "reported accounting period end"),
        ("start_date", "date", False, "duration fact start"),
        ("end_date", "date", False, "duration/instant fact end"),
        ("taxonomy", "string", True, "us-gaap, ifrs-full, dei, srt, or custom namespace"),
        ("concept", "string", True, "original XBRL tag"),
        ("canonical_concept", "string", False, "approved cross-company mapped concept"),
        ("unit", "string", True, "reported XBRL unit"),
        ("value", "float", True, "as-filed numeric value"),
        ("decimals", "string", False, "XBRL precision/decimals attribute"),
        ("context_id", "string", False, "original XBRL context identity"),
        ("dimensions_json", "string", False, "sorted XBRL dimensions for context audit"),
        ("frame", "string", False, "SEC frame when present; not a unique context key"),
        ("is_amendment", "boolean", True, "whether fact comes from /A filing"),
        ("restatement_sequence", "integer", False, "chronological version number"),
        ("source_provider", "string", True, "SEC or approved licensed provider"),
        ("source_reference", "string", True, "immutable source record"),
        ("source_retrieved_at_utc", "timestamp", True, "local acquisition time"),
        ("source_revision", "string", True, "checksum or vintage"),
        ("license_class", "string", True, "public_official or licensed"),
        ("is_canonical", "boolean", True, "approved point-in-time row"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_filing_availability_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    delay = int(phase_config["conservative_processing_delay_minutes"])
    rows = [
        (
            "A1",
            "accepted_time_is_primary_clock",
            "No filing-derived feature is available before accepted_timestamp_utc.",
        ),
        (
            "A2",
            "processing_delay",
            f"knowledge_timestamp_utc is at least accepted time plus {delay} minutes.",
        ),
        (
            "A3",
            "period_end_is_not_knowledge_time",
            "Fiscal/report period end dates must never be treated as publication dates.",
        ),
        (
            "A4",
            "next_market_decision",
            "After-close or non-trading-day filings first affect the next eligible decision/execution cycle.",
        ),
        (
            "A5",
            "8k_separate_family",
            "8-K/6-K earnings releases remain separate from periodic-statement features.",
        ),
        (
            "A6",
            "facts_join_to_accession",
            "Every fact must join to one accession and inherit that filing's accepted timestamp.",
        ),
        (
            "A7",
            "raw_retrieval_not_knowledge_time",
            "Local retrieval time proves provenance but cannot replace the public filing time.",
        ),
        (
            "A8",
            "late_or_corrected_data",
            "Late vendor corrections become available only from their documented revision timestamp.",
        ),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "rule", "requirement"])


def build_restatement_policy() -> pd.DataFrame:
    rows = [
        (
            "R1",
            "append_never_overwrite",
            "Original and amended filings remain immutable rows keyed by accession/version.",
        ),
        (
            "R2",
            "as_filed_view",
            "Historical features use the latest filing version known at each decision timestamp.",
        ),
        (
            "R3",
            "latest_restated_view_separate",
            "A latest-restated analytical view may exist but is prohibited for historical training.",
        ),
        (
            "R4",
            "amendment_availability",
            "10-K/A, 10-Q/A, 8-K/A and foreign-form amendments apply only from their own accepted time.",
        ),
        (
            "R5",
            "original_not_deleted",
            "An amendment does not erase the originally observed fact or model state.",
        ),
        (
            "R6",
            "concept_context_versioning",
            "Changed tags, contexts, dimensions or units create explicit versioned mappings.",
        ),
        (
            "R7",
            "restatement_impact_audit",
            "Material feature changes between versions are logged and quantified.",
        ),
        (
            "R8",
            "vendor_vintage_required",
            "Commercial normalized data is canonical only when historical vintages are reproducible.",
        ),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "policy", "requirement"])



def build_pre_xbrl_coverage_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "coverage_segment": "pre_standardized_xbrl",
            "start_date": phase_config["required_start_date"],
            "end_date": "2008-12-31",
            "preferred_source_path": (
                "SEC filing HTML/text plus accession metadata, or approved licensed "
                "point-in-time normalized fundamentals"
            ),
            "canonical_ready_now": False,
            "blocking_reason": (
                "standardized XBRL was not yet broadly required; parser/vendor vintage "
                "coverage and filing-time reconciliation are pending"
            ),
            "training_policy": "exclude until a validated point-in-time source is approved",
        },
        {
            "coverage_segment": "standardized_xbrl_era",
            "start_date": phase_config["standardized_xbrl_start_date"],
            "end_date": phase_config["required_end_date"],
            "preferred_source_path": (
                "SEC submissions plus Company Facts and original inline/XBRL filings"
            ),
            "canonical_ready_now": False,
            "blocking_reason": (
                "raw acquisition, accession-time joins, concept/context mapping, and "
                "restatement replay are pending"
            ),
            "training_policy": "exclude until the SEC pilot passes validation",
        },
    ]
    return pd.DataFrame(rows)

def build_feature_concept_registry() -> pd.DataFrame:
    rows = [
        ("revenue", "growth", "Revenues; SalesRevenueNet", "duration", "quarterly_and_ttm"),
        ("gross_profit", "profitability", "GrossProfit", "duration", "quarterly_and_ttm"),
        ("operating_income", "profitability", "OperatingIncomeLoss", "duration", "quarterly_and_ttm"),
        ("net_income", "profitability", "NetIncomeLoss; ProfitLoss", "duration", "quarterly_and_ttm"),
        ("eps_diluted", "profitability", "EarningsPerShareDiluted", "duration", "quarterly"),
        ("operating_cash_flow", "cash_flow", "NetCashProvidedByUsedInOperatingActivities", "duration", "quarterly_and_ttm"),
        ("capital_expenditure", "investment", "PaymentsToAcquirePropertyPlantAndEquipment", "duration", "quarterly_and_ttm"),
        ("free_cash_flow", "cash_flow", "derived: operating_cash_flow-capital_expenditure", "derived", "quarterly_and_ttm"),
        ("research_and_development", "investment", "ResearchAndDevelopmentExpense", "duration", "quarterly_and_ttm"),
        ("selling_general_admin", "efficiency", "SellingGeneralAndAdministrativeExpense", "duration", "quarterly_and_ttm"),
        ("assets", "balance_sheet", "Assets", "instant", "quarter_end"),
        ("current_assets", "liquidity", "AssetsCurrent", "instant", "quarter_end"),
        ("cash_and_equivalents", "liquidity", "CashAndCashEquivalentsAtCarryingValue", "instant", "quarter_end"),
        ("inventory", "working_capital", "InventoryNet", "instant", "quarter_end"),
        ("receivables", "working_capital", "AccountsReceivableNetCurrent", "instant", "quarter_end"),
        ("liabilities", "balance_sheet", "Liabilities", "instant", "quarter_end"),
        ("current_liabilities", "liquidity", "LiabilitiesCurrent", "instant", "quarter_end"),
        ("debt", "leverage", "LongTermDebtAndFinanceLeaseObligationsCurrent+Noncurrent", "derived", "quarter_end"),
        ("stockholders_equity", "balance_sheet", "StockholdersEquity", "instant", "quarter_end"),
        ("shares_diluted", "capital_structure", "WeightedAverageNumberOfDilutedSharesOutstanding", "duration", "quarterly"),
        ("gross_margin", "profitability", "derived: gross_profit/revenue", "derived", "quarterly_and_ttm"),
        ("operating_margin", "profitability", "derived: operating_income/revenue", "derived", "quarterly_and_ttm"),
        ("return_on_assets", "quality", "derived: ttm_net_income/average_assets", "derived", "ttm"),
        ("accruals", "quality", "derived: net_income-operating_cash_flow", "derived", "ttm"),
        ("asset_growth", "investment", "derived: assets/assets_lagged-1", "derived", "annual_or_quarterly"),
    ]
    frame = pd.DataFrame(
        rows,
        columns=[
            "canonical_feature",
            "family",
            "candidate_tags_or_formula",
            "fact_type",
            "initial_frequency",
        ],
    )
    frame["mapping_status"] = "pilot_mapping_required"
    frame["point_in_time_rule"] = (
        "use only accession versions with knowledge_timestamp_utc <= decision_timestamp_utc"
    )
    return frame


def build_context_selection_rules() -> pd.DataFrame:
    rows = [
        ("C1", "accession_bound", "Facts cannot be selected without accession-level provenance."),
        ("C2", "consolidated_preferred", "Prefer consolidated entity-wide contexts over segments unless feature explicitly requires segments."),
        ("C3", "duration_alignment", "Quarterly and TTM features require explicit start/end duration checks."),
        ("C4", "instant_alignment", "Balance-sheet facts must align to the intended report-period instant."),
        ("C5", "unit_consistency", "Concept mappings specify accepted units and reject silent unit conversion."),
        ("C6", "dimension_deduplication", "Dimensions are part of context identity; duplicate-looking facts are not collapsed blindly."),
        ("C7", "fiscal_calendar_aware", "Issuer fiscal calendars are retained; calendar-frame labels are not treated as exact periods."),
        ("C8", "custom_tag_mapping_review", "Custom tags require audited mapping and cannot be auto-merged by label similarity alone."),
        ("C9", "taxonomy_version_recorded", "Taxonomy namespace/version is preserved for every source fact."),
        ("C10", "no_latest_fact_shortcut", "The latest available value today may not be backfilled through prior decision dates."),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "rule", "requirement"])


def build_validation_plan() -> pd.DataFrame:
    rows = [
        ("V1", "required schema", "all required filing/fact columns present and nonblank"),
        ("V2", "accepted-time parse", "accepted and knowledge timestamps parse as UTC"),
        ("V3", "knowledge ordering", "knowledge timestamp is not earlier than accepted timestamp"),
        ("V4", "retrieval ordering", "retrieval timestamp is not earlier than accepted timestamp"),
        ("V5", "period ordering", "report period end is not after filing date"),
        ("V6", "form whitelist", "form belongs to approved periodic/event filing set"),
        ("V7", "amendment consistency", "/A forms agree with is_amendment"),
        ("V8", "accession uniqueness", "fact identity is unique within accession/context/unit"),
        ("V9", "canonical provenance", "canonical facts originate from SEC public-official or approved licensed data"),
        ("V10", "as-filed replay", "historical feature values reproduce accession vintages at decision times"),
        ("V11", "taxonomy drift", "standard and custom tag mappings are versioned and test-covered"),
        ("V12", "restatement replay", "amended values appear only after amendment knowledge time"),
        ("V13", "filing sample reconciliation", "selected facts reconcile to filing HTML/XBRL documents"),
        ("V14", "coverage", "issuer/period coverage is quantified by universe and year"),
        ("V15", "raw immutability", "raw bytes, checksums and retrieval metadata are preserved"),
    ]
    return pd.DataFrame(rows, columns=["test_id", "test", "acceptance_rule"])


def build_acquisition_plan(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "action": (
                "Audit 2006-2008 pre-XBRL coverage using SEC filing HTML/text and an "
                "optional licensed point-in-time vendor sample"
            ),
            "dependency": "none",
            "status": "pending",
        },
        {
            "priority": 3,
            "action": "Archive SEC submissions bulk data with checksums and retrieval metadata",
            "dependency": "none",
            "status": "pending",
        },
        {
            "priority": 3,
            "action": "Archive SEC companyfacts bulk data for a small pilot issuer set",
            "dependency": "approved SEC fair-access client and local raw-data layout",
            "status": "pending",
        },
        {
            "priority": 4,
            "action": "Join facts to accession acceptance timestamps and apply processing delay",
            "dependency": "submissions and companyfacts pilot archives",
            "status": "blocked_by_acquisition",
        },
        {
            "priority": 5,
            "action": "Parse original inline XBRL filings for context/custom-tag reconciliation",
            "dependency": "pilot accession list",
            "status": "blocked_by_acquisition",
        },
        {
            "priority": 6,
            "action": "Replay original and amended filing versions for restatement tests",
            "dependency": "accession-level fact normalization",
            "status": "not_started",
        },
        {
            "priority": 7,
            "action": "Approve initial fundamental concept map and coverage thresholds",
            "dependency": (
                f"pilot coverage across {phase_config['required_start_date']} through "
                f"{phase_config['required_end_date']}"
            ),
            "status": "not_started",
        },
    ]
    return pd.DataFrame(rows)


def build_scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    controls = {
        "data_download_allowed": phase_config["allow_data_download"],
        "fundamental_panel_build_allowed": phase_config["allow_fundamental_panel_build"],
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


def build_empty_filing_event_template() -> pd.DataFrame:
    return pd.DataFrame(columns=build_filing_event_schema()["column"].tolist())


def build_empty_fundamental_fact_template() -> pd.DataFrame:
    return pd.DataFrame(columns=build_fundamental_fact_schema()["column"].tolist())


# ---------------------------------------------------------------------------
# Reusable sample validator
# ---------------------------------------------------------------------------


def validate_fundamental_fact_frame(facts: pd.DataFrame) -> pd.DataFrame:
    missing_columns = sorted(set(FUNDAMENTAL_FACT_REQUIRED_COLUMNS) - set(facts.columns))
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

    working = facts.copy()
    nonblank_columns = [
        column
        for column in FUNDAMENTAL_FACT_REQUIRED_COLUMNS
        if column not in {"value", "is_amendment", "is_canonical"}
    ]
    required_nonblank = working[nonblank_columns].fillna("").astype(str)
    nonblank = bool(
        required_nonblank.apply(lambda column: column.str.strip().ne("")).all().all()
    )
    rows.append(_gate("required_values_nonblank", nonblank, f"rows={len(working)}"))

    forms_valid = bool(working["form"].astype(str).isin(VALID_FORMS).all())
    rows.append(
        _gate(
            "forms_valid",
            forms_valid,
            ";".join(sorted(set(working["form"].astype(str)))),
        )
    )

    filing_date = pd.to_datetime(working["filing_date"], utc=True, errors="coerce")
    accepted = pd.to_datetime(
        working["accepted_timestamp_utc"], utc=True, errors="coerce"
    )
    knowledge = pd.to_datetime(
        working["knowledge_timestamp_utc"], utc=True, errors="coerce"
    )
    report_period = pd.to_datetime(
        working["report_period_end"], utc=True, errors="coerce"
    )
    retrieved = pd.to_datetime(
        working["source_retrieved_at_utc"], utc=True, errors="coerce"
    )
    timestamps_parse = bool(
        filing_date.notna().all()
        and accepted.notna().all()
        and knowledge.notna().all()
        and report_period.notna().all()
        and retrieved.notna().all()
    )
    rows.append(_gate("timestamps_parse", timestamps_parse, f"rows={len(working)}"))

    report_before_filing = (
        bool((report_period <= filing_date).all()) if timestamps_parse else False
    )
    rows.append(
        _gate(
            "report_period_not_after_filing_date",
            report_before_filing,
            "period-end versus filing date",
        )
    )

    accepted_on_or_after_filing_date = (
        bool((accepted.dt.normalize() >= filing_date.dt.normalize()).all())
        if timestamps_parse
        else False
    )
    rows.append(
        _gate(
            "accepted_date_not_before_filing_date",
            accepted_on_or_after_filing_date,
            "accepted timestamp date versus filing date",
        )
    )

    knowledge_ordering = bool((knowledge >= accepted).all()) if timestamps_parse else False
    rows.append(
        _gate(
            "knowledge_not_before_accepted_timestamp",
            knowledge_ordering,
            "point-in-time availability ordering",
        )
    )

    retrieval_ordering = bool((retrieved >= accepted).all()) if timestamps_parse else False
    rows.append(
        _gate(
            "retrieval_not_before_accepted_timestamp",
            retrieval_ordering,
            "provenance ordering",
        )
    )

    amendment_flag = working["is_amendment"].fillna(False).astype(bool)
    amendment_form = working["form"].astype(str).str.endswith("/A")
    amendment_consistent = bool(amendment_flag.eq(amendment_form).all())
    rows.append(
        _gate(
            "amendment_flag_matches_form",
            amendment_consistent,
            "forms ending /A must be amendments and vice versa",
        )
    )

    identity_columns = [
        "cik",
        "accession_number",
        "taxonomy",
        "concept",
        "unit",
        "report_period_end",
    ]
    for optional in ["start_date", "end_date", "context_id", "dimensions_json"]:
        if optional in working.columns:
            identity_columns.append(optional)
    unique_facts = not bool(working.duplicated(identity_columns).any())
    rows.append(
        _gate(
            "fact_identity_unique_within_filing_context",
            unique_facts,
            "identity=" + ";".join(identity_columns),
        )
    )

    canonical_safe = True
    canonical_rows = working.loc[working["is_canonical"].fillna(False).astype(bool)]
    if not canonical_rows.empty:
        providers = canonical_rows["source_provider"].astype(str).str.lower()
        license_class = canonical_rows["license_class"].astype(str).str.lower()
        provider_safe = providers.str.contains("sec").fillna(False) | license_class.eq(
            "licensed"
        )
        license_safe = license_class.isin({"public_official", "licensed"})
        canonical_safe = bool((provider_safe & license_safe).all())
    rows.append(
        _gate(
            "canonical_rows_have_approved_provenance",
            canonical_safe,
            "canonical rows require SEC public-official or licensed provenance",
        )
    )

    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


# ---------------------------------------------------------------------------
# Phase gates and output generation
# ---------------------------------------------------------------------------


def build_gate_report(
    *,
    phase_config: dict[str, Any],
    source_registry: pd.DataFrame,
    source_scorecard: pd.DataFrame,
    filing_event_schema: pd.DataFrame,
    fundamental_fact_schema: pd.DataFrame,
    availability_policy: pd.DataFrame,
    restatement_policy: pd.DataFrame,
    pre_xbrl_coverage_policy: pd.DataFrame,
    feature_concept_registry: pd.DataFrame,
    context_selection_rules: pd.DataFrame,
    validation_plan: pd.DataFrame,
    acquisition_plan: pd.DataFrame,
    scope_boundary: pd.DataFrame,
) -> pd.DataFrame:
    approved_contract_sources = set(
        source_scorecard.loc[source_scorecard["source_contract_ready"], "source_id"]
    )
    gates = [
        _gate("phase_enabled", bool(phase_config["enabled"]), "Phase23C explicitly enabled"),
        _gate(
            "sec_filing_metadata_contract_identified",
            "SEC_SUBMISSIONS_API" in approved_contract_sources,
            ";".join(sorted(approved_contract_sources)),
        ),
        _gate(
            "sec_standardized_fact_contract_identified",
            "SEC_XBRL_COMPANYFACTS" in approved_contract_sources,
            ";".join(sorted(approved_contract_sources)),
        ),
        _gate(
            "as_filed_document_contract_identified",
            "SEC_INLINE_XBRL_FILING_ARCHIVE" in approved_contract_sources,
            ";".join(sorted(approved_contract_sources)),
        ),
        _gate(
            "no_unvalidated_data_marked_ready",
            not bool(source_scorecard["canonical_data_ready_now"].any()),
            "acquisition and pilot validation remain pending",
        ),
        _gate(
            "filing_schema_has_accepted_and_knowledge_time",
            {"accepted_timestamp_utc", "knowledge_timestamp_utc", "accession_number"}.issubset(
                set(filing_event_schema["column"])
            ),
            f"columns={len(filing_event_schema)}",
        ),
        _gate(
            "fact_schema_has_version_and_context_fields",
            {
                "accession_number",
                "taxonomy",
                "concept",
                "unit",
                "source_revision",
                "is_amendment",
            }.issubset(set(fundamental_fact_schema["column"])),
            f"columns={len(fundamental_fact_schema)}",
        ),
        _gate(
            "availability_policy_complete",
            len(availability_policy) >= 8,
            f"rules={len(availability_policy)}",
        ),
        _gate(
            "restatement_policy_complete",
            len(restatement_policy) >= 8,
            f"rules={len(restatement_policy)}",
        ),
        _gate(
            "pre_xbrl_coverage_gap_explicit",
            {"pre_standardized_xbrl", "standardized_xbrl_era"}.issubset(
                set(pre_xbrl_coverage_policy["coverage_segment"])
            ),
            f"segments={len(pre_xbrl_coverage_policy)}",
        ),
        _gate(
            "initial_feature_concept_registry_defined",
            len(feature_concept_registry) >= 20,
            f"features={len(feature_concept_registry)}",
        ),
        _gate(
            "context_selection_rules_complete",
            len(context_selection_rules) >= 10,
            f"rules={len(context_selection_rules)}",
        ),
        _gate(
            "validation_plan_complete",
            len(validation_plan) >= 15,
            f"tests={len(validation_plan)}",
        ),
        _gate(
            "acquisition_plan_defined",
            len(acquisition_plan) >= 6,
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
    *,
    phase_config: dict[str, Any],
    gate_report: pd.DataFrame,
    source_scorecard: pd.DataFrame,
) -> pd.DataFrame:
    execution_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    source_contract_ready = bool(source_scorecard["source_contract_ready"].any())
    data_ready = bool(source_scorecard["canonical_data_ready_now"].any())
    return pd.DataFrame(
        [
            {
                "phase": "Phase 23C",
                "phase23c_decision": (
                    phase_config["phase_decision"]
                    if execution_passed and source_contract_ready and not data_ready
                    else "phase23c_fundamental_source_audit_blocked"
                    if not execution_passed
                    else "phase23c_fundamental_data_ready"
                ),
                "phase_execution_gates_passed": execution_passed,
                "all_gates_passed": execution_passed,
                "fundamental_source_contract_ready": source_contract_ready,
                "fundamental_data_ready": data_ready,
                "source_contracts_ready_count": int(
                    source_scorecard["source_contract_ready"].sum()
                ),
                "canonical_data_sources_ready_count": int(
                    source_scorecard["canonical_data_ready_now"].sum()
                ),
                "required_start_date": phase_config["required_start_date"],
                "standardized_xbrl_start_date": phase_config[
                    "standardized_xbrl_start_date"
                ],
                "required_end_date": phase_config["required_end_date"],
                "pre_xbrl_gap_requires_parser_or_vendor": True,
                "conservative_processing_delay_minutes": int(
                    phase_config["conservative_processing_delay_minutes"]
                ),
                "fundamental_panel_build_allowed": False,
                "feature_calculation_allowed": False,
                "model_training_allowed": False,
                "backtest_allowed": False,
                "next_phase": (
                    "Phase 23D — sentiment/news source and timestamp audit; "
                    "Phase23B universe acquisition and Phase23C fundamental acquisition remain "
                    "blocking for stock-model training"
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
                    "Phase 23C passed as a source and availability audit: official SEC filing "
                    "metadata, standardized-fact, and as-filed-document contracts are defined, "
                    "but no canonical fundamental panel is approved yet."
                    if bool(row["phase_execution_gates_passed"])
                    else "Phase 23C failed: the fundamental source or timing contract is incomplete."
                ),
                "fundamental_source_contract_ready": bool(
                    row["fundamental_source_contract_ready"]
                ),
                "fundamental_data_ready": bool(row["fundamental_data_ready"]),
                "allowed_next_step": (
                    "audit sentiment/news sources and prepare a small SEC acquisition pilot"
                ),
                "blocked_next_step": (
                    "fundamental feature panel, stock-model training, stock-selection backtest, "
                    "paper orders, live trading, real money, broker API"
                ),
            }
        ]
    )


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    titles = {
        "source_registry": "Source Registry",
        "source_scorecard": "Source Scorecard",
        "filing_event_schema": "Filing Event Schema",
        "fundamental_fact_schema": "Fundamental Fact Schema",
        "filing_availability_policy": "Filing Availability Policy",
        "restatement_policy": "Restatement Policy",
        "pre_xbrl_coverage_policy": "Pre-XBRL Coverage Policy",
        "feature_concept_registry": "Initial Feature/Concept Registry",
        "context_selection_rules": "Context Selection Rules",
        "validation_plan": "Validation Plan",
        "acquisition_plan": "Acquisition Plan",
        "scope_boundary": "Phase Boundary",
        "gate_report": "Gate Report",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    lines = [
        "# Phase 23C — Fundamental Data Source, Filing-Lag and Restatement Audit",
        "",
        (
            "This phase defines the point-in-time contract for SEC filing metadata and "
            "fundamental facts. It does not download data, construct a fundamental panel, "
            "calculate stock features, train models, backtest stock selection, or create orders."
        ),
        "",
    ]
    for key, title in titles.items():
        lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23c_fundamental_data_source_audit(
    *, config: dict[str, Any], reports_dir: str | Path
) -> dict[str, pd.DataFrame]:
    phase_config = _phase_config(config)
    if not phase_config["enabled"]:
        empty = pd.DataFrame()
        return {"summary": empty, "gate_report": empty, "conclusion": empty}

    output_dir = _resolve_configured_path(
        configured_path=phase_config["output_dir"], reports_dir=reports_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    source_registry = build_source_registry()
    source_scorecard = build_source_scorecard(source_registry)
    filing_event_schema = build_filing_event_schema()
    fundamental_fact_schema = build_fundamental_fact_schema()
    availability_policy = build_filing_availability_policy(phase_config)
    restatement_policy = build_restatement_policy()
    pre_xbrl_coverage_policy = build_pre_xbrl_coverage_policy(phase_config)
    feature_concept_registry = build_feature_concept_registry()
    context_selection_rules = build_context_selection_rules()
    validation_plan = build_validation_plan()
    acquisition_plan = build_acquisition_plan(phase_config)
    scope_boundary = build_scope_boundary(phase_config)
    gate_report = build_gate_report(
        phase_config=phase_config,
        source_registry=source_registry,
        source_scorecard=source_scorecard,
        filing_event_schema=filing_event_schema,
        fundamental_fact_schema=fundamental_fact_schema,
        availability_policy=availability_policy,
        restatement_policy=restatement_policy,
        pre_xbrl_coverage_policy=pre_xbrl_coverage_policy,
        feature_concept_registry=feature_concept_registry,
        context_selection_rules=context_selection_rules,
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
        "filing_event_schema": filing_event_schema,
        "fundamental_fact_schema": fundamental_fact_schema,
        "filing_availability_policy": availability_policy,
        "restatement_policy": restatement_policy,
        "pre_xbrl_coverage_policy": pre_xbrl_coverage_policy,
        "feature_concept_registry": feature_concept_registry,
        "context_selection_rules": context_selection_rules,
        "validation_plan": validation_plan,
        "acquisition_plan": acquisition_plan,
        "scope_boundary": scope_boundary,
        "gate_report": gate_report,
        "summary": summary,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23c_{name}.csv", index=False)

    build_empty_filing_event_template().to_csv(
        output_dir / "phase23c_filing_event_import_template.csv", index=False
    )
    build_empty_fundamental_fact_template().to_csv(
        output_dir / "phase23c_fundamental_fact_import_template.csv", index=False
    )
    _write_markdown(outputs, output_dir / "phase23c_fundamental_data_source_audit.md")

    dashboard_path = _resolve_configured_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23c_fundamental_data_source_audit_status_written"
    dashboard["notes"] = (
        "SEC source and point-in-time filing contracts are ready; raw acquisition, accession "
        "joins, context mapping, and restatement replay remain required before model training."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23C fundamental data source audit reports.")
    return outputs
