import pandas as pd

from market_strats.analysis.preregistered_macro_rule_test import (
    build_phase10f_base_return_frame,
    build_phase10f_benchmark_metrics,
    build_phase10f_behavioural_metrics,
    build_phase10f_conclusion,
    build_phase10f_discipline_gate_report,
    build_phase10f_episode_metrics,
    build_phase10f_macro_panel,
    build_phase10f_rule_activation_frame,
    build_phase10f_rule_comparison_summary,
    build_phase10f_rule_gate_report,
    build_phase10f_rule_metrics,
    build_phase10f_rule_returns,
    save_phase10f_preregistered_macro_rule_test,
)


def _phase_config():
    return {
        "test_role": "Pre-registered macro-rule test only",
        "canonical_start_date": "2020-01-01",
        "canonical_end_date": "2021-12-31",
        "holdout_start_date": "2021-01-01",
        "allow_new_thresholds": False,
        "allow_new_inputs": False,
        "allow_model_feature_creation": False,
        "allow_model_training": False,
        "allow_strategy_promotion": False,
        "friction": {
            "stress_bps_per_rule_switch": 10.0,
            "max_stress_cagr_degradation_pts": 0.15,
            "max_stress_calmar_degradation": 0.010,
        },
        "episode_windows": [
            {
                "episode": "sample_2020",
                "start_date": "2020-01-01",
                "end_date": "2020-12-31",
            },
            {
                "episode": "sample_2021",
                "start_date": "2021-01-01",
                "end_date": "2021-12-31",
            },
        ],
        "allowed_macro_input_registry": [
            "DGS2",
            "CPIAUCSL",
            "UNRATE",
            "cpi_yoy",
            "short_rate_level",
            "inflation_yoy",
            "unemployment_level",
            "existing_final_candidate_return",
        ],
        "rules": [
            {
                "rule_id": "H1_supportive_low_rate_low_inflation_relief",
                "hypothesis_id": "H1_supportive_low_rate_low_inflation_relief",
                "role": "Candidate for further validation only",
                "replacement_return_column": "buy_hold_return",
                "activation_join": "AND",
                "conditions": [
                    {
                        "input": "DGS2",
                        "derived_input": "short_rate_level",
                        "operator": "<",
                        "threshold": 1.5,
                        "locked_threshold_description": "DGS2 below 1.5",
                    },
                    {
                        "input": "cpi_yoy",
                        "derived_input": "inflation_yoy",
                        "operator": "<",
                        "threshold": 0.02,
                        "locked_threshold_description": "CPI below 2%",
                    },
                ],
            },
            {
                "rule_id": "H2_high_rate_high_unemployment_stress_guard",
                "hypothesis_id": "H2_high_rate_high_unemployment_stress_guard",
                "role": "Candidate for further validation only",
                "replacement_return_column": "spy_12m_return",
                "activation_join": "OR",
                "conditions": [
                    {
                        "input": "DGS2",
                        "derived_input": "short_rate_level",
                        "operator": ">",
                        "threshold": 4.0,
                        "locked_threshold_description": "DGS2 above 4.0",
                    },
                    {
                        "input": "UNRATE",
                        "derived_input": "unemployment_level",
                        "operator": ">",
                        "threshold": 6.0,
                        "locked_threshold_description": "UNRATE above 6.0",
                    },
                ],
            },
        ],
        "validation_gates": {
            "max_full_cagr_damage_pts": 0.15,
            "max_episode_cagr_damage_pts": 0.25,
            "max_episode_calmar_damage": 0.020,
            "max_episode_drawdown_damage_pts": 1.00,
        },
        "gates": {
            "expected_rule_ids": [
                "H1_supportive_low_rate_low_inflation_relief",
                "H2_high_rate_high_unemployment_stress_guard",
            ],
            "min_rules": 2,
            "max_rules": 2,
            "required_test_role": "Pre-registered macro-rule test only",
        },
    }


def _macro_aligned_series():
    dates = pd.bdate_range("2020-01-01", "2021-12-31")
    frames = []

    values = {
        "DGS2": 1.0,
        "CPIAUCSL": 250.0,
        "UNRATE": 5.0,
    }

    for series_id, start_value in values.items():
        frames.append(
            pd.DataFrame(
                {
                    "series_id": series_id,
                    "trading_date": dates,
                    "value": [start_value + index * 0.001 for index in range(len(dates))],
                }
            )
        )

    return pd.concat(frames, ignore_index=True)


def _strategy_frame(daily_return):
    dates = pd.bdate_range("2020-01-01", "2021-12-31")
    return pd.DataFrame({"date": dates, "strategy_return": daily_return})


