from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PHASE23A_CONFIG: dict[str, Any] = {
    "enabled": False,
    "output_dir": "reports/individual_equity_decision_system/phase23a_architecture",
    "dashboard_status_path": (
        "reports/paper_trading/dashboard/"
        "phase23a_individual_equity_decision_architecture_status.csv"
    ),
    "phase_role": (
        "Individual-equity autonomous decision architecture and point-in-time "
        "research contract only"
    ),
    "phase_decision": "phase23a_architecture_ready_for_point_in_time_source_audits",
    "ultimate_goal": (
        "Build a leak-safe autonomous research and paper-trading system that can "
        "select individual equities from point-in-time S&P 500 and Nasdaq-100 "
        "universes using technical, fundamental, sentiment, macro, cross-asset, "
        "market-stress, and risk information."
    ),
    "primary_universes": ["SP500_POINT_IN_TIME", "NASDAQ100_POINT_IN_TIME"],
    "decision_cadence": "weekly_after_close",
    "monitoring_cadence": "daily_after_close",
    "execution_policy": "next_trading_day_after_signal",
    "primary_target": "forward_20d_excess_return_vs_universe",
    "secondary_targets": [
        "forward_1d_excess_return_vs_universe",
        "forward_5d_excess_return_vs_universe",
        "forward_63d_excess_return_vs_universe",
        "forward_20d_positive_alpha_probability",
    ],
    "initial_model_family": "interpretable_cross_sectional_ranking_baseline",
    "future_model_families": [
        "regularized_linear_ranker",
        "gradient_boosted_tree_ranker",
        "probability_calibrated_ensemble",
    ],
    "initial_portfolio_size": 20,
    "max_single_stock_weight": 0.05,
    "max_sector_weight": 0.25,
    "max_turnover_per_rebalance": 0.30,
    "minimum_cash_weight": 0.00,
    "maximum_cash_weight": 0.50,
    "allow_data_download": False,
    "allow_feature_calculation": False,
    "allow_model_training": False,
    "allow_backtest": False,
    "allow_paper_orders": False,
    "allow_live_trading": False,
    "allow_real_money": False,
    "allow_broker_api": False,
    "allow_promotion": False,
}


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
        DEFAULT_PHASE23A_CONFIG,
        config.get("phase23a_individual_equity_decision_architecture", {}),
    )


def _join(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, (list, tuple, set)):
        return "; ".join(str(value) for value in values)
    return str(values)


def _gate(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "result": "Passed" if passed else "Failed",
        "detail": detail,
    }


def build_scope_and_objective(phase_config: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "phase": "Phase 23A",
                "phase_role": phase_config["phase_role"],
                "ultimate_goal": phase_config["ultimate_goal"],
                "primary_universes": _join(phase_config["primary_universes"]),
                "decision_cadence": phase_config["decision_cadence"],
                "monitoring_cadence": phase_config["monitoring_cadence"],
                "execution_policy": phase_config["execution_policy"],
                "current_scope": "architecture_and_contract_only",
                "individual_stock_selection_in_scope_eventually": True,
                "autonomous_target_weight_generation_in_scope_eventually": True,
                "current_model_trained": False,
                "current_individual_stock_backtest_run": False,
            }
        ]
    )


def build_point_in_time_universe_contract() -> pd.DataFrame:
    rows = [
        {
            "contract_id": "U1",
            "requirement": "Historical membership must be point-in-time",
            "required": True,
            "reason": "Prevents survivorship bias from using today's constituents historically",
            "blocked_shortcut": "current_constituents_backfilled_through_history",
        },
        {
            "contract_id": "U2",
            "requirement": "Membership effective dates and announcement dates stored separately",
            "required": True,
            "reason": "Prevents trading on index changes before they were public/effective",
            "blocked_shortcut": "membership_without_effective_timestamp",
        },
        {
            "contract_id": "U3",
            "requirement": "Delisted, acquired, bankrupt, and renamed securities retained",
            "required": True,
            "reason": "Preserves realistic historical opportunity and failure sets",
            "blocked_shortcut": "survivors_only_price_panel",
        },
        {
            "contract_id": "U4",
            "requirement": "Ticker-to-permanent-security identifier mapping required",
            "required": True,
            "reason": "Ticker symbols can change and be reused",
            "blocked_shortcut": "ticker_as_permanent_identity",
        },
        {
            "contract_id": "U5",
            "requirement": "Corporate actions and adjusted/raw prices retained",
            "required": True,
            "reason": "Signals, execution prices, splits, dividends, and returns need distinct handling",
            "blocked_shortcut": "single_unqualified_price_series",
        },
        {
            "contract_id": "U6",
            "requirement": "S&P 500 and Nasdaq-100 overlap deduplicated by permanent identifier",
            "required": True,
            "reason": "Avoids duplicate securities and accidental double weight",
            "blocked_shortcut": "duplicate_ticker_rows_across_universes",
        },
    ]
    return pd.DataFrame(rows)


