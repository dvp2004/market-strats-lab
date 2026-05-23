from pathlib import Path

import pandas as pd

from market_strats.analysis.macro_source_reliability_alignment_audit import (
    build_phase10c_aligned_series_frame,
    build_phase10c_conclusion,
    build_phase10c_coverage_alignment_summary,
    build_phase10c_gate_report,
    build_phase10c_phase10d_boundary_check,
    build_phase10c_phase10d_readiness,
    build_phase10c_raw_series_frame,
    build_phase10c_series_catalog,
    build_phase10c_source_catalog,
    build_phase10c_summary,
    save_phase10c_macro_source_reliability_alignment_audit,
)


def _write_csv(path: Path, series_id: str) -> None:
    dates = pd.date_range("2020-01-01", "2021-12-31", freq="MS")
    if series_id in {"DGS2", "DGS10"}:
        dates = pd.date_range("2020-01-01", "2021-12-31", freq="B")

    values = range(1, len(dates) + 1)
    pd.DataFrame({"DATE": dates, series_id: values}).to_csv(path, index=False)


def _sample_config(tmp_path: Path) -> dict:
    paths = {}
    for series_id in ["UNRATE", "DGS2", "DGS10", "CPIAUCSL"]:
        path = tmp_path / f"{series_id}.csv"
        _write_csv(path, series_id)
        paths[series_id] = str(path)

    return {
        "audit_role": "Macro source reliability and point-in-time alignment audit only",
        "proposed_next_phase": "Phase 10D",
        "recommended_family": "macro_rates_inflation",
        "canonical_start_date": "2020-01-01",
        "canonical_end_date": "2021-12-31",
        "allow_remote_fetch": False,
        "allow_macro_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_model_feature_creation": False,
        "allow_model_training": False,
        "allow_strategy_test": False,
        "allow_strategy_promotion": False,
        "phase10d_boundary": {
            "allowed_next_step": "diagnostic-only macro regime analysis",
            "forbidden_next_step": "macro allocation rule, predictive model, or strategy test",
            "phase10d_may_create_macro_regime_diagnostic": True,
            "phase10d_may_create_strategy_signal": False,
            "phase10d_may_test_strategy": False,
            "phase10d_may_train_model": False,
            "phase10d_may_promote_candidate": False,
        },
        "selected_sources": [
            {
                "source_id": "fred_alfred_macro_vintage",
                "name": "FRED / ALFRED",
                "source_role": "general_macro_vintage_candidate",
                "provider": "FRED",
                "release_date_policy": "release policy documented",
                "revision_policy": "revision policy documented",
                "source_caveat": "audit only",
                "selected_for_phase10c": True,
                "allowed_for_phase10d_diagnostic": True,
                "allowed_for_strategy_test": False,
                "series": [
                    {
                        "series_id": "UNRATE",
                        "display_name": "Unemployment rate",
                        "fetch_url": "",
                        "local_csv_path": paths["UNRATE"],
                        "date_column": "DATE",
                        "value_column": "UNRATE",
                        "frequency": "monthly",
                        "value_type": "macro_level",
                        "availability_lag_trading_days": 3,
                        "has_explicit_release_dates": False,
                        "has_vintage_support": True,
                        "uses_current_revised_values": True,
                        "revision_risk_documented": True,
                    }
                ],
            },
            {
                "source_id": "treasury_rates_yield_curve",
                "name": "Treasury rates",
                "source_role": "rates_and_yield_curve_candidate",
                "provider": "FRED proxy",
                "release_date_policy": "release policy documented",
                "revision_policy": "revision policy documented",
                "source_caveat": "audit only",
                "selected_for_phase10c": True,
                "allowed_for_phase10d_diagnostic": True,
                "allowed_for_strategy_test": False,
                "series": [
                    {
                        "series_id": "DGS2",
                        "display_name": "2Y yield",
                        "fetch_url": "",
                        "local_csv_path": paths["DGS2"],
                        "date_column": "DATE",
                        "value_column": "DGS2",
                        "frequency": "daily",
                        "value_type": "rate_level",
                        "availability_lag_trading_days": 1,
                        "has_explicit_release_dates": True,
                        "has_vintage_support": False,
                        "uses_current_revised_values": False,
                        "revision_risk_documented": True,
                    },
                    {
                        "series_id": "DGS10",
                        "display_name": "10Y yield",
                        "fetch_url": "",
                        "local_csv_path": paths["DGS10"],
                        "date_column": "DATE",
                        "value_column": "DGS10",
                        "frequency": "daily",
                        "value_type": "rate_level",
                        "availability_lag_trading_days": 1,
                        "has_explicit_release_dates": True,
                        "has_vintage_support": False,
                        "uses_current_revised_values": False,
                        "revision_risk_documented": True,
                    },
                ],
            },
            {
                "source_id": "bls_cpi_inflation",
                "name": "BLS CPI",
                "source_role": "inflation_candidate",
                "provider": "FRED proxy",
                "release_date_policy": "release policy documented",
                "revision_policy": "revision policy documented",
                "source_caveat": "audit only",
                "selected_for_phase10c": True,
                "allowed_for_phase10d_diagnostic": True,
                "allowed_for_strategy_test": False,
                "series": [
                    {
                        "series_id": "CPIAUCSL",
                        "display_name": "CPI",
                        "fetch_url": "",
                        "local_csv_path": paths["CPIAUCSL"],
                        "date_column": "DATE",
                        "value_column": "CPIAUCSL",
                        "frequency": "monthly",
                        "value_type": "inflation_level",
                        "availability_lag_trading_days": 15,
                        "has_explicit_release_dates": False,
                        "has_vintage_support": False,
                        "uses_current_revised_values": True,
                        "revision_risk_documented": True,
                    }
                ],
            },
        ],
        "gates": {
            "min_selected_sources": 3,
            "min_loaded_series": 4,
            "min_phase10d_ready_series": 3,
            "min_aligned_availability_rate": 0.70,
            "require_remote_or_local_load_success": True,
            "require_release_policy_documented": True,
            "require_revision_policy_documented": True,
            "require_conservative_lag_applied": True,
            "require_revision_risk_documented": True,
            "require_rates_series_ready": True,
            "require_inflation_series_ready": True,
            "require_macro_series_ready": True,
            "require_no_macro_signal_creation": True,
            "require_no_allocation_rule_creation": True,
            "require_no_model_feature_creation": True,
            "require_no_model_training": True,
            "require_no_strategy_test": True,
            "require_no_strategy_promotion": True,
            "require_phase10d_boundary_diagnostic_only": True,
            "required_audit_role": "Macro source reliability and point-in-time alignment audit only",
        },
    }


