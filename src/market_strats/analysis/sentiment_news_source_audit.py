from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE23D_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23d_sentiment_news_source_audit"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23d_sentiment_news_source_audit_status.csv"
    ),
    "audit_as_of_date": "2026-06-13",
    "required_start_date": "2006-04-28",
    "required_end_date": "2026-05-01",
    "gdelt2_start_date": "2015-02-19",
    "phase_decision": "phase23d_timestamp_contract_ready_acquisition_pending",
    "conservative_processing_delay_minutes": 5,
    "allow_data_download": False,
    "allow_text_panel_build": False,
    "allow_sentiment_calculation": False,
    "allow_feature_calculation": False,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}

VALID_SOURCE_TYPES = {
    "SEC_FILING_TEXT",
    "ISSUER_PRESS_RELEASE",
    "LICENSED_NEWS",
    "EARNINGS_CALL_TRANSCRIPT",
    "ANALYST_ACTION",
    "SOCIAL_POST",
    "MACRO_RELEASE",
    "OPEN_NEWS_METADATA",
}

VALID_UPDATE_TYPES = {
    "INITIAL",
    "UPDATE",
    "CORRECTION",
    "RETRACTION",
    "DELETION",
    "TRANSCRIPT_REVISION",
}

NEWS_EVENT_REQUIRED_COLUMNS = [
    "event_id",
    "source_provider",
    "source_type",
    "source_event_id",
    "published_timestamp_utc",
    "first_seen_timestamp_utc",
    "knowledge_timestamp_utc",
    "event_version",
    "update_type",
    "permanent_security_id",
    "ticker",
    "headline",
    "body_hash",
    "language",
    "source_reference",
    "source_retrieved_at_utc",
    "license_class",
    "is_canonical",
]

