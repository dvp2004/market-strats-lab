import ast
import inspect
from pathlib import Path

import pandas as pd

import market_strats.run_backtest as run_backtest


PHASE15_FUNCTIONS = [
    "save_phase15q_post_endpoint_data_source_creation",
    "save_phase15r_real_post_endpoint_stream_validation",
    "save_phase15o_post_endpoint_candidate_stream_extension",
    "save_phase15p_extended_candidate_stream_audit",
    "save_phase15m_fresh_current_signal_generation",
    "save_phase15n_fresh_signal_audit_paper_dry_run_eligibility",
]

PHASE15_KEYS = [
    "phase15q_post_endpoint_data_source_creation",
    "phase15r_real_post_endpoint_stream_validation",
    "phase15o_post_endpoint_candidate_stream_extension",
    "phase15p_extended_candidate_stream_audit",
    "phase15m_fresh_current_signal_generation",
    "phase15n_fresh_signal_audit_paper_dry_run_eligibility",
]

PHASE15WXYZ_FUNCTIONS = [
    "build_phase15w_fresh_extension_config",
    "save_phase15wxyz_reports",
]

PHASE16A_FUNCTION = "save_phase16a_paper_dry_run_preregistration"
PHASE16B_FUNCTION = "save_phase16b_paper_dry_run_dashboard"
PHASE17A_FUNCTION = "save_phase17a_strategy_factory_report"
PHASE17B_FUNCTION = "save_phase17b_strategy_factory_robustness"
PHASE17C_FUNCTION = "save_phase17c_strategy_factory_watchlist_dashboard"
PHASE18A_FUNCTION = "save_phase18a_paper_signal_operational_hardening"
PHASE18B_FUNCTION = "save_phase18b_paper_cycle_tracker"
PHASE19A_FUNCTION = "save_phase19a_strategy_factory_multiverse"
PHASE19B_FUNCTION = "save_phase19b_strategy_factory_finalist_validation"
PHASE20A_FUNCTION = "save_phase20a_paper_finalist_tracking"
PHASE20B_FUNCTION = "save_phase20b_finalist_dynamic_allocation"
PHASE20C_FUNCTION = "save_phase20c_manual_paper_session"
PHASE20D_FUNCTION = "save_phase20d_manual_paper_session_ingestion"
PHASE20E_FUNCTION = "save_phase20e_manual_paper_discipline_tracker"
PHASE20F_FUNCTION = "save_phase20f_manual_paper_session_rollover"
PHASE21A_FUNCTION = "save_phase21a_historical_regime_stress_lab"
PHASE21B_FUNCTION = "save_phase21b_regime_candidate_reconciliation"


def _phase_config(enabled: bool) -> dict:
    return {key: {"enabled": enabled} for key in PHASE15_KEYS}


def _patch_phase15_functions(monkeypatch, calls: list[tuple[str, dict]]) -> None:
    for function_name in PHASE15_FUNCTIONS:

        def recorder(function_name=function_name, **kwargs):
            calls.append((function_name, kwargs))
            return {"summary": pd.DataFrame({"function_name": [function_name]})}

        monkeypatch.setattr(run_backtest, function_name, recorder)


def test_run_backtest_imports_phase15_downstream_save_functions():
    for function_name in PHASE15_FUNCTIONS:
        assert hasattr(run_backtest, function_name)


def test_run_backtest_imports_phase15wxyz_save_functions():
    for function_name in PHASE15WXYZ_FUNCTIONS:
        assert hasattr(run_backtest, function_name)


def test_run_backtest_imports_phase16a_save_function():
    assert hasattr(run_backtest, PHASE16A_FUNCTION)


def test_run_backtest_imports_phase16b_save_function():
    assert hasattr(run_backtest, PHASE16B_FUNCTION)


def test_run_backtest_imports_phase17a_save_function():
    assert hasattr(run_backtest, PHASE17A_FUNCTION)


