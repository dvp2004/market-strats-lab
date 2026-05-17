import pandas as pd

from market_strats.analysis.lookahead_signal_execution_audit import (
    _create_confirmation_reconstruction_audit,
    _create_lookahead_conclusion,
    _create_trend_sma_audit,
)


def test_create_trend_sma_audit_passes_for_trailing_sma():
    prices = [float(value) for value in range(1, 31)]
    trend_sma_days = 5

    overlay_result = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=len(prices)),
            "signal_price": prices,
            "trend_sma": pd.Series(prices).rolling(trend_sma_days).mean(),
        }
    )

    config = {
        "regime_switch_overlay": {"trend_sma_days": trend_sma_days},
        "phase7_lookahead_signal_execution_audit": {
            "trend_sma_tolerance": 0.000001,
            "ignored_initial_sma_warmup_rows": trend_sma_days,
            "max_allowed_trend_sma_mismatches": 0,
        },
    }

    audit = _create_trend_sma_audit(
        overlay_result=overlay_result,
        config=config,
    )

    assert audit.iloc[0]["status"] == "Passed"
    assert audit.iloc[0]["mismatch_count"] == 0


def test_create_confirmation_reconstruction_audit_passes():
    prices = [
        100.0,
        101.0,
        102.0,
        99.0,
        98.0,
        97.0,
        101.0,
        102.0,
        103.0,
    ]
    trend = [100.0] * len(prices)

    overlay_result = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=len(prices)),
            "signal_price": prices,
            "trend_sma": trend,
        }
    )

    # Three closes below trend switch defensive on the sixth row.
    # Three closes above trend switch offensive again on the ninth row.
    overlay_result["raw_signal_use_defensive"] = [
        False,
        False,
        False,
        False,
        False,
        True,
        True,
        True,
        False,
    ]

    config = {
        "regime_switch_overlay": {"confirmation_days": 3},
        "phase7_lookahead_signal_execution_audit": {
            "max_allowed_confirmation_mismatches": 0,
        },
    }

    audit = _create_confirmation_reconstruction_audit(
        overlay_result=overlay_result,
        config=config,
    )

    assert audit.iloc[0]["status"] == "Passed"
    assert audit.iloc[0]["mismatch_count"] == 0


def test_create_lookahead_conclusion_passes_when_inputs_pass():
    column_audit = pd.DataFrame({"status": ["Passed"]})
    trend_sma_audit = pd.DataFrame({"status": ["Passed"]})
    confirmation_audit = pd.DataFrame({"status": ["Passed"]})
    switch_timing_audit = pd.DataFrame({"status": ["Passed"]})
    slippage_turnover_audit = pd.DataFrame({"status": ["Passed"]})

    conclusion = _create_lookahead_conclusion(
        column_audit=column_audit,
        trend_sma_audit=trend_sma_audit,
        confirmation_audit=confirmation_audit,
        switch_timing_audit=switch_timing_audit,
        slippage_turnover_audit=slippage_turnover_audit,
    )

    final_row = conclusion[
        conclusion["claim"]
        == "No obvious lookahead issue was found in the audited final candidate."
    ].iloc[0]

    assert final_row["status"] == "Passed"