SENTIMENT_OBSERVATION_REQUIRED_COLUMNS = [
    "event_id",
    "event_version",
    "permanent_security_id",
    "model_id",
    "model_version",
    "calculated_timestamp_utc",
    "feature_available_timestamp_utc",
    "sentiment_score",
    "confidence_score",
    "entity_relevance_score",
    "source_revision",
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
        DEFAULT_PHASE23D_CONFIG,
        config.get("phase23d_sentiment_news_source_audit", {}),
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
    """Resolve configured paths without creating ``reports/reports``.

    A path already rooted at ``reports`` is anchored to the supplied reports root.
    Other relative paths are interpreted underneath that root. ``Path.parts`` keeps
    the behaviour identical on Windows and POSIX systems.
    """

    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def build_source_registry() -> pd.DataFrame:
    rows = [
        {
            "source_id": "SEC_FILING_TEXT_AND_EXHIBITS",
            "source_family": "regulatory_text",
            "provider": "U.S. Securities and Exchange Commission",
            "source_name": "EDGAR filing documents, exhibits, and accepted-time metadata",
            "source_class": "official_public_text_canonical_candidate",
            "official_provider": True,
            "programmatic_access": True,
            "historical_coverage_claim": "full_edgar_archive_subject_to_form_parser_audit",
            "event_timestamp_quality": "accepted_timestamp_available",
            "revision_lineage": True,
            "deletion_or_retraction_state": "amendment_and_filing_history_available",
            "stable_entity_identifier": "CIK_join_required",
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "filing tone, risk-factor change, management uncertainty, and "
                "earnings-release exhibit text"
            ),
            "audit_status": "approved_contract_source_download_and_parser_pilot_pending",
            "evidence_reference": (
                "https://www.sec.gov/search-filings/"
                "edgar-application-programming-interfaces"
            ),
        },
        {
            "source_id": "LICENSED_MACHINE_READABLE_NEWS",
            "source_family": "company_news",
            "provider": "Approved institutional news vendor",
            "source_name": "Timestamped machine-readable company news archive",
            "source_class": "licensed_canonical_candidate",
            "official_provider": False,
            "programmatic_access": True,
            "historical_coverage_claim": "vendor_entitlement_and_backfile_to_verify",
            "event_timestamp_quality": "first_seen_and_update_timestamps_required",
            "revision_lineage": True,
            "deletion_or_retraction_state": "required_by_contract",
            "stable_entity_identifier": "vendor_permanent_id_mapping_required",
            "license_or_subscription_required": True,
            "public_free_source": False,
            "intended_use": (
                "company-specific news relevance, novelty, event taxonomy, volume, and tone"
            ),
            "audit_status": "preferred_pending_vendor_sample_license_and_backfile_validation",
            "evidence_reference": "vendor_contract_and_sample_required",
        },
        {
            "source_id": "LICENSED_EARNINGS_CALL_TRANSCRIPTS",
            "source_family": "earnings_calls",
            "provider": "Approved transcript vendor",
            "source_name": "Timestamped earnings-call transcript and revision archive",
            "source_class": "licensed_canonical_candidate",
            "official_provider": False,
            "programmatic_access": True,
            "historical_coverage_claim": "vendor_backfile_to_verify",
            "event_timestamp_quality": "call_start_end_and_transcript_release_required",
            "revision_lineage": True,
            "deletion_or_retraction_state": "revision_history_required",
            "stable_entity_identifier": "permanent_security_and_event_id_required",
            "license_or_subscription_required": True,
            "public_free_source": False,
            "intended_use": (
                "prepared-remarks tone, Q&A tone, uncertainty, topic shifts, and speaker roles"
            ),
            "audit_status": "pending_vendor_sample_and_transcript_vintage_validation",
            "evidence_reference": "vendor_contract_and_sample_required",
        },
        {
            "source_id": "LICENSED_ANALYST_ACTIONS",
            "source_family": "analyst_actions",
            "provider": "Approved estimates and analyst-actions vendor",
            "source_name": "Point-in-time ratings, target prices, and estimate revisions",
            "source_class": "licensed_canonical_candidate",
            "official_provider": False,
            "programmatic_access": True,
            "historical_coverage_claim": "vendor_vintage_history_to_verify",
            "event_timestamp_quality": "publication_and_vendor_first_seen_required",
            "revision_lineage": True,
            "deletion_or_retraction_state": "correction_history_required",
            "stable_entity_identifier": "permanent_security_id_required",
            "license_or_subscription_required": True,
            "public_free_source": False,
            "intended_use": (
                "upgrade/downgrade events, target changes, estimate dispersion, and revision breadth"
            ),
            "audit_status": "pending_vendor_sample_vintage_and_survivorship_validation",
            "evidence_reference": "vendor_contract_and_sample_required",
        },
        {
            "source_id": "ISSUER_IR_PRESS_RELEASES",
            "source_family": "issuer_disclosures",
            "provider": "Public-company investor-relations sites",
            "source_name": "Issuer press releases and presentation archives",
            "source_class": "official_issuer_validation_and_forward_capture_source",
            "official_provider": True,
            "programmatic_access": "issuer_specific",
            "historical_coverage_claim": "archive_completeness_not_guaranteed",
            "event_timestamp_quality": "issuer_timestamp_and_first_seen_required",
            "revision_lineage": "issuer_specific",
            "deletion_or_retraction_state": "issuer_specific",
            "stable_entity_identifier": "CIK_or_permanent_security_mapping_required",
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": "forward capture and cross-check of material issuer announcements",
            "audit_status": "validation_only_until_completeness_is_demonstrated",
            "evidence_reference": "issuer_ir_site_and_sec_exhibit_cross_check",
        },
        {
            "source_id": "GDELT_2_GKG_EVENTS",
            "source_family": "open_news_metadata",
            "provider": "The GDELT Project",
            "source_name": "GDELT 2.0 Events, Mentions, GKG, and GCAM metadata",
            "source_class": "open_research_candidate_not_canonical_yet",
            "official_provider": True,
            "programmatic_access": True,
            "historical_coverage_claim": "gdelt2_from_2015_with_earlier_products_separate",
            "event_timestamp_quality": "published_and_15_minute_ingestion_metadata",
            "revision_lineage": "deduplication_and_story_lineage_audit_required",
            "deletion_or_retraction_state": "not_guaranteed_as_editorial_retraction_feed",
            "stable_entity_identifier": "issuer_entity_linking_required",
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "broad news volume, themes, geography, macro tone, and secondary validation"
            ),
            "audit_status": "experimental_until_coverage_entity_and_revision_audits_pass",
            "evidence_reference": (
                "https://blog.gdeltproject.org/"
                "gdelt-2-0-our-global-world-in-realtime/"
            ),
        },
        {
            "source_id": "OFFICIAL_MACRO_RELEASES",
            "source_family": "macro_news",
            "provider": "Federal Reserve, BLS, BEA, Treasury, and other official agencies",
            "source_name": "Official release calendars, statements, and release documents",
            "source_class": "official_public_macro_event_canonical_candidate",
            "official_provider": True,
            "programmatic_access": "agency_specific",
            "historical_coverage_claim": "agency_archive_and_vintage_audit_required",
            "event_timestamp_quality": "scheduled_release_and_publication_timestamp_required",
            "revision_lineage": True,
            "deletion_or_retraction_state": "agency_correction_policy",
            "stable_entity_identifier": "macro_series_or_event_id",
            "license_or_subscription_required": False,
            "public_free_source": True,
            "intended_use": (
                "policy tone, release surprise context, recession/inflation themes, and event risk"
            ),
            "audit_status": "approved_contract_family_source_specific_pilots_pending",
            "evidence_reference": "official_agency_release_archives",
        },
        {
            "source_id": "REDDIT_OFFICIAL_API",
            "source_family": "social_sentiment",
            "provider": "Reddit",
            "source_name": "Official Reddit posts and comments API",
            "source_class": "experimental_social_source",
            "official_provider": True,
            "programmatic_access": True,
            "historical_coverage_claim": "access_tier_and_archive_completeness_to_verify",
            "event_timestamp_quality": "created_timestamp_plus_first_seen_required",
            "revision_lineage": "edits_and_deletions_must_be_versioned",
            "deletion_or_retraction_state": "deleted_removed_state_required",
            "stable_entity_identifier": "ticker_entity_resolution_required",
            "license_or_subscription_required": "terms_and_access_tier_dependent",
            "public_free_source": "limited_or_terms_dependent",
            "intended_use": (
                "retail attention, message volume, sentiment dispersion, and crowd disagreement"
            ),
            "audit_status": "experimental_not_canonical_without_legal_and_history_audit",
            "evidence_reference": "https://www.reddit.com/dev/api/",
        },
        {
            "source_id": "X_OFFICIAL_API",
            "source_family": "social_sentiment",
            "provider": "X",
            "source_name": "Official X posts API",
            "source_class": "experimental_social_source",
            "official_provider": True,
            "programmatic_access": True,
            "historical_coverage_claim": "access_tier_and_archive_entitlement_to_verify",
            "event_timestamp_quality": "created_at_plus_first_seen_required",
            "revision_lineage": "edits_quotes_reposts_and_deletions_must_be_versioned",
            "deletion_or_retraction_state": "delete_compliance_required",
            "stable_entity_identifier": "ticker_entity_resolution_required",
            "license_or_subscription_required": True,
            "public_free_source": False,
            "intended_use": "real-time attention and event-reaction research only",
            "audit_status": "experimental_not_canonical_without_license_history_and_bias_audit",
            "evidence_reference": "https://developer.x.com/en/docs/x-api",
        },
        {
            "source_id": "USER_SUPPLIED_LICENSED_TEXT_EXPORT",
            "source_family": "controlled_ingestion",
            "provider": "Approved licensed vendor export",
            "source_name": "Local point-in-time news/sentiment event export",
            "source_class": "ingestion_contract_not_a_source",
            "official_provider": False,
            "programmatic_access": True,
            "historical_coverage_claim": "depends_on_upstream_vendor",
            "event_timestamp_quality": "required_by_import_contract",
            "revision_lineage": "required_by_import_contract",
            "deletion_or_retraction_state": "required_by_import_contract",
            "stable_entity_identifier": "required_by_import_contract",
            "license_or_subscription_required": "depends_on_upstream_vendor",
            "public_free_source": False,
            "intended_use": "controlled local ingestion after legal and source approval",
            "audit_status": "schema_ready_source_not_yet_supplied",
            "evidence_reference": "local_file_contract",
        },
    ]
    return pd.DataFrame(rows)


