import pandas as pd

from market_strats.analysis.diagnostic_macro_regime_analysis import (
    build_phase10d_analysis_frame,
    build_phase10d_conclusion,
    build_phase10d_gate_report,
    build_phase10d_helpful_regime_report,
    build_phase10d_macro_panel,
    build_phase10d_phase10e_boundary_check,
    build_phase10d_regime_frame,
    build_phase10d_regime_metrics,
    build_phase10d_summary,
    build_phase10d_weak_regime_report,
    save_phase10d_diagnostic_macro_regime_analysis,
)


def _phase_config():
    return {
        "diagnostic_role": "Diagnostic-only macro regime analysis",
        "proposed_next_phase": "Phase 10E",
        "canonical_start_date": "2020-01-01",
        "canonical_end_date": "2021-12-31",
        "allow_macro_signal_creation": False,
        "allow_allocation_rule_creation": False,
        "allow_model_feature_creation": False,
        "allow_model_training": False,
        "allow_strategy_test": False,
        "allow_strategy_promotion": False,
        "phase10e_boundary": {
            "allowed_next_step": "pre-registered macro hypothesis design spec only",
            "forbidden_next_step": "macro allocation rule, predictive model, or strategy test",
            "phase10e_may_create_hypothesis_spec": True,
            "phase10e_may_create_strategy_signal": False,
            "phase10e_may_test_strategy": False,
            "phase10e_may_train_model": False,
            "phase10e_may_promote_candidate": False,
        },
        "regime_definitions": {
            "unemployment_level": {
                "low_threshold": 4.0,
                "high_threshold": 6.0,
                "labels": {
                    "low": "low_unemployment_below_4",
                    "normal": "normal_unemployment_4_to_6",
                    "high": "high_unemployment_above_6",
                },
            },
            "unemployment_6m_change": {
                "lookback_trading_days": 20,
                "falling_threshold": -0.1,
                "rising_threshold": 0.1,
                "labels": {
                    "falling": "unemployment_falling",
                    "stable": "unemployment_stable",
                    "rising": "unemployment_rising",
                },
            },
            "yield_curve_10y_2y": {
                "inverted_threshold": 0.0,
                "steep_threshold": 1.0,
                "labels": {
                    "inverted": "yield_curve_inverted",
                    "normal": "yield_curve_normal_0_to_1",
                    "steep": "yield_curve_steep_above_1",
                },
            },
            "short_rate_level": {
                "low_threshold": 1.5,
                "high_threshold": 4.0,
                "labels": {
                    "low": "low_short_rates_below_1_5",
                    "normal": "normal_short_rates_1_5_to_4",
                    "high": "high_short_rates_above_4",
                },
            },
            "inflation_yoy": {
                "lookback_trading_days": 20,
                "low_threshold": 0.02,
                "high_threshold": 0.04,
                "labels": {
                    "low": "low_inflation_below_2",
                    "normal": "normal_inflation_2_to_4",
                    "high": "high_inflation_above_4",
                },
            },
        },
        "gates": {
            "min_macro_panel_rows": 400,
            "min_regime_families": 5,
            "min_regime_metric_rows": 5,
            "min_rows_per_regime": 20,
            "require_macro_panel_loaded": True,
            "require_unrate_present": True,
            "require_dgs2_present": True,
            "require_dgs10_present": True,
            "require_cpi_present": True,
            "require_regime_metrics_generated": True,
            "require_no_macro_signal_creation": True,
            "require_no_allocation_rule_creation": True,
            "require_no_model_feature_creation": True,
            "require_no_model_training": True,
            "require_no_strategy_test": True,
            "require_no_strategy_promotion": True,
            "require_phase10e_boundary_spec_only": True,
            "required_diagnostic_role": "Diagnostic-only macro regime analysis",
        },
    }


def _macro_aligned_series():
    dates = pd.bdate_range("2020-01-01", "2021-12-31")
    frames = []
    for series_id, value in [
        ("UNRATE", 5.0),
        ("DGS2", 1.0),
        ("DGS10", 2.0),
        ("CPIAUCSL", 250.0),
    ]:
        series_values = [value + index * 0.001 for index in range(len(dates))]
        frames.append(
            pd.DataFrame(
                {
                    "source_id": "test_source",
                    "series_id": series_id,
                    "trading_date": dates,
                    "value": series_values,
                }
            )
        )

    return pd.concat(frames, ignore_index=True)


def _strategy_frame(daily_return: float):
    dates = pd.bdate_range("2020-01-01", "2021-12-31")
    return pd.DataFrame(
        {
            "date": dates,
            "strategy_return": [daily_return] * len(dates),
        }
    )


