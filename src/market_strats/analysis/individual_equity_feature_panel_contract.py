from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE23E_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": (
        "reports/individual_equity_decision_system/"
        "phase23e_combined_feature_panel_contract"
    ),
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23e_combined_feature_panel_contract_status.csv"
    ),
    "audit_as_of_date": "2026-06-13",
    "required_start_date": "2006-04-28",
    "required_end_date": "2026-05-01",
    "decision_cadence": "weekly_after_close",
    "execution_policy": "next_trading_day_after_signal",
    "primary_target": "forward_20d_excess_return_vs_universe",
    "secondary_targets": [
        "forward_1d_excess_return_vs_universe",
        "forward_5d_excess_return_vs_universe",
        "forward_63d_excess_return_vs_universe",
        "forward_20d_positive_alpha_probability",
    ],
    "maximum_target_horizon_trading_days": 63,
    "purge_window_trading_days": 63,
    "embargo_window_trading_days": 63,
    "minimum_eligible_cross_section": 50,
    "phase_decision": "phase23e_combined_feature_panel_contract_ready_pilot_pending",
    "allow_data_download": False,
    "allow_panel_build": False,
    "allow_feature_calculation": False,
    "allow_target_calculation": False,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}

VALID_UNIVERSES = {"SP500_POINT_IN_TIME", "NASDAQ100_POINT_IN_TIME"}
VALID_SPLIT_LABELS = {"UNASSIGNED", "TRAIN", "VALIDATION", "TEST", "FINAL_HOLDOUT"}
VALID_FEATURE_FAMILIES = {
    "technical",
    "fundamental",
    "sentiment_news",
    "macro",
    "cross_asset",
    "market_stress",
    "liquidity_risk",
    "event_corporate_action",
    "missingness_quality",
}

FEATURE_PANEL_REQUIRED_COLUMNS = [
    "panel_row_id",
    "decision_timestamp_utc",
    "signal_date",
    "execution_date",
    "universe_id",
    "permanent_security_id",
    "permanent_company_id",
    "ticker_asof",
    "sector_asof",
    "industry_asof",
    "membership_known_timestamp_utc",
    "membership_effective_date",
    "membership_active",
    "model_cutoff_timestamp_utc",
    "technical_available_timestamp_utc",
    "fundamental_available_timestamp_utc",
    "sentiment_available_timestamp_utc",
    "macro_available_timestamp_utc",
    "cross_asset_available_timestamp_utc",
    "market_stress_available_timestamp_utc",
    "liquidity_available_timestamp_utc",
    "event_available_timestamp_utc",
    "feature_max_available_timestamp_utc",
    "feature_set_version",
    "source_snapshot_id",
    "split_label",
    "training_eligible",
]

TARGET_REQUIRED_COLUMNS = [
    "panel_row_id",
    "target_name",
    "target_horizon_trading_days",
    "target_value",
    "target_period_start_date",
    "target_period_end_date",
    "target_available_timestamp_utc",
    "target_set_version",
]