def build_feature_family_registry() -> pd.DataFrame:
    rows = [
        {
            "family": "technical",
            "examples": "momentum; trend; volatility; volume; gaps; liquidity; breadth",
            "intended_role": "timing_and_cross_sectional_strength",
            "point_in_time_rule": "computed only from data available by signal cutoff",
            "initial_status": "source_and_formula_audit_required",
        },
        {
            "family": "fundamental",
            "examples": "valuation; profitability; quality; growth; leverage; revisions",
            "intended_role": "business_quality_and_expected_return_context",
            "point_in_time_rule": "filing/publication timestamp plus conservative availability lag",
            "initial_status": "dedicated_source_and_restated_data_audit_required",
        },
        {
            "family": "sentiment",
            "examples": "news; filings tone; analyst revisions; earnings-call tone; options positioning",
            "intended_role": "expectation_change_and_narrative_context",
            "point_in_time_rule": "source timestamp, deduplication, entity linking, and cutoff enforcement",
            "initial_status": "dedicated_source_noise_and_leakage_audit_required",
        },
        {
            "family": "macro",
            "examples": "rates; inflation; labour; growth; liquidity; credit conditions",
            "intended_role": "market_regime_and_discount_rate_context",
            "point_in_time_rule": "release timestamp and vintage-aware values",
            "initial_status": "existing_macro_contract_reuse_and_extension_audit",
        },
        {
            "family": "cross_asset",
            "examples": "dollar; commodities; bonds; credit; volatility; crypto",
            "intended_role": "risk_appetite_and_transmission_context",
            "point_in_time_rule": "market-close alignment and timezone normalization",
            "initial_status": "source_alignment_audit_required",
        },
        {
            "family": "market_stress",
            "examples": "dispersion; correlation; breadth; volatility term structure; liquidity stress",
            "intended_role": "risk_budget_and_trade_suppression",
            "point_in_time_rule": "available-by-cutoff aggregation only",
            "initial_status": "feature_contract_required",
        },
        {
            "family": "event_and_corporate_action",
            "examples": "earnings dates; guidance; dividends; splits; M&A; index events",
            "intended_role": "event_risk_and_execution_guard",
            "point_in_time_rule": "announcement timestamp distinct from event/effective date",
            "initial_status": "event_calendar_contract_required",
        },
    ]
    return pd.DataFrame(rows)


def build_target_and_decision_contract(phase_config: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "primary_target": phase_config["primary_target"],
                "secondary_targets": _join(phase_config["secondary_targets"]),
                "target_type": "cross_sectional_forward_excess_return_and_probability",
                "decision_unit": "security_date",
                "signal_cutoff": "after_market_close",
                "execution_date": phase_config["execution_policy"],
                "ranking_direction": "higher_score_higher_expected_alpha",
                "label_purge_required": True,
                "embargo_required": True,
                "transaction_cost_aware": True,
                "reason_for_20d_primary": (
                    "reduces noise and turnover relative to a next-day-only target while "
                    "remaining responsive enough for active allocation"
                ),
            }
        ]
    )