def test_phase10d_builds_macro_panel_and_regime_metrics():
    phase_config = _phase_config()
    macro_panel = build_phase10d_macro_panel(
        macro_aligned_series=_macro_aligned_series(),
        phase_config=phase_config,
    )
    regime_frame = build_phase10d_regime_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    analysis = build_phase10d_analysis_frame(
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
        regime_frame=regime_frame,
    )
    metrics = build_phase10d_regime_metrics(
        analysis_frame=analysis,
        phase_config=phase_config,
    )

    assert not macro_panel.empty
    assert regime_frame["regime_family"].nunique() == 5
    assert not analysis.empty
    assert not metrics.empty


def test_phase10d_gate_report_passes_valid_diagnostic():
    phase_config = _phase_config()
    macro_panel = build_phase10d_macro_panel(
        macro_aligned_series=_macro_aligned_series(),
        phase_config=phase_config,
    )
    regime_frame = build_phase10d_regime_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    analysis = build_phase10d_analysis_frame(
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
        regime_frame=regime_frame,
    )
    metrics = build_phase10d_regime_metrics(
        analysis_frame=analysis,
        phase_config=phase_config,
    )
    helpful = build_phase10d_helpful_regime_report(metrics)
    weak = build_phase10d_weak_regime_report(metrics)
    boundary = build_phase10d_phase10e_boundary_check(phase_config)
    summary = build_phase10d_summary(
        phase_config=phase_config,
        macro_panel=macro_panel,
        regime_frame=regime_frame,
        regime_metrics=metrics,
        helpful_regime_report=helpful,
        weak_regime_report=weak,
        phase10e_boundary_check=boundary,
    )
    gate_report = build_phase10d_gate_report(
        phase_config=phase_config,
        macro_panel=macro_panel,
        regime_metrics=metrics,
        summary=summary,
    )
    conclusion = build_phase10d_conclusion(gate_report)

    assert bool(gate_report["passed"].all())
    assert conclusion.iloc[0]["verdict"] == (
        "Completed — diagnostic-only macro regime analysis"
    )


def test_phase10d_gate_report_fails_if_strategy_test_allowed():
    phase_config = _phase_config()
    phase_config["allow_strategy_test"] = True

    macro_panel = build_phase10d_macro_panel(
        macro_aligned_series=_macro_aligned_series(),
        phase_config=phase_config,
    )
    regime_frame = build_phase10d_regime_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    analysis = build_phase10d_analysis_frame(
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
        regime_frame=regime_frame,
    )
    metrics = build_phase10d_regime_metrics(
        analysis_frame=analysis,
        phase_config=phase_config,
    )
    helpful = build_phase10d_helpful_regime_report(metrics)
    weak = build_phase10d_weak_regime_report(metrics)
    boundary = build_phase10d_phase10e_boundary_check(phase_config)
    summary = build_phase10d_summary(
        phase_config=phase_config,
        macro_panel=macro_panel,
        regime_frame=regime_frame,
        regime_metrics=metrics,
        helpful_regime_report=helpful,
        weak_regime_report=weak,
        phase10e_boundary_check=boundary,
    )
    gate_report = build_phase10d_gate_report(
        phase_config=phase_config,
        macro_panel=macro_panel,
        regime_metrics=metrics,
        summary=summary,
    )

    assert not bool(gate_report["passed"].all())


def test_save_phase10d_writes_expected_reports(tmp_path):
    phase_config = _phase_config()
    config = {
        "phase10d_diagnostic_macro_regime_analysis": {
            "enabled": True,
            **phase_config,
        }
    }

    outputs = save_phase10d_diagnostic_macro_regime_analysis(
        config=config,
        reports_dir=tmp_path,
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
        macro_aligned_series=_macro_aligned_series(),
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10d_macro_panel.csv").exists()
    assert (tmp_path / "phase10d_macro_regime_frame.csv").exists()
    assert (tmp_path / "phase10d_macro_analysis_frame.csv").exists()
    assert (tmp_path / "phase10d_macro_regime_metrics.csv").exists()
    assert (tmp_path / "phase10d_macro_helpful_regime_report.csv").exists()
    assert (tmp_path / "phase10d_macro_weak_regime_report.csv").exists()
    assert (tmp_path / "phase10d_macro_phase10e_boundary_check.csv").exists()
    assert (tmp_path / "phase10d_macro_summary.csv").exists()
    assert (tmp_path / "phase10d_macro_gate_report.csv").exists()
    assert (tmp_path / "phase10d_macro_conclusion.csv").exists()
    assert (tmp_path / "phase10d_diagnostic_macro_regime_analysis.md").exists() 