def test_run_backtest_imports_phase17b_save_function():
    assert hasattr(run_backtest, PHASE17B_FUNCTION)


def test_run_backtest_imports_phase17c_save_function():
    assert hasattr(run_backtest, PHASE17C_FUNCTION)


def test_run_backtest_imports_phase18a_save_function():
    assert hasattr(run_backtest, PHASE18A_FUNCTION)


def test_run_backtest_imports_phase18b_save_function():
    assert hasattr(run_backtest, PHASE18B_FUNCTION)


def test_run_backtest_imports_phase19a_save_function():
    assert hasattr(run_backtest, PHASE19A_FUNCTION)


def test_run_backtest_imports_phase19b_save_function():
    assert hasattr(run_backtest, PHASE19B_FUNCTION)


def test_run_backtest_imports_phase20a_save_function():
    assert hasattr(run_backtest, PHASE20A_FUNCTION)


def test_run_backtest_imports_phase20b_save_function():
    assert hasattr(run_backtest, PHASE20B_FUNCTION)


def test_run_backtest_imports_phase20c_save_function():
    assert hasattr(run_backtest, PHASE20C_FUNCTION)


def test_run_backtest_imports_phase20d_save_function():
    assert hasattr(run_backtest, PHASE20D_FUNCTION)


def test_run_backtest_imports_phase20e_save_function():
    assert hasattr(run_backtest, PHASE20E_FUNCTION)


def test_run_backtest_imports_phase20f_save_function():
    assert hasattr(run_backtest, PHASE20F_FUNCTION)


def test_run_backtest_imports_phase21a_save_function():
    assert hasattr(run_backtest, PHASE21A_FUNCTION)


def test_run_backtest_imports_phase21b_save_function():
    assert hasattr(run_backtest, PHASE21B_FUNCTION)


def test_phase15_downstream_chain_calls_functions_in_required_order():
    source = inspect.getsource(run_backtest._run_phase15_downstream_fresh_signal_chain)
    tree = ast.parse(source)

    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.startswith("save_phase15")
    ]

    assert calls == PHASE15_FUNCTIONS


def test_phase15_downstream_chain_does_not_call_disabled_sections(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=_phase_config(enabled=False),
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert calls == []
    assert outputs == {}


def test_phase15wxyz_helper_does_not_run_when_disabled():
    outputs = run_backtest._run_phase15wxyz_fresh_extension_pipeline(
        config={"phase15wxyz_fresh_extension_pipeline": {"enabled": False}},
        reports_dir=Path("reports"),
    )

    assert outputs == {}


def test_phase15_fresh_extension_uses_separate_processed_data_dir():
    assert run_backtest._processed_data_dir({}) == Path("data/processed")
    assert run_backtest._processed_data_dir(
        {"_phase15_fresh_extension_mode": True}
    ) == Path("data/fresh/processed")
    assert run_backtest._processed_data_dir(
        {
            "_phase15_fresh_extension_mode": True,
            "phase15wxyz_fresh_extension_pipeline": {
                "fresh_processed_data_dir": "custom/fresh/cache"
            },
        }
    ) == Path("custom/fresh/cache")


def test_phase15_downstream_chain_executes_enabled_sections_with_expected_arguments(
    monkeypatch,
):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)
    reports_dir = Path("reports")
    relative_momentum_outputs = {"allocator": {"metrics": pd.DataFrame()}}
    ticker_outputs = {"SPY": {"strategy_results": {}}}

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=_phase_config(enabled=True),
        reports_dir=reports_dir,
        relative_momentum_outputs=relative_momentum_outputs,
        ticker_outputs=ticker_outputs,
    )

    assert [name for name, _kwargs in calls] == PHASE15_FUNCTIONS
    assert list(outputs) == [
        "phase15q",
        "phase15r",
        "phase15o",
        "phase15p",
        "phase15m",
        "phase15n",
    ]

    for function_name, kwargs in calls:
        assert kwargs["reports_dir"] == reports_dir
        assert "config" in kwargs

        if function_name in {
            "save_phase15o_post_endpoint_candidate_stream_extension",
            "save_phase15m_fresh_current_signal_generation",
        }:
            assert kwargs["relative_momentum_outputs"] is relative_momentum_outputs
            assert kwargs["ticker_outputs"] is ticker_outputs
        else:
            assert "relative_momentum_outputs" not in kwargs
            assert "ticker_outputs" not in kwargs