def build_model_architecture(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "layer_order": 1,
            "layer": "point_in_time_eligibility",
            "responsibility": "membership, tradability, price, liquidity, and data-availability checks",
            "output": "eligible_security_flag",
            "autonomous": True,
            "hard_guardrail": True,
        },
        {
            "layer_order": 2,
            "layer": "feature_panel",
            "responsibility": "assemble lagged technical, fundamental, sentiment, macro, cross-asset, and stress features",
            "output": "security_date_feature_vector",
            "autonomous": True,
            "hard_guardrail": True,
        },
        {
            "layer_order": 3,
            "layer": "cross_sectional_alpha_model",
            "responsibility": "predict relative return and positive-alpha probability",
            "output": "expected_alpha_score_and_confidence",
            "autonomous": True,
            "hard_guardrail": False,
        },
        {
            "layer_order": 4,
            "layer": "ensemble_and_calibration",
            "responsibility": "combine interpretable baseline and validated nonlinear models",
            "output": "calibrated_composite_rank",
            "autonomous": True,
            "hard_guardrail": False,
        },
        {
            "layer_order": 5,
            "layer": "portfolio_constructor",
            "responsibility": "convert ranks into bounded target weights",
            "output": "target_weight_by_security",
            "autonomous": True,
            "hard_guardrail": True,
        },
        {
            "layer_order": 6,
            "layer": "risk_and_execution_guard",
            "responsibility": "sector, stock, liquidity, turnover, event, drawdown, and stale-data checks",
            "output": "approved_paper_order_or_block_reason",
            "autonomous": True,
            "hard_guardrail": True,
        },
        {
            "layer_order": 7,
            "layer": "audit_and_monitoring",
            "responsibility": "decision explanations, drift, attribution, and stop conditions",
            "output": "immutable_decision_and_model_audit",
            "autonomous": True,
            "hard_guardrail": True,
        },
    ]
    frame = pd.DataFrame(rows)
    frame["initial_model_family"] = phase_config["initial_model_family"]
    frame["future_model_families"] = _join(phase_config["future_model_families"])
    return frame


def build_portfolio_construction_contract(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "constraint": "portfolio_size",
            "value": phase_config["initial_portfolio_size"],
            "unit": "securities",
            "purpose": "initial sparse, auditable long-only portfolio",
        },
        {
            "constraint": "max_single_stock_weight",
            "value": phase_config["max_single_stock_weight"],
            "unit": "fraction",
            "purpose": "idiosyncratic risk control",
        },
        {
            "constraint": "max_sector_weight",
            "value": phase_config["max_sector_weight"],
            "unit": "fraction",
            "purpose": "sector concentration control",
        },
        {
            "constraint": "max_turnover_per_rebalance",
            "value": phase_config["max_turnover_per_rebalance"],
            "unit": "fraction",
            "purpose": "cost and churn control",
        },
        {
            "constraint": "minimum_cash_weight",
            "value": phase_config["minimum_cash_weight"],
            "unit": "fraction",
            "purpose": "lower bound only; not forced defensive allocation",
        },
        {
            "constraint": "maximum_cash_weight",
            "value": phase_config["maximum_cash_weight"],
            "unit": "fraction",
            "purpose": "allows risk-off state without unrestricted de-risking",
        },
        {
            "constraint": "long_only_initially",
            "value": 1,
            "unit": "boolean",
            "purpose": "reduces borrow, leverage, and execution complexity",
        },
        {
            "constraint": "benchmark_comparisons",
            "value": "SPY; QQQ; equal_weight_universe; sector_neutral_baseline",
            "unit": "benchmarks",
            "purpose": "separates stock-selection alpha from market and sector beta",
        },
    ]
    return pd.DataFrame(rows)


def build_risk_and_execution_contract(phase_config: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("signal_execution_separation", "signal after close; execute next trading day"),
        ("stale_data_block", "block security or full run when required data is stale"),
        ("earnings_event_guard", "explicit policy for positions around earnings events"),
        ("liquidity_guard", "minimum price, dollar volume, and tradable history"),
        ("corporate_action_guard", "split, merger, delisting, and symbol-change handling"),
        ("turnover_guard", "trade only when score improvement exceeds cost-aware buffer"),
        ("portfolio_drawdown_guard", "reduce risk or halt new entries at preregistered thresholds"),
        ("model_drift_guard", "halt when feature, prediction, calibration, or residual drift breaches limits"),
        ("missing_family_policy", "no silent imputation across unavailable fundamental or sentiment history"),
        ("paper_before_live", "shadow decisions then manual paper then automated paper before any live consideration"),
    ]
    frame = pd.DataFrame(rows, columns=["control", "policy"])
    frame["decision_cadence"] = phase_config["decision_cadence"]
    frame["monitoring_cadence"] = phase_config["monitoring_cadence"]
    frame["live_trading_allowed"] = False
    frame["real_money_allowed"] = False
    frame["broker_api_integration_allowed"] = False
    return frame


