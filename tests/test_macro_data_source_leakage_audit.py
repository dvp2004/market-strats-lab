from market_strats.analysis.macro_data_source_leakage_audit import (
    build_phase10b_conclusion,
    build_phase10b_gate_report,
    build_phase10b_leakage_control_check,
    build_phase10b_phase10c_boundary_check,
    build_phase10b_source_catalog,
    build_phase10b_source_recommendation,
    build_phase10b_summary,
    build_phase10b_timing_revision_check,
    save_phase10b_macro_data_source_leakage_audit,
)


def _source(source_id, macro_role, vintage=False, allowed=True, disqualifiers=None):
    return {
        "source_id": source_id,
        "name": source_id,
        "provider_type": "public_source",
        "macro_role": macro_role,
        "source_family": "macro_rates_inflation",
        "example_series": ["example"],
        "frequency": "monthly",
        "expected_history_coverage": "strong",
        "release_date_policy": "release-date-aware alignment",
        "revision_policy": "document revision policy",
        "has_release_calendar_or_timestamp": True,
        "has_vintage_or_revision_support": vintage,
        "supports_point_in_time_alignment": True,
        "known_leakage_risks": ["publication lag"],
        "required_controls": ["Use values only after release date."],
        "allowed_for_phase10c_source_audit": allowed,
        "allowed_for_strategy_test_now": False,
        "active_disqualifiers": disqualifiers or [],
    }


def _sample_phase_config():
    return {
        "audit_role": "Data-source and leakage feasibility audit only",
        "proposed_next_phase": "Phase 10C",
        "recommended_family": "macro_rates_inflation",
        "allow_data_download": False,
        "allow_feature_engineering": False,
        "allow_signal_creation": False,
        "allow_model_training": False,
        "allow_strategy_test": False,
        "allow_strategy_promotion": False,
        "phase10c_boundary": {
            "allowed_next_step": "data-source reliability and point-in-time alignment audit only",
            "forbidden_next_step": "macro signal backtest or allocation rule test",
            "phase10c_may_download_data": True,
            "phase10c_may_create_strategy_signal": False,
            "phase10c_may_test_strategy": False,
            "phase10c_may_promote_candidate": False,
        },
        "source_candidates": [
            _source("fred_alfred_macro_vintage", "general_macro_vintage_candidate", True),
            _source("treasury_rates_yield_curve", "rates_and_yield_curve_candidate"),
            _source("bls_cpi_inflation", "inflation_candidate"),
            _source(
                "bea_growth_activity",
                "growth_and_activity_candidate",
                False,
                True,
                ["revision_treatment_not_yet_solved"],
            ),
            _source(
                "nber_recession_dates",
                "evaluation_label_only",
                False,
                True,
                ["label_only_not_real_time_feature"],
            ),
        ],
        "gates": {
            "min_source_candidates": 5,
            "require_recommended_family_macro_rates_inflation": True,
            "require_no_data_download": True,
            "require_no_feature_engineering": True,
            "require_no_signal_creation": True,
            "require_no_model_training": True,
            "require_no_strategy_test": True,
            "require_no_strategy_promotion": True,
            "require_each_source_has_release_policy": True,
            "require_each_source_has_revision_policy": True,
            "require_each_source_has_leakage_controls": True,
            "require_at_least_one_vintage_capable_source": True,
            "require_at_least_one_rates_source": True,
            "require_at_least_one_inflation_source": True,
            "require_no_source_allowed_for_strategy_test_now": True,
            "require_phase10c_boundary_is_data_audit_only": True,
            "required_audit_role": "Data-source and leakage feasibility audit only",
        },
    }


def test_phase10b_builds_audit_tables_and_recommendation():
    phase_config = _sample_phase_config()

    catalog = build_phase10b_source_catalog(phase_config)
    timing = build_phase10b_timing_revision_check(phase_config)
    leakage = build_phase10b_leakage_control_check(phase_config)
    recommendation = build_phase10b_source_recommendation(
        catalog,
        timing,
        leakage,
        phase_config,
    )
    boundary = build_phase10b_phase10c_boundary_check(phase_config)

    assert len(catalog) == 5
    assert not timing.empty
    assert not leakage.empty
    assert recommendation.iloc[0]["phase10c_allowed"]
    assert bool(boundary["passed"].all())


def test_phase10b_gate_report_passes_valid_spec():
    phase_config = _sample_phase_config()

    catalog = build_phase10b_source_catalog(phase_config)
    timing = build_phase10b_timing_revision_check(phase_config)
    leakage = build_phase10b_leakage_control_check(phase_config)
    recommendation = build_phase10b_source_recommendation(
        catalog,
        timing,
        leakage,
        phase_config,
    )
    boundary = build_phase10b_phase10c_boundary_check(phase_config)
    summary = build_phase10b_summary(
        phase_config,
        catalog,
        timing,
        leakage,
        recommendation,
        boundary,
    )
    gate_report = build_phase10b_gate_report(
        phase_config,
        catalog,
        timing,
        leakage,
        summary,
    )
    conclusion = build_phase10b_conclusion(gate_report, recommendation)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — macro data-source leakage audit passed"
    )


def test_phase10b_gate_report_fails_if_strategy_test_allowed():
    phase_config = _sample_phase_config()
    phase_config["allow_strategy_test"] = True

    catalog = build_phase10b_source_catalog(phase_config)
    timing = build_phase10b_timing_revision_check(phase_config)
    leakage = build_phase10b_leakage_control_check(phase_config)
    recommendation = build_phase10b_source_recommendation(
        catalog,
        timing,
        leakage,
        phase_config,
    )
    boundary = build_phase10b_phase10c_boundary_check(phase_config)
    summary = build_phase10b_summary(
        phase_config,
        catalog,
        timing,
        leakage,
        recommendation,
        boundary,
    )
    gate_report = build_phase10b_gate_report(
        phase_config,
        catalog,
        timing,
        leakage,
        summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase10b_writes_expected_reports(tmp_path):
    config = {
        "phase10b_macro_data_source_leakage_audit": {
            "enabled": True,
            **_sample_phase_config(),
        }
    }

    outputs = save_phase10b_macro_data_source_leakage_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10b_macro_source_catalog.csv").exists()
    assert (tmp_path / "phase10b_macro_timing_revision_check.csv").exists()
    assert (tmp_path / "phase10b_macro_leakage_control_check.csv").exists()
    assert (tmp_path / "phase10b_macro_source_recommendation.csv").exists()
    assert (tmp_path / "phase10b_macro_phase10c_boundary_check.csv").exists()
    assert (tmp_path / "phase10b_macro_summary.csv").exists()
    assert (tmp_path / "phase10b_macro_gate_report.csv").exists()
    assert (tmp_path / "phase10b_macro_conclusion.csv").exists()
    assert (tmp_path / "phase10b_macro_data_source_leakage_audit.md").exists()