def build_source_scorecard(source_registry: pd.DataFrame) -> pd.DataFrame:
    frame = source_registry.copy()
    frame["authority_score"] = frame["official_provider"].astype(bool).astype(int) * 2
    frame["automation_score"] = frame["programmatic_access"].map(
        {True: 2, False: 0, "issuer_specific": 1, "agency_specific": 1}
    ).fillna(0)
    frame["timestamp_score"] = frame["event_timestamp_quality"].astype(str).map(
        lambda value: 2 if "required" not in value and "available" in value else 1
    )
    frame["lineage_score"] = frame["revision_lineage"].map(
        {True: 2, False: 0, "required_by_import_contract": 1, "issuer_specific": 1}
    ).fillna(1)
    frame["identifier_score"] = frame["stable_entity_identifier"].astype(str).map(
        lambda value: 2 if value in {"CIK_join_required", "permanent_security_id_required"} else 1
    )
    frame["audit_score"] = frame[
        [
            "authority_score",
            "automation_score",
            "timestamp_score",
            "lineage_score",
            "identifier_score",
        ]
    ].sum(axis=1)
    frame["source_contract_ready"] = frame["source_id"].isin(
        {"SEC_FILING_TEXT_AND_EXHIBITS", "OFFICIAL_MACRO_RELEASES"}
    )
    frame["canonical_data_ready_now"] = False
    frame["canonical_blocking_reason"] = frame["source_class"].map(
        {
            "official_public_text_canonical_candidate": (
                "raw acquisition, parser, entity mapping, and text-version audit pending"
            ),
            "licensed_canonical_candidate": (
                "license, historical backfile, first-seen timestamp, revision, and sample audit pending"
            ),
            "official_issuer_validation_and_forward_capture_source": (
                "issuer archives are not assumed complete historical feeds"
            ),
            "open_research_candidate_not_canonical_yet": (
                "coverage, entity linking, deduplication, and retraction audits pending"
            ),
            "official_public_macro_event_canonical_candidate": (
                "agency-specific release and vintage ingestion pilots pending"
            ),
            "experimental_social_source": (
                "access rights, historical completeness, edit/delete lineage, and sampling bias pending"
            ),
            "ingestion_contract_not_a_source": "upstream approved data has not been supplied",
        }
    )
    return frame.sort_values(
        ["source_contract_ready", "audit_score", "source_id"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_news_event_schema() -> pd.DataFrame:
    rows = [
        ("event_id", "string", True, "deterministic internal event/version identifier"),
        ("source_provider", "string", True, "upstream publisher or vendor"),
        ("source_type", "string", True, "regulated news/text source family"),
        ("source_event_id", "string", True, "stable upstream story/post/filing identifier"),
        ("root_event_id", "string", False, "original story/event linking all revisions"),
        ("published_timestamp_utc", "timestamp", True, "publisher-declared publication time"),
        ("first_seen_timestamp_utc", "timestamp", True, "first time the feed exposed the event"),
        ("knowledge_timestamp_utc", "timestamp", True, "earliest model-eligible timestamp"),
        ("revision_timestamp_utc", "timestamp", False, "publisher/vendor revision timestamp"),
        ("event_version", "integer", True, "monotonic version within root event"),
        ("update_type", "string", True, "initial/update/correction/retraction/deletion"),
        ("permanent_security_id", "string", True, "point-in-time tradable share-line identity"),
        ("permanent_company_id", "string", False, "stable issuer identity"),
        ("ticker", "string", True, "ticker valid at event time"),
        ("headline", "string", True, "headline/title as observed in this version"),
        ("body_hash", "string", True, "immutable hash of normalized source text"),
        ("language", "string", True, "BCP-47 or source language code"),
        ("event_category", "string", False, "earnings, product, M&A, legal, macro, etc."),
        ("entity_link_method", "string", False, "vendor ID, CIK, alias map, or model link"),
        ("source_reference", "string", True, "URL, accession, vendor key, or archive record"),
        ("source_retrieved_at_utc", "timestamp", True, "immutable local retrieval timestamp"),
        ("source_revision", "string", False, "vendor file revision or checksum"),
        ("license_class", "string", True, "licensed, public_official, or experimental"),
        ("is_canonical", "boolean", True, "true only after source and lineage approval"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_sentiment_observation_schema() -> pd.DataFrame:
    rows = [
        ("event_id", "string", True, "news/text event being scored"),
        ("event_version", "integer", True, "exact source version scored"),
        ("permanent_security_id", "string", True, "security receiving the observation"),
        ("model_id", "string", True, "registered sentiment/event model"),
        ("model_version", "string", True, "immutable model artifact version"),
        ("calculated_timestamp_utc", "timestamp", True, "when scoring completed"),
        (
            "feature_available_timestamp_utc",
            "timestamp",
            True,
            "max(source knowledge time, scoring completion time)",
        ),
        ("sentiment_score", "float", True, "signed score constrained to [-1, 1]"),
        ("confidence_score", "float", True, "model confidence constrained to [0, 1]"),
        ("entity_relevance_score", "float", True, "issuer relevance constrained to [0, 1]"),
        ("novelty_score", "float", False, "novelty versus earlier known events"),
        ("uncertainty_score", "float", False, "uncertainty or ambiguity score"),
        ("event_category", "string", False, "registered event taxonomy label"),
        ("source_revision", "string", True, "source event checksum/version"),
        ("feature_revision", "string", False, "feature pipeline revision"),
        ("is_training_eligible", "boolean", True, "false for blocked/retracted/unmapped rows"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_timestamp_availability_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    delay = int(phase_config["conservative_processing_delay_minutes"])
    rows = [
        (
            "T1",
            "first_seen_is_primary_feed_clock",
            "A vendor/publisher timestamp never makes an event usable before first_seen_timestamp_utc.",
        ),
        (
            "T2",
            "processing_delay",
            f"knowledge_timestamp_utc is at least first-seen time plus {delay} minutes.",
        ),
        (
            "T3",
            "published_time_not_sufficient",
            "Publisher-declared publication time alone is not proof that the model could retrieve it.",
        ),
        (
            "T4",
            "revision_time_is_new_information",
            "Corrections, updates, transcript revisions, retractions, and deletions apply only from their own first-seen time.",
        ),
        (
            "T5",
            "market_cycle_mapping",
            "After-close and non-trading-day events first affect the next eligible decision/execution cycle.",
        ),
        (
            "T6",
            "scoring_completion_is_required",
            "A derived sentiment feature is unavailable until both source knowledge time and model scoring completion.",
        ),
        (
            "T7",
            "retrieval_time_not_backfilled",
            "A late historical download cannot be assigned an earlier first-seen timestamp without auditable vendor history.",
        ),
        (
            "T8",
            "timezone_normalization",
            "All source clocks are preserved raw and normalized to UTC with explicit timezone provenance.",
        ),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "rule", "requirement"])


def build_revision_deduplication_policy() -> pd.DataFrame:
    rows = [
        ("R1", "append_never_overwrite", "Every observed story/post/transcript version remains immutable."),
        ("R2", "root_event_lineage", "Updates and corrections link to one root_event_id and monotonic event_version."),
        ("R3", "retraction_not_deletion", "Retractions block future eligibility but do not erase the historically observed text."),
        ("R4", "duplicate_story_clusters", "Syndicated copies are clustered but first-seen timing remains source-specific."),
        ("R5", "body_hash_versioning", "Changed normalized text or metadata creates a new source revision."),
        ("R6", "transcript_vintages", "Live, preliminary, corrected, and final transcripts remain separate vintages."),
        ("R7", "social_edit_delete_state", "Edited/deleted/removed social content is represented through explicit versions and states."),
        ("R8", "feature_recalculation_versioned", "Re-scoring with a new NLP model creates a new feature revision, never a rewritten historical feature."),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "policy", "requirement"])


def build_entity_linking_policy() -> pd.DataFrame:
    rows = [
        ("E1", "permanent_id_primary", "Canonical events require a permanent security or issuer identifier."),
        ("E2", "ticker_is_time_varying", "Ticker text is resolved using the point-in-time identity map from Phase23B."),
        ("E3", "multi_entity_allocation", "One event may map to multiple issuers with separate relevance scores."),
        ("E4", "ambiguous_alias_block", "Unresolved common words or ambiguous tickers remain unassigned and training-ineligible."),
        ("E5", "subsidiary_parent_mapping", "Subsidiary/product events require an auditable parent-security relationship valid at event time."),
        ("E6", "index_macro_separation", "Macro/index-wide events are stored separately from company-specific events."),
        ("E7", "link_model_versioning", "Automated entity-link model and alias dictionaries are versioned."),
        ("E8", "future_identity_block", "Future mergers, ticker changes, or names cannot be used to resolve earlier events unless historically knowable."),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "policy", "requirement"])


def build_coverage_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "coverage_segment": "canonical_company_news_backfile",
                "start_date": phase_config["required_start_date"],
                "end_date": phase_config["required_end_date"],
                "required_source": "licensed timestamped news archive",
                "canonical_ready_now": False,
                "training_policy": "exclude until licensed first-seen and revision history pass validation",
                "blocking_reason": "licensed backfile not acquired or validated",
            },
            {
                "coverage_segment": "sec_filing_text",
                "start_date": phase_config["required_start_date"],
                "end_date": phase_config["required_end_date"],
                "required_source": "SEC EDGAR filing documents and accepted timestamps",
                "canonical_ready_now": False,
                "training_policy": "exclude until parser, text hashing, and accession-time joins pass",
                "blocking_reason": "raw acquisition and text parser pilot not run",
            },
            {
                "coverage_segment": "gdelt2_open_news_metadata",
                "start_date": phase_config["gdelt2_start_date"],
                "end_date": phase_config["required_end_date"],
                "required_source": "GDELT 2.0 GKG/Events/Mentions",
                "canonical_ready_now": False,
                "training_policy": "secondary or experimental only until entity and revision audits pass",
                "blocking_reason": "does not independently satisfy full 2006 onward canonical company-news history",
            },
            {
                "coverage_segment": "social_sentiment_history",
                "start_date": phase_config["required_start_date"],
                "end_date": phase_config["required_end_date"],
                "required_source": "approved historical social archive with edit/delete lineage",
                "canonical_ready_now": False,
                "training_policy": "optional ablation family; never required for baseline model",
                "blocking_reason": "historical completeness, licensing, and sampling bias unresolved",
            },
            {
                "coverage_segment": "forward_shadow_collection",
                "start_date": phase_config["audit_as_of_date"],
                "end_date": "open",
                "required_source": "approved forward capture feeds",
                "canonical_ready_now": False,
                "training_policy": "store raw events only after legal/source approval; no orders",
                "blocking_reason": "source approval and ingestion implementation pending",
            },
        ]
    )


