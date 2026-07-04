from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from market_strats.global_multi_asset.gma4_contract import FIXED_GMA4_UNIVERSE
from market_strats.global_multi_asset.gma6c_tournament_contract import EXPANDED_UNIVERSE
from market_strats.global_multi_asset import gma6d_cross_universe_tournament as gma6d

CONFIG_PATH = Path("configs/global_multi_asset_alpha/gma6c_cross_universe_tournament_v1.yaml")
MODULE_PATH = Path("src/market_strats/global_multi_asset/gma6d_cross_universe_tournament.py")


def _synthetic_dates() -> list:
    return [pd.Timestamp("2007-05-30").date(), *pd.bdate_range("2024-01-02", "2026-05-01").date]


def _synthetic_price_loader(_files: dict[str, Path], symbols: list[str]) -> dict[str, pd.DataFrame]:
    dates = _synthetic_dates()
    prices: dict[str, pd.DataFrame] = {}
    for idx, symbol in enumerate(symbols):
        drift = 0.0001 + idx * 0.000002
        if symbol in {"SPY", "QQQ", "XLK", "VNQ", "SLV", "EWG", "EWJ"}:
            drift += 0.00025
        if symbol == "BIL":
            drift = 0.00003
        values = [100.0 + idx]
        for _date in dates[1:]:
            values.append(values[-1] * (1.0 + drift))
        prices[symbol] = pd.DataFrame(
            {"close_raw": values, "total_return_index": values}, index=dates
        )
    return prices


def _fake_run_arm(*, arm, registry, config_path, prices, run_id):
    del config_path, prices
    scoreboard_rows = []
    detail_rows = []
    target_rows = []
    for cost_idx, cost in enumerate(gma6d.REQUIRED_COST_SCENARIOS):
        for trial_idx, trial in enumerate(registry.trials):
            trial_id = trial["trial_id"]
            detail_rows.append(
                {
                    "run_id": run_id,
                    "universe_version": arm.universe_version,
                    "source_gma4_trial_id": trial_id,
                    "arm_trial_id": f"{arm.universe_version}__{trial_id}",
                    "cost_scenario": cost,
                    "rebalance_schedule": "monthly_last_session_next_open",
                    "required_lookback_sessions": 0,
                    "trial_identity_application": "locked_trial_identity_with_arm_specific_universe_application",
                    "signal_rows": 1,
                    "order_rows": 1,
                    "equity_rows": 3,
                }
            )
            edge = 0.002 if arm.universe_version == gma6d.EXPANDED_UNIVERSE_VERSION else 0.0
            for scope in [
                "full_history",
                "rolling_3y",
                "rolling_5y",
                "sequential_walk_forward",
                "predefined_regimes",
            ]:
                scoreboard_rows.append(
                    {
                        "run_id": run_id,
                        "universe_version": arm.universe_version,
                        "trial_id": trial_id,
                        "trial_family": trial["family"],
                        "cost_scenario": cost,
                        "evaluation_scope": scope,
                        "window_id": scope,
                        "regime_id": "gfc_stress" if scope == "predefined_regimes" else "",
                        "period_start": gma6d.HISTORY_START,
                        "period_end": gma6d.HISTORY_END,
                        "effective_period_start": "2008-05-30"
                        if trial_idx
                        else gma6d.HISTORY_START,
                        "session_count": 100,
                        "net_cagr": 0.04 + edge + trial_idx / 10000 - cost_idx / 1000,
                        "annualised_volatility": 0.12,
                        "sharpe": 0.5 + edge,
                        "sortino": 0.7 + edge,
                        "maximum_drawdown": -0.2,
                        "cumulative_net_return": 1.0 + edge,
                        "annualised_turnover": 2.0,
                        "cost_drag": cost_idx / 1000,
                        "maximum_hhi": 0.25,
                        "methodology_regime_flag": arm.methodology_regime_flag,
                        "measurement_status": "valid",
                        "source_run_id": run_id,
                    }
                )
            target_rows.append(
                {
                    "run_id": run_id,
                    "universe_version": arm.universe_version,
                    "source_gma4_trial_id": trial_id,
                    "cost_scenario": cost,
                    "strategy_id": f"{arm.universe_version}__{trial_id}",
                    "decision_date": gma6d.HISTORY_START,
                    "execution_date": gma6d.HISTORY_END,
                    "symbol": "BIL",
                    "target_weight": 1.0,
                }
            )
    return pd.DataFrame(scoreboard_rows), pd.DataFrame(detail_rows), pd.DataFrame(target_rows)