def test_phase10c_loads_and_aligns_local_macro_sources(tmp_path):
    phase_config = _sample_config(tmp_path)
    source_catalog = build_phase10c_source_catalog(phase_config)
    series_catalog = build_phase10c_series_catalog(phase_config)
    raw_series, load_report = build_phase10c_raw_series_frame(
        series_catalog=series_catalog,
        allow_remote_fetch=False,
        remote_fetch_timeout_seconds=5,
    )
    trading_calendar = pd.bdate_range("2020-01-01", "2021-12-31")
    aligned = build_phase10c_aligned_series_frame(
        raw_series=raw_series,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    coverage = build_phase10c_coverage_alignment_summary(
        raw_series=raw_series,
        aligned_series=aligned,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )

    assert len(source_catalog) == 3
    assert bool(load_report["loaded"].all())
    assert not raw_series.empty
    assert not aligned.empty
    assert bool((coverage["aligned_availability_rate"] > 0.70).all())


def test_phase10c_gate_report_passes_valid_audit(tmp_path):
    phase_config = _sample_config(tmp_path)
    source_catalog = build_phase10c_source_catalog(phase_config)
    series_catalog = build_phase10c_series_catalog(phase_config)
    raw_series, load_report = build_phase10c_raw_series_frame(
        series_catalog=series_catalog,
        allow_remote_fetch=False,
        remote_fetch_timeout_seconds=5,
    )
    trading_calendar = pd.bdate_range("2020-01-01", "2021-12-31")
    aligned = build_phase10c_aligned_series_frame(
        raw_series=raw_series,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    coverage = build_phase10c_coverage_alignment_summary(
        raw_series=raw_series,
        aligned_series=aligned,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    readiness = build_phase10c_phase10d_readiness(
        coverage_alignment_summary=coverage,
        phase_config=phase_config,
    )
    boundary = build_phase10c_phase10d_boundary_check(phase_config)
    summary = build_phase10c_summary(
        phase_config=phase_config,
        source_catalog=source_catalog,
        series_catalog=series_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage,
        phase10d_readiness=readiness,
        phase10d_boundary_check=boundary,
    )
    gate_report = build_phase10c_gate_report(
        phase_config=phase_config,
        source_catalog=source_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage,
        phase10d_readiness=readiness,
        phase10d_boundary_check=boundary,
        summary=summary,
    )
    conclusion = build_phase10c_conclusion(
        gate_report=gate_report,
        phase10d_readiness=readiness,
    )

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — macro source reliability/alignment audit passed"
    )


def test_phase10c_gate_report_fails_if_strategy_test_allowed(tmp_path):
    phase_config = _sample_config(tmp_path)
    phase_config["allow_strategy_test"] = True

    source_catalog = build_phase10c_source_catalog(phase_config)
    series_catalog = build_phase10c_series_catalog(phase_config)
    raw_series, load_report = build_phase10c_raw_series_frame(
        series_catalog=series_catalog,
        allow_remote_fetch=False,
        remote_fetch_timeout_seconds=5,
    )
    trading_calendar = pd.bdate_range("2020-01-01", "2021-12-31")
    aligned = build_phase10c_aligned_series_frame(
        raw_series=raw_series,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    coverage = build_phase10c_coverage_alignment_summary(
        raw_series=raw_series,
        aligned_series=aligned,
        series_catalog=series_catalog,
        trading_calendar=trading_calendar,
    )
    readiness = build_phase10c_phase10d_readiness(
        coverage_alignment_summary=coverage,
        phase_config=phase_config,
    )
    boundary = build_phase10c_phase10d_boundary_check(phase_config)
    summary = build_phase10c_summary(
        phase_config=phase_config,
        source_catalog=source_catalog,
        series_catalog=series_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage,
        phase10d_readiness=readiness,
        phase10d_boundary_check=boundary,
    )
    gate_report = build_phase10c_gate_report(
        phase_config=phase_config,
        source_catalog=source_catalog,
        load_report=load_report,
        coverage_alignment_summary=coverage,
        phase10d_readiness=readiness,
        phase10d_boundary_check=boundary,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase10c_writes_expected_reports(tmp_path):
    phase_config = _sample_config(tmp_path)
    config = {
        "phase10c_macro_source_reliability_alignment_audit": {
            "enabled": True,
            **phase_config,
        }
    }

    outputs = save_phase10c_macro_source_reliability_alignment_audit(
        config=config,
        reports_dir=tmp_path,
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10c_macro_source_catalog.csv").exists()
    assert (tmp_path / "phase10c_macro_series_catalog.csv").exists()
    assert (tmp_path / "phase10c_macro_raw_series.csv").exists()
    assert (tmp_path / "phase10c_macro_load_report.csv").exists()
    assert (tmp_path / "phase10c_macro_aligned_series.csv").exists()
    assert (tmp_path / "phase10c_macro_coverage_alignment_summary.csv").exists()
    assert (tmp_path / "phase10c_macro_phase10d_readiness.csv").exists()
    assert (tmp_path / "phase10c_macro_phase10d_boundary_check.csv").exists()
    assert (tmp_path / "phase10c_macro_summary.csv").exists()
    assert (tmp_path / "phase10c_macro_gate_report.csv").exists()
    assert (tmp_path / "phase10c_macro_conclusion.csv").exists()
    assert (
        tmp_path / "phase10c_macro_source_reliability_alignment_audit.md"
    ).exists()