def build_feature_registry() -> pd.DataFrame:
    rows = [
        ("news_sentiment_1d", "company_news", "relevance-weighted issuer news tone over 1 day", "pilot_required"),
        ("news_sentiment_5d", "company_news", "relevance-weighted issuer news tone over 5 days", "pilot_required"),
        ("news_volume_surprise", "company_news", "event count versus trailing issuer baseline", "pilot_required"),
        ("news_novelty", "company_news", "novelty versus previously known story clusters", "pilot_required"),
        ("negative_event_intensity", "event_risk", "legal, fraud, bankruptcy, regulatory, and controversy intensity", "pilot_required"),
        ("positive_catalyst_intensity", "event_risk", "product, contract, guidance, approval, and strategic catalyst intensity", "pilot_required"),
        ("filing_tone", "filing_text", "tone of as-filed regulatory text", "pilot_required"),
        ("risk_factor_change", "filing_text", "semantic change in risk-factor sections versus prior known filing", "pilot_required"),
        ("management_uncertainty", "filing_text", "uncertainty and forward-looking language score", "pilot_required"),
        ("earnings_call_prepared_tone", "earnings_calls", "prepared remarks sentiment and uncertainty", "licensed_source_required"),
        ("earnings_call_qa_tone", "earnings_calls", "analyst Q&A sentiment, evasiveness, and disagreement", "licensed_source_required"),
        ("analyst_revision_breadth", "analyst_actions", "net upgrades/downgrades and estimate revisions", "licensed_source_required"),
        ("target_price_revision", "analyst_actions", "point-in-time target-price revision magnitude", "licensed_source_required"),
        ("social_attention", "social_sentiment", "issuer-linked message volume versus baseline", "experimental_optional"),
        ("social_sentiment_dispersion", "social_sentiment", "cross-message disagreement and polarity dispersion", "experimental_optional"),
        ("macro_policy_tone", "macro_news", "official policy-statement tone and topic intensity", "pilot_required"),
        ("macro_release_event_risk", "macro_news", "scheduled release and surprise-event risk context", "pilot_required"),
        ("cross_source_sentiment_consensus", "ensemble", "agreement across approved independent source families", "future_ensemble"),
    ]
    return pd.DataFrame(
        rows,
        columns=["canonical_feature", "family", "definition", "mapping_status"],
    )