def build_validation_plan() -> pd.DataFrame:
    rows = [
        (1, "data_contract", "point-in-time universe, timestamps, lags, delistings, and corporate actions"),
        (2, "feature_quality", "coverage, staleness, missingness, outliers, and leakage"),
        (3, "walk_forward_prediction", "purged expanding/rolling validation with untouched holdout"),
        (4, "cross_sectional_skill", "rank IC, top-minus-bottom spread, hit rate, calibration, and stability"),
        (5, "portfolio_backtest", "cost-aware next-day execution with delistings and realistic liquidity"),
        (6, "robustness", "subperiods, sectors, universes, costs, turnover, and parameter neighborhoods"),
        (7, "ablation", "technical-only, fundamental-only, sentiment-only, macro-only, and combined"),
        (8, "paper_shadow", "daily autonomous decisions without orders"),
        (9, "manual_paper", "human-approved simulated fills and reconciliation"),
        (10, "automated_paper", "broker sandbox only after manual-paper gates"),
    ]
    frame = pd.DataFrame(rows, columns=["stage_order", "stage", "required_evidence"])
    frame["promotion_allowed_at_stage"] = False
    return frame


def build_autonomous_decision_schema() -> pd.DataFrame:
    columns = [
        ("decision_run_id", "string", "unique immutable run identifier"),
        ("model_version", "string", "registered model and feature-contract version"),
        ("as_of_timestamp_utc", "timestamp", "latest information cutoff"),
        ("signal_date", "date", "date on which features and predictions are formed"),
        ("execution_date", "date", "next eligible trading date"),
        ("permanent_security_id", "string", "stable security identity"),
        ("ticker", "string", "display/execution symbol valid on signal date"),
        ("universe_membership", "string", "point-in-time eligible universe"),
        ("sector", "string", "point-in-time sector classification"),
        ("eligibility_passed", "boolean", "all data and tradability gates passed"),
        ("technical_score", "float", "technical family contribution"),
        ("fundamental_score", "float", "fundamental family contribution"),
        ("sentiment_score", "float", "sentiment family contribution"),
        ("macro_context_score", "float", "macro context contribution"),
        ("cross_asset_score", "float", "cross-asset contribution"),
        ("market_stress_score", "float", "risk-state contribution"),
        ("predicted_excess_return_20d", "float", "primary continuous prediction"),
        ("positive_alpha_probability_20d", "float", "calibrated probability"),
        ("prediction_confidence", "float", "model confidence after calibration"),
        ("cross_sectional_rank", "integer", "rank within eligible universe"),
        ("current_weight", "float", "pre-trade portfolio weight"),
        ("raw_target_weight", "float", "model-implied unconstrained weight"),
        ("approved_target_weight", "float", "post-guardrail target weight"),
        ("trade_action", "string", "BUY, SELL, HOLD, BLOCK, or CASH"),
        ("expected_turnover", "float", "absolute proposed weight change"),
        ("estimated_cost_bps", "float", "estimated execution cost"),
        ("decision_reason", "string", "human-readable top drivers and blockers"),
        ("blocking_reasons", "string", "hard guard failures"),
        ("paper_order_allowed", "boolean", "false until later paper gates"),
        ("live_trading_allowed", "boolean", "must remain false"),
        ("real_money_allowed", "boolean", "must remain false"),
        ("broker_api_integration_allowed", "boolean", "must remain false"),
        ("promotion_allowed", "boolean", "must remain false"),
    ]
    return pd.DataFrame(columns, columns=["column", "dtype", "description"])


def build_research_roadmap() -> pd.DataFrame:
    rows = [
        ("23A", "Architecture and point-in-time contract", "completed_by_this_phase"),
        ("23B", "Point-in-time S&P 500/Nasdaq-100 universe source audit", "next"),
        ("23C", "Fundamental data source, filing-lag, and restatement audit", "planned"),
        ("23D", "Sentiment/news source, timestamp, entity-linking, and noise audit", "planned"),
        ("23E", "Combined security-date feature panel schema and availability contract", "planned"),
        ("23F", "Pilot point-in-time universe and feature calculation", "planned"),
        ("23G", "Interpretable cross-sectional ranking baseline", "planned"),
        ("23H", "Walk-forward nonlinear ranker and calibrated ensemble", "planned"),
        ("23I", "Cost-aware portfolio construction and backtest", "planned"),
        ("23J", "Robustness, ablation, and untouched holdout decision", "planned"),
        ("23K", "Autonomous shadow decisions", "planned"),
        ("23L", "Manual individual-equity paper workflow", "planned"),
        ("23M", "Automated broker-sandbox paper execution", "future_gated"),
    ]
    return pd.DataFrame(rows, columns=["phase", "objective", "status"])


