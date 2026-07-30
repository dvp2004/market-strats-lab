from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from market_strats.intelligence.mi2.technical_baseline import (
    RISK_FREE_INSTRUMENT_ID,
    build_feature_panel,
    build_target_panel,
    capped_inverse_vol_weights,
    final_prior_month_sessions,
    run_mi2_technical_baseline,
    simulate_strategies,
    top_quartile,
    validate_mi1_contract,
    walk_forward_boundaries,
)

ROOT = Path(__file__).resolve().parents[1]


def _tmp(name: str) -> Path:
    path = ROOT / ".pytest_tmp" / f"mi2_{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _sessions(count: int = 340) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-02", periods=count)


def _bars(instruments: list[str] | None = None, count: int = 340) -> pd.DataFrame:
    instruments = instruments or [
        "mi1_etf_spy",
        "mi1_etf_qqq",
        "mi1_etf_iwm",
        "mi1_etf_xlk",
        RISK_FREE_INSTRUMENT_ID,
    ]
    rows = []
    sessions = _sessions(count)
    for instrument_index, instrument_id in enumerate(instruments):
        for session_index, session in enumerate(sessions):
            raw_close = 100 + instrument_index * 10 + session_index * (1 + instrument_index * 0.1)
            adjusted_close = raw_close * (1.0 + instrument_index * 0.01)
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "session_date": session,
                    "open_raw": raw_close - 0.2,
                    "high_raw": raw_close + 0.5,
                    "low_raw": raw_close - 0.5,
                    "close_raw": raw_close,
                    "volume_raw": 1_000_000 + instrument_index * 1000,
                    "vendor_adjusted_close": adjusted_close,
                    "available_at_utc": datetime.combine(session.date(), datetime.min.time(), UTC),
                    "availability_evidence_level": "contractual_assumption",
                }
            )
    return pd.DataFrame(rows)


def _actions() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "event_id",
            "instrument_id",
            "session_date",
            "action_type",
            "value",
            "source_name",
            "available_at_utc",
            "availability_evidence_level",
            "availability_rule_id",
            "retrieved_at_utc",
            "snapshot_id",
        ]
    )


def _availability(bars: pd.DataFrame, *, unverified_eligible: bool = False) -> pd.DataFrame:
    rows = []
    for row in bars.itertuples(index=False):
        level = (
            "unverified"
            if unverified_eligible and len(rows) == 0
            else row.availability_evidence_level
        )
        rows.append(
            {
                "decision_timestamp_utc": row.available_at_utc,
                "dataset_row_id": f"{row.instrument_id}|{row.session_date.date().isoformat()}",
                "available_at_utc": row.available_at_utc,
                "availability_evidence_level": level,
                "eligible": True,
                "failure_reason": "",
            }
        )
    return pd.DataFrame(rows)


def _coverage(instruments: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run_id": "run",
            "instrument_id": instruments,
            "first_observed_session": "2020-01-02",
            "last_observed_session": "2021-04-21",
            "eligible_sessions": 340,
            "missing_sessions": 0,
            "coverage_ratio": 1.0,
            "continuous_history_sessions": 340,
            "start_date_eligible": True,
            "notes": "ok",
        }
    )


def _registry() -> dict:
    return {
        "research_start_date": {"minimum_common_history_sessions": 252},
        "walk_forward_and_holdout": {
            "initial_training_fraction": 0.50,
            "test_block_sessions": 20,
            "expanding_window": True,
            "purge_sessions": 20,
            "embargo_sessions": 20,
            "untouched_holdout_fraction": 0.20,
            "holdout_tuning_allowed": False,
        },
    }


def test_no_adjusted_close_enters_technical_features_and_split_windows_are_blocked() -> None:
    bars = _bars(["mi1_etf_spy"], count=280)
    bars.loc[bars["session_date"].eq(bars["session_date"].iloc[-1]), "vendor_adjusted_close"] = (
        999999.0
    )
    actions = pd.DataFrame(
        {
            "instrument_id": ["mi1_etf_spy"],
            "session_date": [bars["session_date"].iloc[260]],
            "action_type": ["split"],
        }
    )
    features = build_feature_panel(bars, actions, bars["session_date"].iloc[251])
    last = features.iloc[-1]
    raw_expected = bars["close_raw"].iloc[-1] / bars["close_raw"].iloc[-22] - 1.0
    assert last["raw_return_21"] == pytest.approx(raw_expected)
    assert last["feature_available"] is np.False_
    assert (
        last["feature_block_reason"] == "split_in_lookback_window_raw_prices_not_silently_adjusted"
    )
    assert "vendor_adjusted_close" not in features.columns


def test_target_uses_future_adjusted_data_and_target_never_appears_in_features() -> None:
    bars = _bars(["mi1_etf_spy", RISK_FREE_INSTRUMENT_ID], count=40)
    targets = build_target_panel(bars)
    features = build_feature_panel(bars, _actions(), bars["session_date"].iloc[0])
    spy = targets[targets["instrument_id"] == "mi1_etf_spy"].iloc[0]
    bil = bars[bars["instrument_id"] == RISK_FREE_INSTRUMENT_ID].reset_index(drop=True)
    spy_bars = bars[bars["instrument_id"] == "mi1_etf_spy"].reset_index(drop=True)
    expected = (
        spy_bars["vendor_adjusted_close"].iloc[20] / spy_bars["vendor_adjusted_close"].iloc[0] - 1
    ) - (bil["vendor_adjusted_close"].iloc[20] / bil["vendor_adjusted_close"].iloc[0] - 1)
    assert spy["target_value"] == pytest.approx(expected)
    assert spy["target_is_future_information"] is np.True_
    assert "target_value" not in features.columns