def build_validation_plan() -> pd.DataFrame:
    rows = [
        ("V1", "schema completeness", "all required event and sentiment fields present"),
        ("V2", "timestamp ordering", "published <= first seen <= knowledge <= feature availability"),
        ("V3", "processing delay", "knowledge time satisfies configured conservative delay"),
        ("V4", "event/version uniqueness", "event_id and event_version uniquely identify one immutable source version"),
        ("V5", "revision lineage", "updates/corrections/retractions link to a root event"),
        ("V6", "body integrity", "body hash matches normalized archived text"),
        ("V7", "entity precision", "sample entity links meet preregistered precision and ambiguity thresholds"),
        ("V8", "point-in-time ticker mapping", "event identity resolves through Phase23B mapping valid at event time"),
        ("V9", "coverage continuity", "approved backfile covers required period with documented outages"),
        ("V10", "survivorship retention", "removed, delisted, bankrupt, and acquired issuers remain queryable"),
        ("V11", "deduplication stability", "story clusters are deterministic and do not leak future copies"),
        ("V12", "retraction behaviour", "historically observed events remain but future eligibility changes at retraction time"),
        ("V13", "sentiment calibration", "scores are stable, bounded, and calibrated by source/event family"),
        ("V14", "language handling", "language detection/translation path is versioned and audited"),
        ("V15", "license provenance", "every canonical event has documented permitted research use"),
        ("V16", "immutable raw archive", "checksums, retrieval timestamps, and source vintages are preserved"),
    ]
    return pd.DataFrame(rows, columns=["test_id", "test", "acceptance_rule"])