@pytest.fixture()
def synthetic_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gma6d, "_run_arm", _fake_run_arm)
    return gma6d.run_gma6d_cross_universe_tournament(
        config_path=CONFIG_PATH,
        output_root=tmp_path / "reports",
        run_id_override="gma6d_test_fixed",
        executed_at_utc=datetime(2026, 6, 23, tzinfo=timezone.utc),
        price_loader=_synthetic_price_loader,
    )


def test_exactly_twenty_trials_are_executed_for_each_arm(synthetic_result):
    detail = pd.read_csv(synthetic_result.run_dir / "gma6d_evaluation_detail_v1.csv")
    counts = detail.groupby("universe_version")["source_gma4_trial_id"].nunique().to_dict()
    assert counts == {gma6d.CONTROL_UNIVERSE_VERSION: 20, gma6d.EXPANDED_UNIVERSE_VERSION: 20}


def test_exactly_four_frozen_cost_scenarios_are_used(synthetic_result):
    detail = pd.read_csv(synthetic_result.run_dir / "gma6d_evaluation_detail_v1.csv")
    assert sorted(detail["cost_scenario"].unique()) == sorted(gma6d.REQUIRED_COST_SCENARIOS)


def test_control_and_expanded_universe_sizes_and_no_fallback():
    assert len(FIXED_GMA4_UNIVERSE) == 22
    assert len(EXPANDED_UNIVERSE) == 29
    assert len(EXPANDED_UNIVERSE) != 27
    assert EXPANDED_UNIVERSE[:22] == FIXED_GMA4_UNIVERSE


def test_uso_and_dba_are_mandatory_in_expanded_execution():
    assert {"USO", "DBA"} <= set(EXPANDED_UNIVERSE)


def test_bundled_normalised_hashes_must_match_before_execution(tmp_path: Path):
    bad_hashes = tmp_path / "bad_hashes.csv"
    copy2(gma6d.DEFAULT_NORMALISED_HASHES, bad_hashes)
    bad_hashes.write_text(
        bad_hashes.read_text(encoding="utf-8").replace("SPY,", "SPY_BAD,", 1),
        encoding="utf-8",
    )
    with pytest.raises(gma6d.GMA6DExecutionError, match="normalised file hash manifest mismatch"):
        gma6d.verify_inputs(config_path=CONFIG_PATH, normalised_hashes_path=bad_hashes)


def test_missing_uso_methodology_flag_fails_closed(tmp_path: Path):
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    b2_source = Path(config["source_inputs"]["gma6b2_continuity_overlay"])
    b2_bad = tmp_path / "bad_b2.csv"
    b2_bad.write_text(
        b2_source.read_text(encoding="utf-8").replace(gma6d.REQUIRED_USO_FLAG, "not_required", 1),
        encoding="utf-8",
    )
    config["source_inputs"]["gma6b2_continuity_overlay"] = str(b2_bad)
    config_path = tmp_path / "gma6c.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(gma6d.GMA6DExecutionError, match="missing USO"):
        gma6d.verify_inputs(config_path=config_path)


def test_core_and_expanded_outputs_retain_locked_trial_identity(synthetic_result):
    detail = pd.read_csv(synthetic_result.run_dir / "gma6d_evaluation_detail_v1.csv")
    assert set(detail["trial_identity_application"]) == {
        "locked_trial_identity_with_arm_specific_universe_application"
    }
    assert detail["source_gma4_trial_id"].str.startswith("gma4_").all()
    assert detail["arm_trial_id"].str.contains("__gma4_").all()


