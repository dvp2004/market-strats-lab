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


def test_phase15_downstream_chain_is_inserted_after_phase8b_bid_ask_diagnostic():
    source = Path(run_backtest.__file__).read_text(encoding="utf-8")

    phase8b_call = source.index(
        "save_phase8b_bid_ask_market_impact_diagnostic(\n"
        "            relative_momentum_outputs=relative_momentum_outputs,"
    )
    phase15_call = source.index(
        "_run_phase15_downstream_fresh_signal_chain(\n"
        "            config=config,"
    )

    assert phase8b_call < phase15_call