def test_phase16a_runs_after_phase15n_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [*PHASE15_FUNCTIONS, PHASE16A_FUNCTION]
    assert list(outputs) == [
        "phase15q",
        "phase15r",
        "phase15o",
        "phase15p",
        "phase15m",
        "phase15n",
        "phase16a",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase16b_runs_after_phase16a_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
    ]
    assert list(outputs)[-2:] == ["phase16a", "phase16b"]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase17a_runs_after_phase16b_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
    ]
    assert list(outputs)[-3:] == ["phase16a", "phase16b", "phase17a"]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase17b_runs_after_phase17a_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
    ]
    assert list(outputs)[-4:] == ["phase16a", "phase16b", "phase17a", "phase17b"]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase17c_runs_after_phase17b_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    def phase17c_recorder(**kwargs):
        calls.append((PHASE17C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17C_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17C_FUNCTION, phase17c_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    config["phase17c_strategy_factory_watchlist_dashboard"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
        PHASE17C_FUNCTION,
    ]
    assert list(outputs)[-5:] == [
        "phase16a",
        "phase16b",
        "phase17a",
        "phase17b",
        "phase17c",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase18a_runs_after_phase17c_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    def phase17c_recorder(**kwargs):
        calls.append((PHASE17C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17C_FUNCTION]})}

    def phase18a_recorder(**kwargs):
        calls.append((PHASE18A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18A_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17C_FUNCTION, phase17c_recorder)
    monkeypatch.setattr(run_backtest, PHASE18A_FUNCTION, phase18a_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    config["phase17c_strategy_factory_watchlist_dashboard"] = {"enabled": True}
    config["phase18a_paper_signal_operational_hardening"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
        PHASE17C_FUNCTION,
        PHASE18A_FUNCTION,
    ]
    assert list(outputs)[-6:] == [
        "phase16a",
        "phase16b",
        "phase17a",
        "phase17b",
        "phase17c",
        "phase18a",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase18b_runs_after_phase18a_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    def phase17c_recorder(**kwargs):
        calls.append((PHASE17C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17C_FUNCTION]})}

    def phase18a_recorder(**kwargs):
        calls.append((PHASE18A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18A_FUNCTION]})}

    def phase18b_recorder(**kwargs):
        calls.append((PHASE18B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18B_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17C_FUNCTION, phase17c_recorder)
    monkeypatch.setattr(run_backtest, PHASE18A_FUNCTION, phase18a_recorder)
    monkeypatch.setattr(run_backtest, PHASE18B_FUNCTION, phase18b_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    config["phase17c_strategy_factory_watchlist_dashboard"] = {"enabled": True}
    config["phase18a_paper_signal_operational_hardening"] = {"enabled": True}
    config["phase18b_paper_cycle_tracker"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
        PHASE17C_FUNCTION,
        PHASE18A_FUNCTION,
        PHASE18B_FUNCTION,
    ]
    assert list(outputs)[-7:] == [
        "phase16a",
        "phase16b",
        "phase17a",
        "phase17b",
        "phase17c",
        "phase18a",
        "phase18b",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase19a_runs_after_phase18b_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    def phase17c_recorder(**kwargs):
        calls.append((PHASE17C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17C_FUNCTION]})}

    def phase18a_recorder(**kwargs):
        calls.append((PHASE18A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18A_FUNCTION]})}

    def phase18b_recorder(**kwargs):
        calls.append((PHASE18B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18B_FUNCTION]})}

    def phase19a_recorder(**kwargs):
        calls.append((PHASE19A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE19A_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17C_FUNCTION, phase17c_recorder)
    monkeypatch.setattr(run_backtest, PHASE18A_FUNCTION, phase18a_recorder)
    monkeypatch.setattr(run_backtest, PHASE18B_FUNCTION, phase18b_recorder)
    monkeypatch.setattr(run_backtest, PHASE19A_FUNCTION, phase19a_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    config["phase17c_strategy_factory_watchlist_dashboard"] = {"enabled": True}
    config["phase18a_paper_signal_operational_hardening"] = {"enabled": True}
    config["phase18b_paper_cycle_tracker"] = {"enabled": True}
    config["phase19a_strategy_factory_multiverse"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
        PHASE17C_FUNCTION,
        PHASE18A_FUNCTION,
        PHASE18B_FUNCTION,
        PHASE19A_FUNCTION,
    ]
    assert list(outputs)[-8:] == [
        "phase16a",
        "phase16b",
        "phase17a",
        "phase17b",
        "phase17c",
        "phase18a",
        "phase18b",
        "phase19a",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase19b_runs_after_phase19a_when_enabled(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    def phase17c_recorder(**kwargs):
        calls.append((PHASE17C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17C_FUNCTION]})}

    def phase18a_recorder(**kwargs):
        calls.append((PHASE18A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18A_FUNCTION]})}

    def phase18b_recorder(**kwargs):
        calls.append((PHASE18B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18B_FUNCTION]})}

    def phase19a_recorder(**kwargs):
        calls.append((PHASE19A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE19A_FUNCTION]})}

    def phase19b_recorder(**kwargs):
        calls.append((PHASE19B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE19B_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17C_FUNCTION, phase17c_recorder)
    monkeypatch.setattr(run_backtest, PHASE18A_FUNCTION, phase18a_recorder)
    monkeypatch.setattr(run_backtest, PHASE18B_FUNCTION, phase18b_recorder)
    monkeypatch.setattr(run_backtest, PHASE19A_FUNCTION, phase19a_recorder)
    monkeypatch.setattr(run_backtest, PHASE19B_FUNCTION, phase19b_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    config["phase17c_strategy_factory_watchlist_dashboard"] = {"enabled": True}
    config["phase18a_paper_signal_operational_hardening"] = {"enabled": True}
    config["phase18b_paper_cycle_tracker"] = {"enabled": True}
    config["phase19a_strategy_factory_multiverse"] = {"enabled": True}
    config["phase19b_strategy_factory_finalist_validation"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
        PHASE17C_FUNCTION,
        PHASE18A_FUNCTION,
        PHASE18B_FUNCTION,
        PHASE19A_FUNCTION,
        PHASE19B_FUNCTION,
    ]
    assert list(outputs)[-9:] == [
        "phase16a",
        "phase16b",
        "phase17a",
        "phase17b",
        "phase17c",
        "phase18a",
        "phase18b",
        "phase19a",
        "phase19b",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase20b_to_phase20f_run_in_required_order_when_enabled(
    monkeypatch,
):
    calls: list[tuple[str, dict]] = []
    _patch_phase15_functions(monkeypatch, calls)

    def phase16a_recorder(**kwargs):
        calls.append((PHASE16A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16A_FUNCTION]})}

    def phase16b_recorder(**kwargs):
        calls.append((PHASE16B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE16B_FUNCTION]})}

    def phase17a_recorder(**kwargs):
        calls.append((PHASE17A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17A_FUNCTION]})}

    def phase17b_recorder(**kwargs):
        calls.append((PHASE17B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17B_FUNCTION]})}

    def phase17c_recorder(**kwargs):
        calls.append((PHASE17C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE17C_FUNCTION]})}

    def phase18a_recorder(**kwargs):
        calls.append((PHASE18A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18A_FUNCTION]})}

    def phase18b_recorder(**kwargs):
        calls.append((PHASE18B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE18B_FUNCTION]})}

    def phase19a_recorder(**kwargs):
        calls.append((PHASE19A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE19A_FUNCTION]})}

    def phase19b_recorder(**kwargs):
        calls.append((PHASE19B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE19B_FUNCTION]})}

    def phase20a_recorder(**kwargs):
        calls.append((PHASE20A_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE20A_FUNCTION]})}

    def phase20b_recorder(**kwargs):
        calls.append((PHASE20B_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE20B_FUNCTION]})}

    def phase20c_recorder(**kwargs):
        calls.append((PHASE20C_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE20C_FUNCTION]})}

    def phase20d_recorder(**kwargs):
        calls.append((PHASE20D_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE20D_FUNCTION]})}

    def phase20e_recorder(**kwargs):
        calls.append((PHASE20E_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE20E_FUNCTION]})}

    def phase20f_recorder(**kwargs):
        calls.append((PHASE20F_FUNCTION, kwargs))
        return {"summary": pd.DataFrame({"function_name": [PHASE20F_FUNCTION]})}

    monkeypatch.setattr(run_backtest, PHASE16A_FUNCTION, phase16a_recorder)
    monkeypatch.setattr(run_backtest, PHASE16B_FUNCTION, phase16b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17A_FUNCTION, phase17a_recorder)
    monkeypatch.setattr(run_backtest, PHASE17B_FUNCTION, phase17b_recorder)
    monkeypatch.setattr(run_backtest, PHASE17C_FUNCTION, phase17c_recorder)
    monkeypatch.setattr(run_backtest, PHASE18A_FUNCTION, phase18a_recorder)
    monkeypatch.setattr(run_backtest, PHASE18B_FUNCTION, phase18b_recorder)
    monkeypatch.setattr(run_backtest, PHASE19A_FUNCTION, phase19a_recorder)
    monkeypatch.setattr(run_backtest, PHASE19B_FUNCTION, phase19b_recorder)
    monkeypatch.setattr(run_backtest, PHASE20B_FUNCTION, phase20b_recorder)
    monkeypatch.setattr(run_backtest, PHASE20A_FUNCTION, phase20a_recorder)
    monkeypatch.setattr(run_backtest, PHASE20C_FUNCTION, phase20c_recorder)
    monkeypatch.setattr(run_backtest, PHASE20F_FUNCTION, phase20f_recorder)
    monkeypatch.setattr(run_backtest, PHASE20D_FUNCTION, phase20d_recorder)
    monkeypatch.setattr(run_backtest, PHASE20E_FUNCTION, phase20e_recorder)

    config = _phase_config(enabled=True)
    config["phase16a_paper_dry_run_preregistration"] = {"enabled": True}
    config["phase16b_paper_dry_run_dashboard"] = {"enabled": True}
    config["phase17a_strategy_factory"] = {"enabled": True}
    config["phase17b_strategy_factory_robustness"] = {"enabled": True}
    config["phase17c_strategy_factory_watchlist_dashboard"] = {"enabled": True}
    config["phase18a_paper_signal_operational_hardening"] = {"enabled": True}
    config["phase18b_paper_cycle_tracker"] = {"enabled": True}
    config["phase19a_strategy_factory_multiverse"] = {"enabled": True}
    config["phase19b_strategy_factory_finalist_validation"] = {"enabled": True}
    config["phase20b_finalist_dynamic_allocation"] = {"enabled": True}
    config["phase20a_paper_finalist_tracking"] = {"enabled": True}
    config["phase20c_manual_paper_session"] = {"enabled": True}
    config["phase20f_manual_paper_session_rollover"] = {"enabled": True}
    config["phase20d_manual_paper_session_ingestion"] = {"enabled": True}
    config["phase20e_manual_paper_discipline_tracker"] = {"enabled": True}
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase15_downstream_fresh_signal_chain(
        config=config,
        reports_dir=reports_dir,
        relative_momentum_outputs={},
        ticker_outputs={},
    )

    assert [name for name, _kwargs in calls] == [
        *PHASE15_FUNCTIONS,
        PHASE16A_FUNCTION,
        PHASE16B_FUNCTION,
        PHASE17A_FUNCTION,
        PHASE17B_FUNCTION,
        PHASE17C_FUNCTION,
        PHASE18A_FUNCTION,
        PHASE18B_FUNCTION,
        PHASE19A_FUNCTION,
        PHASE19B_FUNCTION,
        PHASE20B_FUNCTION,
        PHASE20A_FUNCTION,
        PHASE20C_FUNCTION,
        PHASE20F_FUNCTION,
        PHASE20D_FUNCTION,
        PHASE20E_FUNCTION,
    ]
    assert list(outputs)[-15:] == [
        "phase16a",
        "phase16b",
        "phase17a",
        "phase17b",
        "phase17c",
        "phase18a",
        "phase18b",
        "phase19a",
        "phase19b",
        "phase20b",
        "phase20a",
        "phase20c",
        "phase20f",
        "phase20d",
        "phase20e",
    ]
    assert calls[-1][1]["reports_dir"] == reports_dir