def build_scope_boundary(phase_config: dict[str, Any]) -> pd.DataFrame:
    controls = {
        "data_download_allowed": phase_config["allow_data_download"],
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
                "control": key,
                "allowed": bool(value),
                "required_state": False,
                "passed": not bool(value),
            }
            for key, value in controls.items()
        ]
    )


def build_gate_report(
    *,
    phase_config: dict[str, Any],
    universe_contract: pd.DataFrame,
    feature_registry: pd.DataFrame,
    model_architecture: pd.DataFrame,
    portfolio_contract: pd.DataFrame,
    validation_plan: pd.DataFrame,
    decision_schema: pd.DataFrame,
    roadmap: pd.DataFrame,
    scope_boundary: pd.DataFrame,
) -> pd.DataFrame:
    required_families = {
        "technical",
        "fundamental",
        "sentiment",
        "macro",
        "cross_asset",
        "market_stress",
    }
    gates = [
        _gate(
            "phase_enabled",
            bool(phase_config["enabled"]),
            "Phase23A must be explicitly enabled",
        ),
        _gate(
            "point_in_time_universe_contract_complete",
            len(universe_contract) >= 6 and bool(universe_contract["required"].all()),
            f"rows={len(universe_contract)}",
        ),
        _gate(
            "required_feature_families_present",
            required_families.issubset(set(feature_registry["family"])),
            _join(sorted(set(feature_registry["family"]))),
        ),
        _gate(
            "autonomous_layers_defined",
            len(model_architecture) >= 7
            and {"cross_sectional_alpha_model", "portfolio_constructor", "risk_and_execution_guard"}.issubset(
                set(model_architecture["layer"])
            ),
            f"layers={len(model_architecture)}",
        ),
        _gate(
            "portfolio_constraints_defined",
            len(portfolio_contract) >= 8,
            f"constraints={len(portfolio_contract)}",
        ),
        _gate(
            "validation_stages_defined",
            len(validation_plan) >= 10,
            f"stages={len(validation_plan)}",
        ),
        _gate(
            "decision_audit_schema_complete",
            len(decision_schema) >= 30
            and {"predicted_excess_return_20d", "approved_target_weight", "trade_action", "blocking_reasons"}.issubset(
                set(decision_schema["column"])
            ),
            f"columns={len(decision_schema)}",
        ),
        _gate(
            "next_phase_is_universe_source_audit",
            bool(
                (
                    (roadmap["phase"] == "23B")
                    & (roadmap["status"] == "next")
                ).any()
            ),
            "Phase23B point-in-time universe source audit",
        ),
        _gate(
            "research_only_boundary_enforced",
            bool(scope_boundary["passed"].all()),
            f"controls={len(scope_boundary)}",
        ),
    ]
    frame = pd.DataFrame(gates)
    frame["all_gates_passed"] = bool(frame["passed"].all())
    return frame


def build_summary(
    *, phase_config: dict[str, Any], gate_report: pd.DataFrame
) -> pd.DataFrame:
    passed = bool(gate_report["passed"].all()) if not gate_report.empty else False
    return pd.DataFrame(
        [
            {
                "phase": "Phase 23A",
                "phase23a_decision": (
                    phase_config["phase_decision"]
                    if passed
                    else "phase23a_architecture_blocked"
                ),
                "all_gates_passed": passed,
                "individual_stock_selection_eventual_scope": True,
                "autonomous_decision_generation_eventual_scope": True,
                "model_trained_in_phase23a": False,
                "backtest_run_in_phase23a": False,
                "next_phase": "Phase 23B — point-in-time universe source audit",
                "paper_only": True,
                "promotion_allowed": False,
                "live_trading_allowed": False,
                "real_money_allowed": False,
                "broker_api_integration_allowed": False,
            }
        ]
    )


def build_conclusion(summary: pd.DataFrame) -> pd.DataFrame:
    passed = bool(summary.iloc[0]["all_gates_passed"])
    return pd.DataFrame(
        [
            {
                "verdict": (
                    "Phase 23A passed — individual-equity autonomous decision architecture "
                    "is specified; data-source audits must precede feature calculation or model training."
                    if passed
                    else "Phase 23A failed — architecture or research boundaries are incomplete."
                ),
                "all_gates_passed": passed,
                "current_system_state": "architecture_only_no_individual_equity_model",
                "allowed_next_step": "point_in_time_universe_source_audit_only",
                "forbidden_next_step": (
                    "current-constituent historical backtest; unaudited fundamental/sentiment ingestion; "
                    "model training; paper orders; live trading; real money; broker API"
                ),
            }
        ]
    )