def test_sample_comparability_status_is_recorded(synthetic_result):
    audit = synthetic_result.sample_audit
    assert set(audit["sample_comparability_status"]) <= {
        "identical_effective_sample",
        "not_comparable_due_to_effective_start",
        "not_comparable_due_to_missing_measurement",
    }
    assert not audit.empty


def test_no_network_data_provider_path_is_imported_or_invoked():
    source = MODULE_PATH.read_text(encoding="utf-8")
    import_lines = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    blocked = ["price_provider", "yfinance", "requests", "urllib", "data_provider"]
    assert not any(term in line for term in blocked for line in import_lines)
    assert "network_access_attempted" in source
    assert gma6d.NETWORK_ACCESS_ATTEMPTED is False


def test_shared_accounting_engine_is_invoked(monkeypatch):
    calls = {"count": 0}
    original = gma6d.replay_adapter._simulate_strategy

    def wrapped(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(gma6d.replay_adapter, "_simulate_strategy", wrapped)
    dates = [
        pd.Timestamp("2007-05-30").date(),
        *pd.bdate_range("2025-01-02", periods=35).date,
        pd.Timestamp("2026-05-01").date(),
    ]
    prices = {}
    for idx, symbol in enumerate(FIXED_GMA4_UNIVERSE):
        values = [100.0 + idx + n for n, _date in enumerate(dates)]
        prices[symbol] = pd.DataFrame(
            {"close_raw": values, "total_return_index": values}, index=dates
        )
    registry = SimpleNamespace(
        trials=[
            {
                "trial_id": "gma4_benchmark_bil_buy_hold_v1",
                "family": "benchmark",
                "version": "v1",
            }
        ]
    )
    gma6d._run_arm(
        arm=gma6d.ArmSpec(
            gma6d.CONTROL_UNIVERSE_VERSION, FIXED_GMA4_UNIVERSE, "not_applicable_no_uso"
        ),
        registry=registry,
        config_path=Path("configs/global_multi_asset_alpha/gma4_cross_asset_tournament_v1.yaml"),
        prices=prices,
        run_id="gma6d_replay_probe",
    )
    assert calls["count"] == 4


def test_repeated_execution_from_identical_inputs_is_deterministic(tmp_path: Path, monkeypatch):
    kwargs = {
        "config_path": CONFIG_PATH,
        "run_id_override": "gma6d_deterministic",
        "executed_at_utc": datetime(2026, 6, 23, tzinfo=timezone.utc),
        "price_loader": _synthetic_price_loader,
    }
    monkeypatch.setattr(gma6d, "_run_arm", _fake_run_arm)
    first = gma6d.run_gma6d_cross_universe_tournament(output_root=tmp_path / "one", **kwargs)
    second = gma6d.run_gma6d_cross_universe_tournament(output_root=tmp_path / "two", **kwargs)
    assert (first.run_dir / "gma6d_tournament_scoreboard_v1.csv").read_text(encoding="utf-8") == (
        second.run_dir / "gma6d_tournament_scoreboard_v1.csv"
    ).read_text(encoding="utf-8")
    assert (first.run_dir / "gma6d_cross_universe_comparison_v1.csv").read_text(
        encoding="utf-8"
    ) == (second.run_dir / "gma6d_cross_universe_comparison_v1.csv").read_text(encoding="utf-8")


def test_forbidden_selection_or_promotion_wording_is_absent(synthetic_result):
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in synthetic_result.run_dir.iterdir()
        if path.suffix in {".md", ".json"}
    )
    allowed_required_sentence = "no execution or promotion decision is produced."
    scrubbed = combined.replace(allowed_required_sentence, "")
    for forbidden in [
        "winner",
        "approved",
        "recommended",
        "deployable",
        "live-ready",
        "promotion workflow",
    ]:
        assert forbidden not in scrubbed