def test_phase15_downstream_chain_is_inserted_after_phase8b_bid_ask_diagnostic():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    phase8b_call = source.index(
        "save_phase8b_bid_ask_market_impact_diagnostic(\n"
        "            relative_momentum_outputs=relative_momentum_outputs,"
    )
    phase15_call = source.rindex(
        "_run_phase15_downstream_fresh_signal_chain(\n"
        "            config=config,"
    )

    assert phase8b_call < phase15_call


def test_phase15wxyz_chain_is_inserted_before_downstream_phase15_chain():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    phase8b_call = source.index(
        "save_phase8b_bid_ask_market_impact_diagnostic(\n"
        "            relative_momentum_outputs=relative_momentum_outputs,"
    )
    phase15wxyz_call = source.rindex(
        "_run_phase15wxyz_fresh_extension_pipeline(\n"
        "            config=config,"
    )
    phase15_downstream_call = source.rindex(
        "_run_phase15_downstream_fresh_signal_chain(\n"
        "            config=config,"
    )

    assert phase8b_call < phase15wxyz_call < phase15_downstream_call


def test_phase21a_runner_helper_calls_phase_when_enabled(monkeypatch):
    calls: list[dict] = []

    def phase21a_recorder(**kwargs):
        calls.append(kwargs)
        return {"summary": Path("reports/strategy_factory/regime_stress/phase21a_summary.csv")}

    monkeypatch.setattr(run_backtest, PHASE21A_FUNCTION, phase21a_recorder)
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase21a_historical_regime_stress_lab(
        config={"phase21a_historical_regime_stress_lab": {"enabled": True}},
        reports_dir=reports_dir,
    )

    assert outputs
    assert calls[0]["reports_dir"] == reports_dir


def test_phase21a_only_cli_flag_is_available():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    assert "--phase21a-only" in source
    assert "_run_phase21a_historical_regime_stress_lab(" in source


def test_phase21b_runner_helper_calls_phase_when_enabled(monkeypatch):
    calls: list[dict] = []

    def phase21b_recorder(**kwargs):
        calls.append(kwargs)
        return {"summary": Path("reports/strategy_factory/regime_reconciliation/phase21b_summary.csv")}

    monkeypatch.setattr(run_backtest, PHASE21B_FUNCTION, phase21b_recorder)
    reports_dir = Path("reports")

    outputs = run_backtest._run_phase21b_regime_candidate_reconciliation(
        config={"phase21b_regime_candidate_reconciliation": {"enabled": True}},
        reports_dir=reports_dir,
    )

    assert outputs
    assert calls[0]["reports_dir"] == reports_dir


def test_phase21b_only_cli_flag_is_available():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    assert "--phase21b-only" in source
    assert "_run_phase21b_regime_candidate_reconciliation(" in source