FEATURE_AVAILABILITY_COLUMNS = [
    "technical_available_timestamp_utc",
    "fundamental_available_timestamp_utc",
    "sentiment_available_timestamp_utc",
    "macro_available_timestamp_utc",
    "cross_asset_available_timestamp_utc",
    "market_stress_available_timestamp_utc",
    "liquidity_available_timestamp_utc",
    "event_available_timestamp_utc",
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
        DEFAULT_PHASE23E_CONFIG,
        config.get("phase23e_combined_feature_panel_contract", {}),
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
    """Resolve paths without creating a duplicated ``reports/reports`` prefix."""

    reports_root = Path(reports_dir)
    path = Path(configured_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "reports":
        return reports_root.joinpath(*path.parts[1:])
    return reports_root / path


def build_panel_grain_contract() -> pd.DataFrame:
    rows = [
        {
            "contract_id": "G1",
            "component": "row_grain",
            "requirement": (
                "Exactly one predictor row per decision timestamp, permanent share-line "
                "identifier, and point-in-time universe."
            ),
            "blocked_shortcut": "multiple_revisions_or_tickers_collapsed_without_lineage",
        },
        {
            "contract_id": "G2",
            "component": "decision_clock",
            "requirement": (
                "decision_timestamp_utc is the only cutoff clock for predictor eligibility."
            ),
            "blocked_shortcut": "date_only_join_without_intraday_availability",
        },
        {
            "contract_id": "G3",
            "component": "membership",
            "requirement": (
                "The security must be active in the selected universe on the signal date and "
                "the membership event must already be knowable."
            ),
            "blocked_shortcut": "today_constituents_backfilled_historically",
        },
        {
            "contract_id": "G4",
            "component": "identity",
            "requirement": (
                "Ticker, sector, and industry are as-of attributes; permanent identifiers are "
                "the join keys."
            ),
            "blocked_shortcut": "ticker_or_current_sector_as_permanent_key",
        },
        {
            "contract_id": "G5",
            "component": "predictor_target_separation",
            "requirement": (
                "Predictors and forward targets are stored in separate tables and joined only "
                "after panel eligibility is frozen."
            ),
            "blocked_shortcut": "forward_return_columns_in_feature_input",
        },
        {
            "contract_id": "G6",
            "component": "revision_lineage",
            "requirement": (
                "Every row identifies the source snapshot and feature-set version used to "
                "construct it."
            ),
            "blocked_shortcut": "silently_recomputed_historical_panel",
        },
    ]
    return pd.DataFrame(rows)


def build_feature_panel_schema() -> pd.DataFrame:
    rows = [
        ("panel_row_id", "string", True, "deterministic unique row identifier"),
        ("decision_timestamp_utc", "timestamp", True, "model decision cutoff"),
        ("signal_date", "date", True, "market date associated with the signal"),
        ("execution_date", "date", True, "next eligible trading date"),
        ("universe_id", "string", True, "point-in-time eligible universe"),
        ("permanent_security_id", "string", True, "stable tradable share-line identity"),
        ("permanent_company_id", "string", True, "stable issuer identity"),
        ("ticker_asof", "string", True, "ticker valid at decision time"),
        ("company_name_asof", "string", False, "issuer name valid at decision time"),
        ("sector_asof", "string", True, "sector classification valid at decision time"),
        ("industry_asof", "string", True, "industry classification valid at decision time"),
        (
            "membership_known_timestamp_utc",
            "timestamp",
            True,
            "when membership information became knowable",
        ),
        ("membership_effective_date", "date", True, "membership effective date"),
        ("membership_active", "boolean", True, "active membership at signal date"),
        ("model_cutoff_timestamp_utc", "timestamp", True, "latest predictor cutoff"),
        (
            "technical_available_timestamp_utc",
            "timestamp",
            True,
            "latest technical input availability",
        ),
        (
            "fundamental_available_timestamp_utc",
            "timestamp",
            True,
            "latest fundamental input availability",
        ),
        (
            "sentiment_available_timestamp_utc",
            "timestamp",
            True,
            "latest text/news feature availability",
        ),
        (
            "macro_available_timestamp_utc",
            "timestamp",
            True,
            "latest vintage-aware macro availability",
        ),
        (
            "cross_asset_available_timestamp_utc",
            "timestamp",
            True,
            "latest cross-asset input availability",
        ),
        (
            "market_stress_available_timestamp_utc",
            "timestamp",
            True,
            "latest market-stress aggregate availability",
        ),
        (
            "liquidity_available_timestamp_utc",
            "timestamp",
            True,
            "latest stock liquidity/risk input availability",
        ),
        (
            "event_available_timestamp_utc",
            "timestamp",
            True,
            "latest event/corporate-action guard availability",
        ),
        (
            "feature_max_available_timestamp_utc",
            "timestamp",
            True,
            "maximum availability timestamp across all predictor families",
        ),
        ("feature_set_version", "string", True, "immutable feature definition version"),
        ("source_snapshot_id", "string", True, "immutable source snapshot manifest"),
        ("split_label", "string", True, "walk-forward split assignment"),
        ("training_eligible", "boolean", True, "row passes all training gates"),
        ("exclusion_reasons", "string", False, "semicolon-separated fail-closed reasons"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_feature_manifest_schema() -> pd.DataFrame:
    rows = [
        ("feature_name", "string", True, "stable machine-readable feature name"),
        ("feature_family", "string", True, "registered feature family"),
        ("dtype", "string", True, "expected panel dtype"),
        ("definition", "string", True, "formula or semantic definition"),
        ("source_contract", "string", True, "approved upstream source contract"),
        ("availability_column", "string", True, "family availability clock"),
        ("lookback_trading_days", "integer", False, "historical window length"),
        ("minimum_observations", "integer", False, "minimum valid observations"),
        ("normalization", "string", True, "none, cross-sectional, sector-relative, etc."),
        ("imputation_policy", "string", True, "fail-closed missing-value treatment"),
        ("winsorization_policy", "string", True, "point-in-time outlier policy"),
        ("feature_version", "string", True, "immutable formula version"),
        ("pilot_status", "string", True, "contract_only, pilot_ready, or blocked"),
        ("training_allowed", "boolean", True, "false until upstream validation passes"),
    ]
    return pd.DataFrame(rows, columns=["column", "dtype", "required", "description"])


def build_feature_family_contract() -> pd.DataFrame:
    rows = [
        {
            "feature_family": "technical",
            "availability_column": "technical_available_timestamp_utc",
            "examples": "momentum; trend; volatility; volume; gaps; breadth",
            "join_contract": "security and decision timestamp; close-aligned point-in-time prices",
            "initial_status": "pilot_price_source_and_formula_validation_required",
        },
        {
            "feature_family": "fundamental",
            "availability_column": "fundamental_available_timestamp_utc",
            "examples": "growth; margins; quality; leverage; investment; valuation",
            "join_contract": "latest as-filed fact version known by cutoff",
            "initial_status": "phase23c_data_acquisition_and_mapping_required",
        },
        {
            "feature_family": "sentiment_news",
            "availability_column": "sentiment_available_timestamp_utc",
            "examples": "news tone; novelty; filing tone; analyst revisions; call tone",
            "join_contract": "event first-seen and scoring completion before cutoff",
            "initial_status": "phase23d_data_acquisition_and_entity_mapping_required",
        },
        {
            "feature_family": "macro",
            "availability_column": "macro_available_timestamp_utc",
            "examples": "rates; inflation; labour; growth; liquidity; credit",
            "join_contract": "release timestamp and historical vintage available by cutoff",
            "initial_status": "existing_macro_contract_reuse_and_panel_alignment_required",
        },
        {
            "feature_family": "cross_asset",
            "availability_column": "cross_asset_available_timestamp_utc",
            "examples": "dollar; bonds; commodities; volatility; crypto; credit",
            "join_contract": "timezone-normalized market observations available by cutoff",
            "initial_status": "existing_asset_sources_alignment_required",
        },
        {
            "feature_family": "market_stress",
            "availability_column": "market_stress_available_timestamp_utc",
            "examples": "breadth; dispersion; correlation; volatility; liquidity stress",
            "join_contract": "same-date eligible-universe aggregate only",
            "initial_status": "point_in_time_cross_section_required",
        },
        {
            "feature_family": "liquidity_risk",
            "availability_column": "liquidity_available_timestamp_utc",
            "examples": "ADV; spread proxy; realized volatility; beta; gap risk",
            "join_contract": "security-level trailing observations available by cutoff",
            "initial_status": "stock_price_and_volume_history_required",
        },
        {
            "feature_family": "event_corporate_action",
            "availability_column": "event_available_timestamp_utc",
            "examples": "earnings; guidance; splits; dividends; M&A; index events",
            "join_contract": "announcement and effective dates stored separately",
            "initial_status": "event_calendar_contract_and_source_required",
        },
        {
            "feature_family": "missingness_quality",
            "availability_column": "feature_max_available_timestamp_utc",
            "examples": "feature age; missing flags; source quality; stale-data flags",
            "join_contract": "derived only from point-in-time source availability",
            "initial_status": "panel_builder_required",
        },
    ]
    return pd.DataFrame(rows)


def build_initial_feature_manifest() -> pd.DataFrame:
    rows = [
        ("momentum_21d", "technical", "21-trading-day total return", "cross_sectional_zscore"),
        ("momentum_63d", "technical", "63-trading-day total return", "cross_sectional_zscore"),
        ("momentum_252d_skip21d", "technical", "12-1 month momentum", "cross_sectional_zscore"),
        ("trend_distance_200d", "technical", "price relative to 200-day mean", "cross_sectional_zscore"),
        ("realized_volatility_21d", "technical", "21-day realized volatility", "cross_sectional_zscore"),
        ("volume_surprise_20d", "technical", "volume versus trailing baseline", "cross_sectional_zscore"),
        ("revenue_growth_yoy", "fundamental", "as-filed revenue year-over-year growth", "sector_relative_zscore"),
        ("gross_margin", "fundamental", "as-filed gross profit divided by revenue", "sector_relative_zscore"),
        ("operating_margin", "fundamental", "as-filed operating income divided by revenue", "sector_relative_zscore"),
        ("free_cash_flow_margin", "fundamental", "as-filed FCF divided by revenue", "sector_relative_zscore"),
        ("return_on_assets", "fundamental", "TTM income divided by average assets", "sector_relative_zscore"),
        ("accruals_to_assets", "fundamental", "income less operating cash flow over assets", "sector_relative_zscore"),
        ("debt_to_assets", "fundamental", "point-in-time debt divided by assets", "sector_relative_zscore"),
        ("asset_growth_yoy", "fundamental", "asset growth versus prior year", "sector_relative_zscore"),
        ("news_sentiment_1d", "sentiment_news", "issuer news sentiment over one day", "cross_sectional_zscore"),
        ("news_sentiment_5d", "sentiment_news", "issuer news sentiment over five days", "cross_sectional_zscore"),
        ("news_volume_surprise", "sentiment_news", "issuer event volume versus baseline", "cross_sectional_zscore"),
        ("negative_event_intensity", "sentiment_news", "negative event taxonomy intensity", "cross_sectional_zscore"),
        ("filing_tone", "sentiment_news", "as-filed regulatory text tone", "sector_relative_zscore"),
        ("macro_growth_regime", "macro", "vintage-aware growth regime score", "none"),
        ("macro_inflation_regime", "macro", "vintage-aware inflation regime score", "none"),
        ("policy_rate_change_63d", "macro", "policy-rate change over 63 days", "none"),
        ("credit_spread_change_21d", "cross_asset", "credit spread change over 21 days", "none"),
        ("vix_term_structure", "cross_asset", "volatility term-structure slope", "none"),
        ("market_breadth_200d", "market_stress", "eligible members above 200-day mean", "none"),
        ("cross_sectional_dispersion_21d", "market_stress", "eligible-stock return dispersion", "none"),
        ("average_dollar_volume_20d", "liquidity_risk", "20-day average dollar volume", "log_cross_sectional_zscore"),
        ("beta_252d", "liquidity_risk", "rolling market beta", "cross_sectional_zscore"),
        ("days_to_next_earnings", "event_corporate_action", "calendar days to known earnings event", "none"),
        ("feature_missing_count", "missingness_quality", "count of unavailable predictor values", "none"),
        ("oldest_feature_age_days", "missingness_quality", "age of oldest source observation", "none"),
    ]
    columns = ["feature_name", "feature_family", "definition", "normalization"]
    frame = pd.DataFrame(rows, columns=columns)
    availability_map = {
        "technical": "technical_available_timestamp_utc",
        "fundamental": "fundamental_available_timestamp_utc",
        "sentiment_news": "sentiment_available_timestamp_utc",
        "macro": "macro_available_timestamp_utc",
        "cross_asset": "cross_asset_available_timestamp_utc",
        "market_stress": "market_stress_available_timestamp_utc",
        "liquidity_risk": "liquidity_available_timestamp_utc",
        "event_corporate_action": "event_available_timestamp_utc",
        "missingness_quality": "feature_max_available_timestamp_utc",
    }
    source_map = {
        "technical": "stock_price_volume_point_in_time",
        "fundamental": "phase23c_fundamental_contract",
        "sentiment_news": "phase23d_sentiment_news_contract",
        "macro": "vintage_aware_macro_contract",
        "cross_asset": "aligned_market_data_contract",
        "market_stress": "point_in_time_universe_aggregate",
        "liquidity_risk": "stock_price_volume_point_in_time",
        "event_corporate_action": "timestamped_event_calendar_contract",
        "missingness_quality": "panel_builder_lineage",
    }
    frame["dtype"] = "float64"
    frame["source_contract"] = frame["feature_family"].map(source_map)
    frame["availability_column"] = frame["feature_family"].map(availability_map)
    frame["lookback_trading_days"] = pd.NA
    frame["minimum_observations"] = pd.NA
    frame["imputation_policy"] = "explicit_missing_indicator_and_train_only_imputer"
    frame["winsorization_policy"] = "same_date_cross_section_or_train_only_parameters"
    frame["feature_version"] = "phase23e_contract_v1"
    frame["pilot_status"] = "contract_only"
    frame["training_allowed"] = False
    return frame[
        [
            "feature_name",
            "feature_family",
            "dtype",
            "definition",
            "source_contract",
            "availability_column",
            "lookback_trading_days",
            "minimum_observations",
            "normalization",
            "imputation_policy",
            "winsorization_policy",
            "feature_version",
            "pilot_status",
            "training_allowed",
        ]
    ]


def build_target_registry(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("forward_1d_total_return", 1, "regression", "security total return"),
        ("forward_5d_total_return", 5, "regression", "security total return"),
        ("forward_20d_total_return", 20, "regression", "security total return"),
        ("forward_63d_total_return", 63, "regression", "security total return"),
        (
            "forward_1d_excess_return_vs_universe",
            1,
            "regression",
            "security return minus same-date eligible-universe return",
        ),
        (
            "forward_5d_excess_return_vs_universe",
            5,
            "regression",
            "security return minus same-date eligible-universe return",
        ),
        (
            "forward_20d_excess_return_vs_universe",
            20,
            "regression",
            "security return minus same-date eligible-universe return",
        ),
        (
            "forward_63d_excess_return_vs_universe",
            63,
            "regression",
            "security return minus same-date eligible-universe return",
        ),
        (
            "forward_20d_positive_alpha_probability",
            20,
            "binary_classification",
            "one when 20-day excess return is positive",
        ),
    ]
    frame = pd.DataFrame(
        rows,
        columns=["target_name", "horizon_trading_days", "target_type", "definition"],
    )
    frame["primary_target"] = frame["target_name"].eq(phase_config["primary_target"])
    frame["predictor_table_allowed"] = False
    frame["availability_rule"] = (
        "available only after target_period_end_date and never during feature construction"
    )
    frame["delisting_return_required"] = True
    frame["target_set_version"] = "phase23e_targets_v1"
    return frame


def build_availability_join_policy() -> pd.DataFrame:
    rows = [
        ("A1", "maximum_family_clock", "Every family records its latest contributing availability timestamp."),
        ("A2", "cutoff_enforcement", "All family availability timestamps must be less than or equal to model_cutoff_timestamp_utc."),
        ("A3", "max_clock_reconciliation", "feature_max_available_timestamp_utc equals the maximum non-null family availability clock."),
        ("A4", "membership_knowledge", "membership_known_timestamp_utc must be less than or equal to the decision cutoff."),
        ("A5", "asof_join_only", "Slow-moving data use backward as-of joins on knowledge timestamps, never period-end or future revisions."),
        ("A6", "same_market_close_alignment", "Market features use observations completed by the decision cutoff with explicit timezone alignment."),
        ("A7", "no_future_metadata", "Future ticker, sector, constituent, event, and corporate-action attributes are prohibited."),
        ("A8", "lineage_reproducibility", "Every row links to immutable source and feature manifests."),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "policy", "requirement"])


def build_missingness_policy() -> pd.DataFrame:
    rows = [
        ("M1", "missing_is_information", "Preserve explicit missing flags and feature age rather than hiding source gaps."),
        ("M2", "no_future_backfill", "Never backward-fill a historical row using a fact, article, classification, or price observed later."),
        ("M3", "no_universal_zero_fill", "Zero is used only when the feature definition makes zero economically meaningful."),
        ("M4", "train_only_imputer", "Any fitted imputer is learned only from the training fold and applied unchanged to validation/test."),
        ("M5", "cross_sectional_imputation", "Same-date median or sector-median imputation may be tested only with missing indicators."),
        ("M6", "coverage_gate", "Rows exceeding registered missingness or stale-data thresholds are training-ineligible."),
        ("M7", "new_listing_warmup", "New listings remain in the universe but unavailable long-lookback features stay missing until warm-up."),
        ("M8", "family_ablation", "Optional feature families may be removed as an ablation; required families may not be silently omitted."),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "policy", "requirement"])


def build_cross_sectional_normalization_policy() -> pd.DataFrame:
    rows = [
        ("N1", "same_date_eligible_universe", "Cross-sectional transforms use only securities eligible at that decision timestamp."),
        ("N2", "no_survivor_reference_set", "Ranks and z-scores never use a modern survivor list as the historical reference set."),
        ("N3", "sector_relative_asof", "Sector-relative transforms use sector_asof, not current sector classifications."),
        ("N4", "point_in_time_winsorization", "Per-date quantile clipping uses only the current eligible cross-section."),
        ("N5", "train_only_global_parameters", "Any global scaler or imputer parameters are fit inside the training fold only."),
        ("N6", "minimum_cross_section", "Cross-sectional features are invalid when the eligible count is below the configured minimum."),
        ("N7", "versioned_transforms", "Transform definitions and parameters are stored with feature_set_version."),
    ]
    return pd.DataFrame(rows, columns=["rule_id", "policy", "requirement"])


def build_training_split_policy(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "policy_id": "S1",
            "policy": "walk_forward_only",
            "requirement": "Training precedes validation, which precedes test and final holdout chronologically.",
            "parameter": "expanding_or_rolling_window",
        },
        {
            "policy_id": "S2",
            "policy": "purged_boundaries",
            "requirement": "Rows whose forward target windows overlap a later fold are removed from the earlier fold boundary.",
            "parameter": phase_config["purge_window_trading_days"],
        },
        {
            "policy_id": "S3",
            "policy": "embargo_after_validation",
            "requirement": "An embargo separates validation/test boundaries to prevent overlapping label information.",
            "parameter": phase_config["embargo_window_trading_days"],
        },
        {
            "policy_id": "S4",
            "policy": "final_holdout_untouched",
            "requirement": "The final holdout is opened only after model family, features, and portfolio rules are frozen.",
            "parameter": "FINAL_HOLDOUT",
        },
        {
            "policy_id": "S5",
            "policy": "cross_section_grouping",
            "requirement": "All securities from one decision timestamp remain in the same split.",
            "parameter": "decision_timestamp_utc",
        },
        {
            "policy_id": "S6",
            "policy": "target_horizon_alignment",
            "requirement": "Purge and embargo windows are at least the maximum registered target horizon.",
            "parameter": phase_config["maximum_target_horizon_trading_days"],
        },
        {
            "policy_id": "S7",
            "policy": "no_random_row_split",
            "requirement": "Random row-level train/test splitting is prohibited.",
            "parameter": "blocked",
        },
    ]
    return pd.DataFrame(rows)


def build_dependency_readiness_matrix() -> pd.DataFrame:
    rows = [
        (
            "point_in_time_universe_membership",
            "Phase23B",
            "membership intervals, permanent IDs, constituent events",
            True,
            False,
            "licensed historical membership sample and approval pending",
        ),
        (
            "stock_price_volume_corporate_actions",
            "Phase23F prerequisite",
            "delisting-aware raw/adjusted prices, volume, splits, dividends",
            True,
            False,
            "individual-stock historical market-data source not yet validated",
        ),
        (
            "fundamental_as_filed_facts",
            "Phase23C",
            "filing events, as-filed facts, amendments, pre-XBRL coverage",
            True,
            False,
            "raw acquisition and mapping pending",
        ),
        (
            "sentiment_news_text",
            "Phase23D",
            "timestamped text events, revisions, entity links, sentiment scores",
            False,
            False,
            "historical licensed feeds and pilot scoring pending",
        ),
        (
            "macro_vintages",
            "existing macro research",
            "release-time and vintage-aware macro features",
            True,
            False,
            "individual-stock panel alignment and completeness audit pending",
        ),
        (
            "cross_asset_market_stress",
            "existing strategy factory",
            "aligned cross-asset prices and market-stress aggregates",
            True,
            False,
            "feature formulas and stock-panel cutoff alignment pending",
        ),
        (
            "event_calendar_and_corporate_actions",
            "Phase23F prerequisite",
            "earnings, guidance, dividends, splits, M&A, delistings",
            True,
            False,
            "point-in-time event source and identity mapping pending",
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "dependency",
            "upstream_phase",
            "required_artifact",
            "required_for_baseline",
            "data_ready_now",
            "blocking_reason",
        ],
    )


def build_validation_plan() -> pd.DataFrame:
    rows = [
        ("V1", "schema completeness", "all required predictor, availability, identity, and lineage columns present"),
        ("V2", "row uniqueness", "panel_row_id and decision/security/universe grain are unique"),
        ("V3", "membership validity", "row belongs to a point-in-time active universe and was knowable by cutoff"),
        ("V4", "availability cutoff", "all predictor-family clocks are on or before model cutoff"),
        ("V5", "maximum clock reconciliation", "feature_max_available_timestamp equals maximum family clock"),
        ("V6", "execution ordering", "execution date is after the signal date under the registered calendar"),
        ("V7", "identity continuity", "ticker/sector changes preserve permanent identifiers"),
        ("V8", "feature manifest coverage", "every predictor column has formula, source, clock, version, and missingness policy"),
        ("V9", "target separation", "forward labels are absent from predictor artifacts"),
        ("V10", "target horizon ordering", "target availability occurs only after its period end"),
        ("V11", "split purity", "one decision timestamp appears in one split only"),
        ("V12", "purge and embargo", "fold boundaries respect maximum target horizon"),
        ("V13", "cross-section size", "normalization occurs only above the minimum eligible count"),
        ("V14", "delisting retention", "failed and removed securities remain in rows and targets"),
        ("V15", "reproducibility", "source snapshot and feature/target versions reproduce identical rows"),
        ("V16", "safety boundary", "no model training, backtest, paper order, live order, or broker integration"),
    ]
    return pd.DataFrame(rows, columns=["test_id", "test", "acceptance_rule"])


def build_phase23f_pilot_plan() -> pd.DataFrame:
    rows = [
        (1, "Select a small point-in-time pilot universe and approved date window", "not_started"),
        (2, "Acquire delisting-aware stock price, volume, split, and dividend samples", "not_started"),
        (3, "Ingest point-in-time membership and permanent security identifiers", "blocked_by_phase23b_acquisition"),
        (4, "Calculate technical, liquidity, cross-asset, and market-stress features", "blocked_by_market_data_acquisition"),
        (5, "Join a small as-filed SEC fundamental sample", "blocked_by_phase23c_acquisition"),
        (6, "Join filing-text and optional news sentiment samples", "blocked_by_phase23d_acquisition"),
        (7, "Build panel and target tables with full timestamp validation", "blocked_by_steps_1_to_6"),
        (8, "Run coverage, missingness, leakage, and reproducibility audits", "blocked_by_panel_build"),
        (9, "Approve or reject readiness for Phase23G baseline ranking", "not_started"),
    ]
    return pd.DataFrame(rows, columns=["priority", "action", "status"])


def build_scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    controls = {
        "data_download_allowed": phase_config["allow_data_download"],
        "panel_build_allowed": phase_config["allow_panel_build"],
        "feature_calculation_allowed": phase_config["allow_feature_calculation"],
        "target_calculation_allowed": phase_config["allow_target_calculation"],
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


def build_empty_feature_panel_template() -> pd.DataFrame:
    schema_columns = build_feature_panel_schema()["column"].tolist()
    feature_columns = build_initial_feature_manifest()["feature_name"].tolist()
    return pd.DataFrame(columns=schema_columns + feature_columns)


def build_empty_target_template() -> pd.DataFrame:
    return pd.DataFrame(columns=TARGET_REQUIRED_COLUMNS)


def build_empty_feature_manifest_template() -> pd.DataFrame:
    return pd.DataFrame(columns=build_feature_manifest_schema()["column"].tolist())


def validate_feature_panel_frame(panel: pd.DataFrame) -> pd.DataFrame:
    missing_columns = sorted(set(FEATURE_PANEL_REQUIRED_COLUMNS) - set(panel.columns))
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

    working = panel.copy()
    required_nonblank = working[FEATURE_PANEL_REQUIRED_COLUMNS].fillna("").astype(str)
    nonblank = bool(required_nonblank.apply(lambda col: col.str.strip().ne("")).all().all())
    rows.append(_gate("required_values_nonblank", nonblank, f"rows={len(working)}"))

    unique_row_id = not bool(working["panel_row_id"].duplicated().any())
    rows.append(_gate("panel_row_ids_unique", unique_row_id, f"rows={len(working)}"))

    unique_grain = not bool(
        working.duplicated(
            ["decision_timestamp_utc", "universe_id", "permanent_security_id"]
        ).any()
    )
    rows.append(_gate("decision_security_universe_grain_unique", unique_grain, "row grain"))

    universe_valid = bool(working["universe_id"].isin(VALID_UNIVERSES).all())
    rows.append(_gate("universe_ids_valid", universe_valid, "target universes"))

    split_valid = bool(working["split_label"].isin(VALID_SPLIT_LABELS).all())
    rows.append(_gate("split_labels_valid", split_valid, "registered split labels"))

    cutoff = pd.to_datetime(working["model_cutoff_timestamp_utc"], utc=True, errors="coerce")
    decision = pd.to_datetime(working["decision_timestamp_utc"], utc=True, errors="coerce")
    membership_known = pd.to_datetime(
        working["membership_known_timestamp_utc"], utc=True, errors="coerce"
    )
    family_clocks = working[FEATURE_AVAILABILITY_COLUMNS].apply(
        pd.to_datetime, utc=True, errors="coerce"
    )
    feature_max = pd.to_datetime(
        working["feature_max_available_timestamp_utc"], utc=True, errors="coerce"
    )
    timestamps_parse = bool(
        cutoff.notna().all()
        and decision.notna().all()
        and membership_known.notna().all()
        and family_clocks.notna().all().all()
        and feature_max.notna().all()
    )
    rows.append(_gate("timestamps_parse", timestamps_parse, f"rows={len(working)}"))

    if timestamps_parse:
        clocks_before_cutoff = bool(family_clocks.le(cutoff, axis=0).all().all())
        membership_before_cutoff = bool((membership_known <= cutoff).all())
        decision_not_after_cutoff = bool((decision <= cutoff).all())
        family_max = family_clocks.max(axis=1)
        max_reconciles = bool((family_max == feature_max).all())
    else:
        clocks_before_cutoff = False
        membership_before_cutoff = False
        decision_not_after_cutoff = False
        max_reconciles = False
    rows.append(
        _gate(
            "feature_availability_not_after_cutoff",
            clocks_before_cutoff,
            "all family clocks <= model cutoff",
        )
    )
    rows.append(
        _gate(
            "membership_known_not_after_cutoff",
            membership_before_cutoff,
            "membership knowledge ordering",
        )
    )
    rows.append(
        _gate(
            "decision_not_after_model_cutoff",
            decision_not_after_cutoff,
            "decision clock ordering",
        )
    )
    rows.append(
        _gate(
            "feature_max_clock_reconciles",
            max_reconciles,
            "maximum family availability clock",
        )
    )

    signal_date = pd.to_datetime(working["signal_date"], errors="coerce")
    execution_date = pd.to_datetime(working["execution_date"], errors="coerce")
    execution_after_signal = bool(
        signal_date.notna().all()
        and execution_date.notna().all()
        and (execution_date > signal_date).all()
    )
    rows.append(
        _gate(
            "execution_after_signal_date",
            execution_after_signal,
            "next-trading-day execution ordering",
        )
    )

    membership_active = working["membership_active"].map(
        lambda value: str(value).strip().lower() in {"true", "1", "yes"}
    )
    rows.append(
        _gate(
            "membership_active_for_all_rows",
            bool(membership_active.all()),
            "inactive rows excluded from model panel",
        )
    )

    identifiers_present = bool(
        working["permanent_security_id"].astype(str).str.strip().ne("").all()
        and working["permanent_company_id"].astype(str).str.strip().ne("").all()
    )
    rows.append(
        _gate(
            "permanent_identifiers_present",
            identifiers_present,
            "security and company IDs",
        )
    )

    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def validate_target_frame(
    targets: pd.DataFrame, *, panel: pd.DataFrame | None = None
) -> pd.DataFrame:
    missing_columns = sorted(set(TARGET_REQUIRED_COLUMNS) - set(targets.columns))
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

    working = targets.copy()
    unique_targets = not bool(
        working.duplicated(["panel_row_id", "target_name"]).any()
    )
    rows.append(_gate("panel_target_pairs_unique", unique_targets, f"rows={len(working)}"))

    horizons = pd.to_numeric(working["target_horizon_trading_days"], errors="coerce")
    positive_horizons = bool(horizons.notna().all() and (horizons > 0).all())
    rows.append(_gate("target_horizons_positive", positive_horizons, "trading days"))

    start = pd.to_datetime(working["target_period_start_date"], errors="coerce")
    end = pd.to_datetime(working["target_period_end_date"], errors="coerce")
    available = pd.to_datetime(
        working["target_available_timestamp_utc"], utc=True, errors="coerce"
    )
    dates_parse = bool(start.notna().all() and end.notna().all() and available.notna().all())
    rows.append(_gate("target_dates_parse", dates_parse, f"rows={len(working)}"))

    if dates_parse:
        target_period_valid = bool((end >= start).all())
        end_utc = pd.to_datetime(end.dt.strftime("%Y-%m-%d") + "T23:59:59Z", utc=True)
        availability_after_end = bool((available > end_utc).all())
    else:
        target_period_valid = False
        availability_after_end = False
    rows.append(_gate("target_period_ordering_valid", target_period_valid, "start <= end"))
    rows.append(
        _gate(
            "target_available_only_after_period_end",
            availability_after_end,
            "labels remain unavailable during prediction",
        )
    )

    if panel is None or panel.empty:
        panel_ids_valid = True
        target_after_decision = True
    elif "panel_row_id" not in panel.columns or "decision_timestamp_utc" not in panel.columns:
        panel_ids_valid = False
        target_after_decision = False
    else:
        panel_lookup = panel[["panel_row_id", "decision_timestamp_utc"]].drop_duplicates()
        merged = working.merge(panel_lookup, on="panel_row_id", how="left")
        panel_ids_valid = bool(merged["decision_timestamp_utc"].notna().all())
        decision = pd.to_datetime(
            merged["decision_timestamp_utc"], utc=True, errors="coerce"
        )
        target_after_decision = bool(
            panel_ids_valid and decision.notna().all() and (available > decision).all()
        )
    rows.append(_gate("target_panel_ids_exist", panel_ids_valid, "panel row lineage"))
    rows.append(
        _gate(
            "target_available_after_decision",
            target_after_decision,
            "target cannot be predictor-time information",
        )
    )

    report = pd.DataFrame(rows)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def build_gate_report(
    *,
    phase_config: dict[str, Any],
    panel_grain_contract: pd.DataFrame,
    feature_panel_schema: pd.DataFrame,
    feature_manifest_schema: pd.DataFrame,
    feature_family_contract: pd.DataFrame,
    initial_feature_manifest: pd.DataFrame,
    target_registry: pd.DataFrame,
    availability_policy: pd.DataFrame,
    missingness_policy: pd.DataFrame,
    normalization_policy: pd.DataFrame,
    split_policy: pd.DataFrame,
    dependency_matrix: pd.DataFrame,
    validation_plan: pd.DataFrame,
    pilot_plan: pd.DataFrame,
    scope_boundary: pd.DataFrame,
) -> pd.DataFrame:
    schema_columns = set(feature_panel_schema["column"])
    manifest_families = set(initial_feature_manifest["feature_family"])
    registered_targets = set(target_registry["target_name"])
    gates = [
        _gate("phase_enabled", bool(phase_config["enabled"]), "Phase23E explicitly enabled"),
        _gate("panel_grain_contract_complete", len(panel_grain_contract) >= 6, f"rules={len(panel_grain_contract)}"),
        _gate("panel_schema_complete", set(FEATURE_PANEL_REQUIRED_COLUMNS).issubset(schema_columns), f"columns={len(schema_columns)}"),
        _gate("feature_manifest_schema_complete", len(feature_manifest_schema) >= 14, f"columns={len(feature_manifest_schema)}"),
        _gate("all_required_feature_families_registered", VALID_FEATURE_FAMILIES.issubset(manifest_families), ";".join(sorted(manifest_families))),
        _gate("primary_target_registered", phase_config["primary_target"] in registered_targets, phase_config["primary_target"]),
        _gate("target_table_separated", not bool(target_registry["predictor_table_allowed"].any()), "targets prohibited from predictor table"),
        _gate("availability_policy_complete", len(availability_policy) >= 8, f"rules={len(availability_policy)}"),
        _gate("missingness_policy_complete", len(missingness_policy) >= 8, f"rules={len(missingness_policy)}"),
        _gate("normalization_policy_complete", len(normalization_policy) >= 7, f"rules={len(normalization_policy)}"),
        _gate("purge_and_embargo_cover_max_horizon", int(phase_config["purge_window_trading_days"]) >= int(phase_config["maximum_target_horizon_trading_days"]) and int(phase_config["embargo_window_trading_days"]) >= int(phase_config["maximum_target_horizon_trading_days"]), f"max_horizon={phase_config['maximum_target_horizon_trading_days']}"),
        _gate("dependency_matrix_fail_closed", not bool(dependency_matrix["data_ready_now"].any()), "upstream data acquisition remains pending"),
        _gate("validation_plan_complete", len(validation_plan) >= 16, f"tests={len(validation_plan)}"),
        _gate("phase23f_pilot_plan_defined", len(pilot_plan) >= 9, f"actions={len(pilot_plan)}"),
        _gate("research_only_boundary_enforced", bool(scope_boundary["passed"].all()), f"controls={len(scope_boundary)}"),
        _gate("family_contract_matches_manifest", set(feature_family_contract["feature_family"]) == manifest_families, "family registry alignment"),
    ]
    report = pd.DataFrame(gates)
    report["all_gates_passed"] = bool(report["passed"].all())
    return report


def build_summary(
    *,
    phase_config: dict[str, Any],
    gate_report: pd.DataFrame,
    dependency_matrix: pd.DataFrame,
    initial_feature_manifest: pd.DataFrame,
    target_registry: pd.DataFrame,
) -> pd.DataFrame:
    execution_passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    data_ready = bool(dependency_matrix["data_ready_now"].all())
    return pd.DataFrame(
        [
            {
                "phase": "Phase 23E",
                "phase23e_decision": (
                    phase_config["phase_decision"]
                    if execution_passed and not data_ready
                    else "phase23e_feature_panel_contract_blocked"
                    if not execution_passed
                    else "phase23e_feature_panel_data_ready"
                ),
                "phase_execution_gates_passed": execution_passed,
                "all_gates_passed": execution_passed,
                "feature_panel_contract_ready": execution_passed,
                "feature_panel_data_ready": data_ready,
                "registered_feature_count": int(len(initial_feature_manifest)),
                "registered_feature_family_count": int(initial_feature_manifest["feature_family"].nunique()),
                "registered_target_count": int(len(target_registry)),
                "required_dependency_count": int(dependency_matrix["required_for_baseline"].sum()),
                "ready_dependency_count": int(dependency_matrix["data_ready_now"].sum()),
                "required_start_date": phase_config["required_start_date"],
                "required_end_date": phase_config["required_end_date"],
                "decision_cadence": phase_config["decision_cadence"],
                "execution_policy": phase_config["execution_policy"],
                "primary_target": phase_config["primary_target"],
                "maximum_target_horizon_trading_days": phase_config[
                    "maximum_target_horizon_trading_days"
                ],
                "purge_window_trading_days": phase_config["purge_window_trading_days"],
                "embargo_window_trading_days": phase_config[
                    "embargo_window_trading_days"
                ],
                "panel_build_allowed": False,
                "feature_calculation_allowed": False,
                "target_calculation_allowed": False,
                "model_training_allowed": False,
                "backtest_allowed": False,
                "next_phase": (
                    "Phase 23F — pilot point-in-time individual-stock feature calculation; "
                    "Phase23B, Phase23C, Phase23D, and stock market-data acquisition remain "
                    "blocking"
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
                    "Phase 23E passed as a combined feature-panel contract. The row grain, "
                    "availability clocks, predictor/target separation, missingness rules, "
                    "normalization rules, and purged walk-forward split policy are defined. "
                    "No stock-level panel is approved yet."
                    if bool(row["phase_execution_gates_passed"])
                    else "Phase 23E failed: the combined feature-panel contract is incomplete."
                ),
                "feature_panel_contract_ready": bool(
                    row["feature_panel_contract_ready"]
                ),
                "feature_panel_data_ready": bool(row["feature_panel_data_ready"]),
                "allowed_next_step": (
                    "acquire approved pilot inputs and build a small timestamp-validated panel"
                ),
                "blocked_next_step": (
                    "full panel, model training, stock-selection backtest, paper orders, live "
                    "trading, real money, broker API"
                ),
            }
        ]
    )


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    titles = {
        "panel_grain_contract": "Panel Grain Contract",
        "feature_panel_schema": "Feature Panel Schema",
        "feature_manifest_schema": "Feature Manifest Schema",
        "feature_family_contract": "Feature Family Contract",
        "initial_feature_manifest": "Initial Feature Manifest",
        "target_registry": "Target Registry",
        "availability_join_policy": "Availability and Join Policy",
        "missingness_policy": "Missingness Policy",
        "cross_sectional_normalization_policy": "Cross-Sectional Normalization Policy",
        "training_split_policy": "Training Split Policy",
        "dependency_readiness_matrix": "Dependency Readiness Matrix",
        "validation_plan": "Validation Plan",
        "phase23f_pilot_plan": "Phase 23F Pilot Plan",
        "scope_boundary": "Phase Boundary",
        "gate_report": "Gate Report",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    lines = [
        "# Phase 23E — Combined Individual-Stock Feature Panel Contract",
        "",
        (
            "This phase defines the leak-safe stock-level feature and target tables consumed "
            "by future ranking models. It does not download data, build the panel, calculate "
            "features or targets, train models, backtest stock selection, or create orders."
        ),
        "",
    ]
    for key, title in titles.items():
        lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23e_combined_feature_panel_contract(
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

    panel_grain_contract = build_panel_grain_contract()
    feature_panel_schema = build_feature_panel_schema()
    feature_manifest_schema = build_feature_manifest_schema()
    feature_family_contract = build_feature_family_contract()
    initial_feature_manifest = build_initial_feature_manifest()
    target_registry = build_target_registry(phase_config)
    availability_policy = build_availability_join_policy()
    missingness_policy = build_missingness_policy()
    normalization_policy = build_cross_sectional_normalization_policy()
    split_policy = build_training_split_policy(phase_config)
    dependency_matrix = build_dependency_readiness_matrix()
    validation_plan = build_validation_plan()
    pilot_plan = build_phase23f_pilot_plan()
    scope_boundary = build_scope_boundary(phase_config)
    gate_report = build_gate_report(
        phase_config=phase_config,
        panel_grain_contract=panel_grain_contract,
        feature_panel_schema=feature_panel_schema,
        feature_manifest_schema=feature_manifest_schema,
        feature_family_contract=feature_family_contract,
        initial_feature_manifest=initial_feature_manifest,
        target_registry=target_registry,
        availability_policy=availability_policy,
        missingness_policy=missingness_policy,
        normalization_policy=normalization_policy,
        split_policy=split_policy,
        dependency_matrix=dependency_matrix,
        validation_plan=validation_plan,
        pilot_plan=pilot_plan,
        scope_boundary=scope_boundary,
    )
    summary = build_summary(
        phase_config=phase_config,
        gate_report=gate_report,
        dependency_matrix=dependency_matrix,
        initial_feature_manifest=initial_feature_manifest,
        target_registry=target_registry,
    )
    conclusion = build_conclusion(summary)

    outputs = {
        "panel_grain_contract": panel_grain_contract,
        "feature_panel_schema": feature_panel_schema,
        "feature_manifest_schema": feature_manifest_schema,
        "feature_family_contract": feature_family_contract,
        "initial_feature_manifest": initial_feature_manifest,
        "target_registry": target_registry,
        "availability_join_policy": availability_policy,
        "missingness_policy": missingness_policy,
        "cross_sectional_normalization_policy": normalization_policy,
        "training_split_policy": split_policy,
        "dependency_readiness_matrix": dependency_matrix,
        "validation_plan": validation_plan,
        "phase23f_pilot_plan": pilot_plan,
        "scope_boundary": scope_boundary,
        "gate_report": gate_report,
        "summary": summary,
        "conclusion": conclusion,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23e_{name}.csv", index=False)

    build_empty_feature_panel_template().to_csv(
        output_dir / "phase23e_feature_panel_import_template.csv", index=False
    )
    build_empty_target_template().to_csv(
        output_dir / "phase23e_target_import_template.csv", index=False
    )
    build_empty_feature_manifest_template().to_csv(
        output_dir / "phase23e_feature_manifest_import_template.csv", index=False
    )
    _write_markdown(outputs, output_dir / "phase23e_combined_feature_panel_contract.md")

    dashboard_path = _resolve_configured_path(
        configured_path=phase_config["dashboard_status_path"], reports_dir=reports_dir
    )
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23e_combined_feature_panel_contract_status_written"
    dashboard["notes"] = (
        "The leak-safe panel contract is ready; approved universe, market, fundamental, text, "
        "macro, and event data remain required before a pilot panel or model can be built."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23E combined individual-stock feature panel contract reports.")
    return outputs