def test_walk_forward_purge_embargo_and_holdout_boundaries_match_registry() -> None:
    sessions = list(_sessions(260))
    bounds = walk_forward_boundaries(sessions, _registry())
    assert len(bounds["holdout_sessions"]) == 52
    assert bounds["holdout_sessions"][0] == sessions[208]
    assert bounds["initial_train_end_index"] == 104
    first = bounds["blocks"][0]
    assert first["test_start_index"] == 124
    assert first["test_end_index"] == 144
    assert bounds["blocks"][1]["train_end_index"] == 164
    assert _registry()["walk_forward_and_holdout"]["holdout_tuning_allowed"] is False


def test_portfolio_rebalance_execution_costs_bil_residual_and_caps() -> None:
    bars = _bars(count=320)
    features = build_feature_panel(bars, _actions(), bars["session_date"].iloc[251])
    sessions = list(pd.Index(bars["session_date"].unique()).sort_values())[-60:]
    returns, trades = simulate_strategies(
        bars,
        features,
        {"walk_forward_validation": sessions, "untouched_holdout": sessions},
    )
    composite = trades[trades["strategy_name"] == "technical_composite_top_quartile_inverse_vol"]
    assert not composite.empty
    assert (composite["trade_session_date"] > composite["signal_session_date"]).all()
    assert set(composite["execution_rule"]) == {"next_valid_us_equity_session_open"}
    assert composite["signal_session_date"].nunique() == len(
        [
            pair
            for pair in final_prior_month_sessions(
                list(pd.Index(bars["session_date"].unique()).sort_values())
            )
            if pair[1] in set(sessions)
        ]
    )
    assert (composite["research_weight"] <= 0.35).any()
    assert (composite["instrument_id"] == RISK_FREE_INSTRUMENT_ID).any()
    assert returns["transaction_cost"].sum() > 0


def test_top_quartile_selection_and_inverse_vol_cap_are_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "instrument_id": ["b", "a", "c", "d", "e"],
            "raw_momentum_252_minus_21": [1.0, 1.0, 0.5, 0.4, 0.3],
            "realized_volatility_20": [0.2, 0.1, 0.3, 0.4, 0.5],
        }
    )
    selected = top_quartile(frame, "raw_momentum_252_minus_21")
    assert selected["instrument_id"].tolist() == ["a"]
    weights = capped_inverse_vol_weights(frame.head(3), cap=0.35)
    assert max(weights.values()) <= 0.35
    assert sum(weights.values()) == pytest.approx(1.0)


def test_unverified_observations_are_blocked() -> None:
    bars = _bars(count=5)
    inputs = {
        "market_eod_bar": bars,
        "corporate_action_event": _actions(),
        "coverage_audit": _coverage(sorted(bars["instrument_id"].unique())),
        "decision_panel_availability_audit": _availability(bars, unverified_eligible=True),
    }
    with pytest.raises(ValueError, match="Unverified"):
        validate_mi1_contract(inputs)


def test_run_mi2_outputs_are_local_ignored_and_no_network_or_refresh_is_triggered() -> None:
    data_root = _tmp("mi1") / "mi1"
    mi2_root = _tmp("mi2") / "mi2"
    report_root = _tmp("reports") / "mi2"
    normalized = data_root / "normalized"
    normalized.mkdir(parents=True)
    bars = _bars(count=330)
    instruments = sorted(bars["instrument_id"].unique())
    bars.to_parquet(normalized / "market_eod_bar.parquet", index=False)
    _actions().to_parquet(normalized / "corporate_action_event.parquet", index=False)
    _coverage(instruments).to_parquet(normalized / "coverage_audit.parquet", index=False)
    _availability(bars).to_parquet(
        normalized / "decision_panel_availability_audit.parquet", index=False
    )

    result = run_mi2_technical_baseline(
        mi1_data_root=data_root,
        mi2_data_root=mi2_root,
        report_root=report_root,
        registry_path=ROOT / "configs" / "intelligence" / "mi2_research_registry.yaml",
    )
    assert result.feature_row_count == len(bars)
    assert result.target_row_count == len(bars)
    assert result.strategy_count == 7
    assert result.model_count == 1
    for path in result.output_paths.values():
        assert Path(path).exists()

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/private/mi2/*" in gitignore
    assert "/reports/mi2/*" in gitignore


def test_missing_mi1_outputs_fail_clearly() -> None:
    with pytest.raises(FileNotFoundError, match="Missing required MI-1 outputs"):
        run_mi2_technical_baseline(
            mi1_data_root=_tmp("missing"),
            mi2_data_root=_tmp("unused"),
            report_root=_tmp("unused_report"),
        )