def build_acquisition_plan(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "action": "Acquire SEC filing-text pilot for representative issuers and forms",
            "source_family": "regulatory_text",
            "required_evidence": "accepted timestamps, accession joins, immutable text hashes, amendments",
            "status": "pending",
        },
        {
            "priority": 2,
            "action": "Request licensed machine-readable news samples and entitlement terms",
            "source_family": "company_news",
            "required_evidence": (
                f"coverage {phase_config['required_start_date']} through {phase_config['required_end_date']}; "
                "first-seen timestamps; updates; retractions; entity IDs; redistribution terms"
            ),
            "status": "pending",
        },
        {
            "priority": 3,
            "action": "Request point-in-time earnings-call transcript and analyst-action samples",
            "source_family": "earnings_calls_and_analyst_actions",
            "required_evidence": "release timestamps, transcript vintages, corrections, estimate vintages",
            "status": "pending",
        },
        {
            "priority": 4,
            "action": "Run GDELT and official macro-source pilot as secondary/experimental feeds",
            "source_family": "open_news_and_macro",
            "required_evidence": "coverage, timestamp, entity-link, duplicate, and revision diagnostics",
            "status": "not_started",
        },
        {
            "priority": 5,
            "action": "Complete legal and historical-completeness review for social sources",
            "source_family": "social_sentiment",
            "required_evidence": "terms, archive access, edit/delete state, sampling bias, bot controls",
            "status": "not_started_optional",
        },
        {
            "priority": 6,
            "action": "Approve canonical source paths and freeze raw import contracts",
            "source_family": "all",
            "required_evidence": "zero critical validation failures and documented license provenance",
            "status": "blocked_by_source_acquisition",
        },
    ]
    return pd.DataFrame(rows)