def test_phase10f_builds_rule_returns_and_reports():
    phase_config = _phase_config()
    macro_panel = build_phase10f_macro_panel(
        macro_aligned_series=_macro_aligned_series(),
        phase_config=phase_config,
    )
    activation = build_phase10f_rule_activation_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    base_returns = build_phase10f_base_return_frame(
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
    )
    rule_returns = build_phase10f_rule_returns(
        base_returns=base_returns,
        activation_frame=activation,
        phase_config=phase_config,
    )

    assert not macro_panel.empty
    assert not activation.empty
    assert not rule_returns.empty
    assert set(rule_returns["rule_id"].unique()) == {
        "H1_supportive_low_rate_low_inflation_relief",
        "H2_high_rate_high_unemployment_stress_guard",
    }


def test_phase10f_discipline_gate_report_passes():
    phase_config = _phase_config()
    macro_panel = build_phase10f_macro_panel(
        macro_aligned_series=_macro_aligned_series(),
        phase_config=phase_config,
    )
    activation = build_phase10f_rule_activation_frame(
        macro_panel=macro_panel,
        phase_config=phase_config,
    )
    base_returns = build_phase10f_base_return_frame(
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
    )
    rule_returns = build_phase10f_rule_returns(
        base_returns=base_returns,
        activation_frame=activation,
        phase_config=phase_config,
    )
    rule_metrics = build_phase10f_rule_metrics(
        rule_returns=rule_returns,
        phase_config=phase_config,
    )
    benchmark_metrics = build_phase10f_benchmark_metrics(
        base_returns=base_returns,
        phase_config=phase_config,
    )
    episode_metrics = build_phase10f_episode_metrics(
        rule_returns=rule_returns,
        base_returns=base_returns,
        phase_config=phase_config,
    )
    behavioural_metrics = build_phase10f_behavioural_metrics(rule_returns)
    rule_gate_report = build_phase10f_rule_gate_report(
        rule_metrics=rule_metrics,
        benchmark_metrics=benchmark_metrics,
        episode_metrics=episode_metrics,
        behavioural_metrics=behavioural_metrics,
        phase_config=phase_config,
    )
    discipline = build_phase10f_discipline_gate_report(
        phase_config=phase_config,
        rule_metrics=rule_metrics,
        rule_gate_report=rule_gate_report,
    )
    conclusion = build_phase10f_conclusion(
        discipline_gate_report=discipline,
        rule_gate_report=rule_gate_report,
    )

    assert bool(discipline["passed"].all())
    assert not bool(conclusion.iloc[0]["strategy_promotion"])


def test_phase10f_discipline_fails_if_new_inputs_allowed():
    phase_config = _phase_config()
    phase_config["allow_new_inputs"] = True

    discipline = build_phase10f_discipline_gate_report(
        phase_config=phase_config,
        rule_metrics=pd.DataFrame({"x": [1]}),
        rule_gate_report=pd.DataFrame({"x": [1]}),
    )

    assert not bool(discipline["passed"].all())


def test_save_phase10f_writes_expected_reports(tmp_path):
    phase_config = _phase_config()
    config = {
        "phase10f_preregistered_macro_rule_test": {
            "enabled": True,
            **phase_config,
        }
    }

    outputs = save_phase10f_preregistered_macro_rule_test(
        config=config,
        reports_dir=tmp_path,
        final_candidate=_strategy_frame(0.0005),
        spy_buy_hold=_strategy_frame(0.0006),
        spy_12m_momentum=_strategy_frame(0.0004),
        macro_aligned_series=_macro_aligned_series(),
    )

    assert not outputs["conclusion"].empty
    assert (tmp_path / "phase10f_macro_panel.csv").exists()
    assert (tmp_path / "phase10f_macro_rule_activation_frame.csv").exists()
    assert (tmp_path / "phase10f_macro_rule_returns.csv").exists()
    assert (tmp_path / "phase10f_macro_rule_metrics.csv").exists()
    assert (tmp_path / "phase10f_macro_benchmark_metrics.csv").exists()
    assert (tmp_path / "phase10f_macro_episode_metrics.csv").exists()
    assert (tmp_path / "phase10f_macro_behavioural_metrics.csv").exists()
    assert (tmp_path / "phase10f_macro_rule_gate_report.csv").exists()
    assert (tmp_path / "phase10f_macro_rule_comparison_summary.csv").exists()
    assert (tmp_path / "phase10f_macro_discipline_gate_report.csv").exists()
    assert (tmp_path / "phase10f_macro_conclusion.csv").exists()
    assert (tmp_path / "phase10f_preregistered_macro_rule_test.md").exists()