def _write_markdown(outputs: dict[str, pd.DataFrame], output_path: Path) -> None:
    titles = {
        "scope_and_objective": "Scope and Objective",
        "point_in_time_universe_contract": "Point-in-Time Universe Contract",
        "feature_family_registry": "Feature-Family Registry",
        "target_and_decision_contract": "Target and Decision Contract",
        "model_architecture": "Autonomous Model Architecture",
        "portfolio_construction_contract": "Portfolio-Construction Contract",
        "risk_and_execution_contract": "Risk and Execution Contract",
        "validation_plan": "Validation Plan",
        "autonomous_decision_schema": "Autonomous Decision Audit Schema",
        "research_roadmap": "Research Roadmap",
        "scope_boundary": "Phase Boundary",
        "gate_report": "Gate Report",
        "summary": "Summary",
        "conclusion": "Conclusion",
    }
    lines = [
        "# Phase 23A — Individual-Equity Autonomous Decision Architecture",
        "",
        "This phase opens the individual-stock branch while preserving strict point-in-time, "
        "leakage, execution, risk, and safety boundaries. It specifies how a future model may "
        "autonomously rank stocks and propose target weights; it does not ingest data, train a "
        "model, run a stock backtest, or create paper/live orders.",
        "",
    ]
    for key, title in titles.items():
        lines.extend([f"## {title}", "", outputs[key].to_markdown(index=False), ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_phase23a_individual_equity_decision_architecture(
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
        output_dir = root_reports.parent / configured_output
    else:
        output_dir = root_reports / configured_output
    output_dir.mkdir(parents=True, exist_ok=True)

    scope_and_objective = build_scope_and_objective(phase_config)
    universe_contract = build_point_in_time_universe_contract()
    feature_registry = build_feature_family_registry()
    target_contract = build_target_and_decision_contract(phase_config)
    model_architecture = build_model_architecture(phase_config)
    portfolio_contract = build_portfolio_construction_contract(phase_config)
    risk_contract = build_risk_and_execution_contract(phase_config)
    validation_plan = build_validation_plan()
    decision_schema = build_autonomous_decision_schema()
    roadmap = build_research_roadmap()
    scope_boundary = build_scope_boundary(phase_config)
    gate_report = build_gate_report(
        phase_config=phase_config,
        universe_contract=universe_contract,
        feature_registry=feature_registry,
        model_architecture=model_architecture,
        portfolio_contract=portfolio_contract,
        validation_plan=validation_plan,
        decision_schema=decision_schema,
        roadmap=roadmap,
        scope_boundary=scope_boundary,
    )
    summary = build_summary(phase_config=phase_config, gate_report=gate_report)
    conclusion = build_conclusion(summary)

    outputs = {
        "scope_and_objective": scope_and_objective,
        "point_in_time_universe_contract": universe_contract,
        "feature_family_registry": feature_registry,
        "target_and_decision_contract": target_contract,
        "model_architecture": model_architecture,
        "portfolio_construction_contract": portfolio_contract,
        "risk_and_execution_contract": risk_contract,
        "validation_plan": validation_plan,
        "autonomous_decision_schema": decision_schema,
        "research_roadmap": roadmap,
        "scope_boundary": scope_boundary,
        "gate_report": gate_report,
        "summary": summary,
        "conclusion": conclusion,
    }

    for name, frame in outputs.items():
        frame.to_csv(output_dir / f"phase23a_{name}.csv", index=False)

    _write_markdown(outputs, output_dir / "phase23a_individual_equity_decision_architecture.md")

    dashboard_path = Path(str(phase_config["dashboard_status_path"]))
    if not dashboard_path.is_absolute():
        if dashboard_path.parts and dashboard_path.parts[0].lower() == "reports":
            dashboard_path = root_reports.parent / dashboard_path
        else:
            dashboard_path = root_reports / dashboard_path
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard = summary.copy()
    dashboard["dashboard_status"] = "phase23a_architecture_status_written"
    dashboard["notes"] = (
        "Architecture only. No individual-equity model, orders, live trading, real money, or broker API."
    )
    dashboard.to_csv(dashboard_path, index=False)
    outputs["dashboard_status"] = dashboard

    print("Wrote Phase 23A individual-equity decision architecture reports.")
    return outputs