def build_scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    controls = {
        "data_download_allowed": phase_config["allow_data_download"],
        "text_panel_build_allowed": phase_config["allow_text_panel_build"],
        "sentiment_calculation_allowed": phase_config["allow_sentiment_calculation"],
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


def build_empty_news_event_template() -> pd.DataFrame:
    return pd.DataFrame(columns=build_news_event_schema()["column"].tolist())


def build_empty_sentiment_observation_template() -> pd.DataFrame:
    return pd.DataFrame(columns=build_sentiment_observation_schema()["column"].tolist())


def validate_news_event_frame(
    events: pd.DataFrame,
    *,
    conservative_processing_delay_minutes: int = 5,
) -> pd.DataFrame:
    missing_columns = sorted(set(NEWS_EVENT_REQUIRED_COLUMNS) - set(events.columns))
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
    required = working[NEWS_EVENT_REQUIRED_COLUMNS].fillna("").astype(str)
    nonblank = bool(required.apply(lambda column: column.str.strip().ne("")).all().all())
    rows.append(_gate("required_values_nonblank", nonblank, f"rows={len(working)}"))

    rows.append(
        _gate(
            "source_types_valid",
            bool(working["source_type"].isin(VALID_SOURCE_TYPES).all()),
            ";".join(sorted(set(working["source_type"].astype(str)))),
        )
    )
    rows.append(
        _gate(
            "update_types_valid",
            bool(working["update_type"].isin(VALID_UPDATE_TYPES).all()),
            ";".join(sorted(set(working["update_type"].astype(str)))),
        )
    )

    published = pd.to_datetime(working["published_timestamp_utc"], utc=True, errors="coerce")
    first_seen = pd.to_datetime(working["first_seen_timestamp_utc"], utc=True, errors="coerce")
    knowledge = pd.to_datetime(working["knowledge_timestamp_utc"], utc=True, errors="coerce")
    revision = pd.to_datetime(working.get("revision_timestamp_utc"), utc=True, errors="coerce")
    parsed = bool(published.notna().all() and first_seen.notna().all() and knowledge.notna().all())
    rows.append(_gate("timestamps_parse", parsed, f"rows={len(working)}"))

    ordering = bool(((published <= first_seen) & (first_seen <= knowledge)).all()) if parsed else False
    rows.append(_gate("published_first_seen_knowledge_ordering", ordering, "published <= first_seen <= knowledge"))

    delay = pd.Timedelta(minutes=int(conservative_processing_delay_minutes))
    delayed = bool((knowledge >= first_seen + delay).all()) if parsed else False
    rows.append(_gate("knowledge_respects_processing_delay", delayed, f"minutes={int(conservative_processing_delay_minutes)}"))

    revision_ok = True
    if revision is not None and revision.notna().any():
        revision_ok = bool((revision.dropna() >= published.loc[revision.notna()]).all())
    rows.append(_gate("revision_not_before_publication", revision_ok, "revision timestamp ordering"))

    versions = pd.to_numeric(working["event_version"], errors="coerce")
    rows.append(_gate("event_versions_positive", bool((versions >= 1).all()), f"rows={len(working)}"))

    unique = not bool(working.duplicated(["event_id", "event_version"]).any())
    rows.append(_gate("event_versions_unique", unique, f"rows={len(working)}"))

    canonical_safe = True
    canonical_rows = working.loc[working["is_canonical"].fillna(False).astype(bool)]
    if not canonical_rows.empty:
        allowed_licenses = {"licensed", "public_official"}
        canonical_safe = bool(
            canonical_rows["license_class"].astype(str).isin(allowed_licenses).all()
            and canonical_rows["permanent_security_id"].fillna("").astype(str).str.strip().ne("").all()
        )
    rows.append(_gate("canonical_rows_have_provenance_and_identity", canonical_safe, "licensed/public official plus permanent ID"))

    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def validate_sentiment_observation_frame(
    observations: pd.DataFrame,
    *,
    source_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    missing_columns = sorted(
        set(SENTIMENT_OBSERVATION_REQUIRED_COLUMNS) - set(observations.columns)
    )
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

    working = observations.copy()
    required = working[SENTIMENT_OBSERVATION_REQUIRED_COLUMNS].fillna("").astype(str)
    nonblank = bool(required.apply(lambda column: column.str.strip().ne("")).all().all())
    rows.append(_gate("required_values_nonblank", nonblank, f"rows={len(working)}"))

    calculated = pd.to_datetime(working["calculated_timestamp_utc"], utc=True, errors="coerce")
    available = pd.to_datetime(
        working["feature_available_timestamp_utc"], utc=True, errors="coerce"
    )
    parsed = bool(calculated.notna().all() and available.notna().all())
    rows.append(_gate("timestamps_parse", parsed, f"rows={len(working)}"))
    rows.append(
        _gate(
            "feature_not_available_before_calculation",
            bool((available >= calculated).all()) if parsed else False,
            "feature availability ordering",
        )
    )

    sentiment = pd.to_numeric(working["sentiment_score"], errors="coerce")
    confidence = pd.to_numeric(working["confidence_score"], errors="coerce")
    relevance = pd.to_numeric(working["entity_relevance_score"], errors="coerce")
    bounded = bool(
        sentiment.between(-1, 1).all()
        and confidence.between(0, 1).all()
        and relevance.between(0, 1).all()
    )
    rows.append(_gate("scores_bounded", bounded, "sentiment [-1,1], confidence/relevance [0,1]"))

    unique = not bool(
        working.duplicated(["event_id", "event_version", "model_id", "model_version"]).any()
    )
    rows.append(_gate("model_event_versions_unique", unique, f"rows={len(working)}"))

    source_join_ok = True
    if source_events is not None and not source_events.empty:
        source_keys = source_events[["event_id", "event_version", "knowledge_timestamp_utc"]].copy()
        source_keys["event_version"] = pd.to_numeric(source_keys["event_version"], errors="coerce")
        joined = working.merge(source_keys, on=["event_id", "event_version"], how="left")
        source_knowledge = pd.to_datetime(joined["knowledge_timestamp_utc"], utc=True, errors="coerce")
        feature_available = pd.to_datetime(joined["feature_available_timestamp_utc"], utc=True, errors="coerce")
        source_join_ok = bool(
            source_knowledge.notna().all()
            and (feature_available >= source_knowledge).all()
        )
    rows.append(_gate("feature_not_before_source_knowledge", source_join_ok, "source event join"))

    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def build_gate_report(
    *,
    phase_config: dict[str, Any],
    source_registry: pd.DataFrame,
    source_scorecard: pd.DataFrame,
    news_event_schema: pd.DataFrame,
    sentiment_schema: pd.DataFrame,
    timestamp_policy: pd.DataFrame,
    revision_policy: pd.DataFrame,
    entity_policy: pd.DataFrame,
    coverage_policy: pd.DataFrame,
    feature_registry: pd.DataFrame,
    validation_plan: pd.DataFrame,
    acquisition_plan: pd.DataFrame,
    scope_boundary: pd.DataFrame,
) -> pd.DataFrame:
    canonical_candidate_count = int(
        source_registry["source_class"].astype(str).str.contains("canonical_candidate").sum()
    )
    gates = [
        _gate("phase_enabled", bool(phase_config["enabled"]), "Phase23D explicitly enabled"),
        _gate("source_families_registered", len(source_registry) >= 9, f"sources={len(source_registry)}"),
        _gate("canonical_candidate_paths_identified", canonical_candidate_count >= 5, f"count={canonical_candidate_count}"),
        _gate("no_unvalidated_source_marked_data_ready", not bool(source_scorecard["canonical_data_ready_now"].any()), "acquisition and pilots remain pending"),
        _gate("news_event_schema_complete", len(news_event_schema) >= 20, f"columns={len(news_event_schema)}"),
        _gate("sentiment_schema_complete", len(sentiment_schema) >= 14, f"columns={len(sentiment_schema)}"),
        _gate("timestamp_policy_complete", len(timestamp_policy) >= 8, f"rules={len(timestamp_policy)}"),
        _gate("revision_policy_complete", len(revision_policy) >= 8, f"rules={len(revision_policy)}"),
        _gate("entity_policy_complete", len(entity_policy) >= 8, f"rules={len(entity_policy)}"),
        _gate("coverage_gaps_explicit", not bool(coverage_policy["canonical_ready_now"].any()), f"segments={len(coverage_policy)}"),
        _gate("feature_registry_defined", len(feature_registry) >= 15, f"features={len(feature_registry)}"),
        _gate("validation_plan_complete", len(validation_plan) >= 16, f"tests={len(validation_plan)}"),
        _gate("acquisition_plan_defined", len(acquisition_plan) >= 6, f"actions={len(acquisition_plan)}"),
        _gate("research_only_boundary_enforced", bool(scope_boundary["passed"].all()), f"controls={len(scope_boundary)}"),
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
    data_ready = bool(source_scorecard["canonical_data_ready_now"].any())
    contract_ready = execution_passed
    return pd.DataFrame(
        [
            {
                "phase": "Phase 23D",
                "phase23d_decision": (
                    phase_config["phase_decision"]
                    if execution_passed and not data_ready
                    else "phase23d_source_audit_blocked"
                    if not execution_passed
                    else "phase23d_canonical_sentiment_data_ready"
                ),
                "phase_execution_gates_passed": execution_passed,
                "all_gates_passed": execution_passed,
                "sentiment_news_source_contract_ready": contract_ready,
                "sentiment_news_data_ready": data_ready,
                "source_contracts_ready_count": int(source_scorecard["source_contract_ready"].sum()),
                "canonical_data_sources_ready_count": int(source_scorecard["canonical_data_ready_now"].sum()),
                "required_start_date": phase_config["required_start_date"],
                "required_end_date": phase_config["required_end_date"],
                "gdelt2_start_date": phase_config["gdelt2_start_date"],
                "licensed_company_news_backfile_required": True,
                "social_sentiment_optional_ablation_only": True,
                "conservative_processing_delay_minutes": int(phase_config["conservative_processing_delay_minutes"]),
                "text_panel_build_allowed": False,
                "sentiment_calculation_allowed": False,
                "feature_calculation_allowed": False,
                "model_training_allowed": False,
                "backtest_allowed": False,
                "next_phase": (
                    "Phase 23E — combined stock-level feature-panel contract; "
                    "Phase23B universe, Phase23C fundamentals, and Phase23D text/news acquisition "
                    "remain blocking for model training"
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
                    "Phase 23D passed as a source and timestamp-contract audit: text/news, "
                    "revision, entity-linking, and sentiment-feature rules are defined, but no "
                    "canonical historical news or sentiment panel is approved yet."
                    if bool(row["phase_execution_gates_passed"])
                    else "Phase 23D failed: the source audit or safety boundary is incomplete."
                ),
                "sentiment_news_data_ready": bool(row["sentiment_news_data_ready"]),
                "allowed_next_step": (
                    "request licensed samples, pilot SEC/open macro ingestion, and define Phase23E panel joins"
                ),
                "blocked_next_step": (
                    "historical sentiment features, stock-model training, stock backtests, paper orders, "
                    "live trading, real money, broker API"
                ),
            }
        ]
    )


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    titles = {
        "source_registry": "Source Registry",
        "source_scorecard": "Source Scorecard",
        "news_event_schema": "News/Text Event Schema",
        "sentiment_observation_schema": "Sentiment Observation Schema",
        "timestamp_availability_policy": "Timestamp Availability Policy",
        "revision_deduplication_policy": "Revision and Deduplication Policy",
        "entity_linking_policy": "Entity Linking Policy",
        "coverage_policy": "Coverage Policy",
        "feature_registry": "Initial Feature Registry",
        "validation_plan": "Validation Plan",
        "acquisition_plan": "Acquisition Plan",
        "scope_boundary": "Phase Boundary",
        "gate_report": "Gate Report",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    lines = [
        "# Phase 23D — Sentiment and News Source Timestamp Audit",
        "",
        (
            "This phase defines point-in-time source, timestamp, revision, entity-linking, and "
            "sentiment-feature contracts. It does not download historical feeds, build a text "
            "panel, calculate features, train models, backtest stocks, or create orders."
        ),
        "",
    ]
    for key, title in titles.items():
        lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23d_sentiment_news_source_audit(
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
    news_event_schema = build_news_event_schema()
    sentiment_schema = build_sentiment_observation_schema()
    timestamp_policy = build_timestamp_availability_policy(phase_config)
    revision_policy = build_revision_deduplication_policy()
    entity_policy = build_entity_linking_policy()
    coverage_policy = build_coverage_policy(phase_config)
    feature_registry = build_feature_registry()
    validation_plan = build_validation_plan()
    acquisition_plan = build_acquisition_plan(phase_config)
    scope_boundary = build_scope_boundary(phase_config)
    gate_report = build_gate_report(
        phase_config=phase_config,
        source_registry=source_registry,
        source_scorecard=source_scorecard,
        news_event_schema=news_event_schema,
        sentiment_schema=sentiment_schema,
        timestamp_policy=timestamp_policy,
        revision_policy=revision_policy,
        entity_policy=entity_policy,
        coverage_policy=coverage_policy,
        feature_registry=feature_registry,
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
        "news_event_schema": news_event_schema,
        "sentiment_observation_schema": sentiment_schema,
        "timestamp_availability_policy": timestamp_policy,
        "revision_deduplication_policy": revision_policy,
        "entity_linking_policy": entity_policy,
        "coverage_policy": coverage_policy,
        "feature_registry": feature_registry,
        "validation_plan": validation_plan,
        "acquisition_plan": acquisition_plan,
        "scope_boundary": scope_boundary,
        "gate_report": gate_report,
        "summary": summary,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23d_{name}.csv", index=False)

    build_empty_news_event_template().to_csv(
        output_dir / "phase23d_news_event_import_template.csv", index=False
    )
    build_empty_sentiment_observation_template().to_csv(
        output_dir / "phase23d_sentiment_observation_import_template.csv", index=False
    )
    _write_markdown(outputs, output_dir / "phase23d_sentiment_news_source_audit.md")

    dashboard_path = _resolve_configured_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23d_sentiment_news_source_audit_status_written"
    dashboard["notes"] = (
        "Timestamp and revision contracts are ready; licensed historical news/text samples, "
        "entity-link audits, and legal approval remain required before feature calculation."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23D sentiment and news source timestamp audit reports.")
    return outputs
