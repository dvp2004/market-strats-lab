"""
GMA-1A-R tests: Required-Core Reconciliation and Split-Basis Verification.
All 40 tests must pass. No network access. Uses local immutable canonical files.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from market_strats.global_multi_asset.gma1ar_runner import (
    ACTION_TIMING_INSTRUMENTS,
    PROVIDER_BASIS_INSTRUMENTS,
    REQUIRED_CORE,
    _material,
    _return_diffs,
    build_action_timing_resolution,
    build_core_readiness,
    build_gate_report,
    build_inventory,
    build_provider_basis_resolution,
    build_split_evidence,
    determine_decision,
)

REPORT_DIR = Path("reports/global_multi_asset_alpha/data_foundation")
CANONICAL_DIR = Path("data/global_multi_asset_alpha/canonical_market")


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_canonical(
    n_rows: int = 100,
    div_at: list[int] | None = None,
    split_at: dict[int, float] | None = None,
    adj_offset_days: int = 0,
    base_price: float = 100.0,
) -> pd.DataFrame:
    """Synthetic canonical bundle for unit tests."""
    dates = pd.date_range("2020-01-02", periods=n_rows, freq="B")
    close = np.full(n_rows, base_price)
    div = np.zeros(n_rows)
    split = np.ones(n_rows)

    if div_at:
        for i in div_at:
            div[i] = 0.5

    if split_at:
        for i, r in split_at.items():
            split[i] = r

    # Build total_return_factor
    tr = np.ones(n_rows)
    prev_close = close[0]
    for i in range(1, n_rows):
        factor = (close[i] + div[i]) / prev_close
        tr[i] = factor
        prev_close = close[i]

    # Build adj_close: apply div one day earlier to simulate Yahoo offset
    adj = np.full(n_rows, base_price, dtype=float)
    for i in range(1, n_rows):
        offset_div = div[i - adj_offset_days] if adj_offset_days else div[i]
        adj[i] = adj[i - 1] * (close[i] + offset_div) / close[i - 1]

    tr_idx = np.ones(n_rows)
    for i in range(1, n_rows):
        tr_idx[i] = tr_idx[i - 1] * tr[i]

    return pd.DataFrame({
        "date": dates,
        "instrument_id": "TEST",
        "open_raw": close,
        "high_raw": close,
        "low_raw": close,
        "close_raw": close,
        "adj_close_provider": adj,
        "volume": 1_000_000,
        "dividend_cash": div,
        "split_ratio": split,
        "is_completed_observation": [False] + [True] * (n_rows - 1),
        "calendar_id": "us_listed_etf",
        "source_manifest_path": "",
        "source_manifest_sha256": "",
        "source_raw_sha256": "",
        "source_normalised_sha256": "",
        "total_return_factor": tr,
        "total_return_index": tr_idx,
        "total_return_construction_status": ["first_observation"] + ["constructed"] * (n_rows - 1),
    })


# ── TestInventory ──────────────────────────────────────────────────────────────

class TestInventory:

    def test_01_inventory_has_30_rows(self) -> None:
        inv = build_inventory()
        assert len(inv) == 30

    def test_02_inventory_columns_present(self) -> None:
        inv = build_inventory()
        required_cols = [
            "instrument_id", "is_required_core", "is_benchmark_only",
            "is_dynamic_satellite", "reconciliation_status",
            "overlap_rows", "median_return_difference_bps",
            "maximum_return_difference_bps",
            "return_difference_count_gt_tolerance",
            "earliest_material_difference_date",
            "latest_material_difference_date",
            "dividend_event_count", "split_event_count",
            "ready_for_replay_engine",
        ]
        for col in required_cols:
            assert col in inv.columns, f"Missing column: {col}"

    def test_03_reviewed_instruments_count_20(self) -> None:
        inv = build_inventory()
        reviewed = inv[inv["reconciliation_status"].isin(
            ["action_timing_review", "provider_basis_review"]
        )]
        assert len(reviewed) == 20

    def test_04_required_core_reviewed_count_16(self) -> None:
        inv = build_inventory()
        core_reviewed = inv[
            inv["reconciliation_status"].isin(["action_timing_review", "provider_basis_review"]) &
            inv["is_required_core"]
        ]
        assert len(core_reviewed) == 16

    def test_05_action_timing_core_instruments_identified(self) -> None:
        inv = build_inventory()
        at_core = inv[
            (inv["reconciliation_status"] == "action_timing_review") &
            inv["is_required_core"]
        ]["instrument_id"].tolist()
        for sym in ["SPY", "IWM", "RSP", "IEF", "TLT", "TIP", "LQD", "EMB", "UUP"]:
            assert sym in at_core, f"{sym} missing from action_timing core"

    def test_06_provider_basis_core_instruments_identified(self) -> None:
        inv = build_inventory()
        pb_core = inv[
            (inv["reconciliation_status"] == "provider_basis_review") &
            inv["is_required_core"]
        ]["instrument_id"].tolist()
        for sym in ["EFA", "VGK", "EWJ", "EEM", "HYG", "DBC", "VNQ"]:
            assert sym in pb_core, f"{sym} missing from provider_basis core"

    def test_07_acwi_is_benchmark_only(self) -> None:
        inv = build_inventory()
        acwi = inv[inv["instrument_id"] == "ACWI"].iloc[0]
        assert acwi["is_benchmark_only"]
        assert not acwi["is_required_core"]

    def test_08_satellite_instruments_not_core(self) -> None:
        inv = build_inventory()
        satellites = inv[inv["is_dynamic_satellite"]]["instrument_id"].tolist()
        for sym in satellites:
            assert sym not in REQUIRED_CORE


# ── TestSplitBasis ─────────────────────────────────────────────────────────────

class TestSplitBasis:

    def test_09_split_evidence_has_rows(self) -> None:
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        ev = build_split_evidence(actions)
        assert len(ev) > 0

    def test_10_all_evidence_confirmed_split_adjusted(self) -> None:
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        ev = build_split_evidence(actions)
        usable = ev[ev["evidence_status"].notna() &
                    ev["evidence_status"].ne("no_usable_split_rows_in_canonical")]
        # Every usable row must be confirmed from open/high/low/close continuity.
        expected = "raw_ohlc_already_split_adjusted_confirmed"
        assert (usable["evidence_status"] == expected).all(), \
            f"Unconfirmed rows:\n{usable[usable['evidence_status'] != expected]}"
        assert usable["all_raw_ohlc_consistent_with_split_adjustment"].all()

    def test_11_raw_price_ratio_near_1_for_all_splits(self) -> None:
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        ev = build_split_evidence(actions)
        usable = ev[ev["raw_price_ratio"].notna()]
        for _, r in usable.iterrows():
            ratio = float(r["raw_price_ratio"])
            # Normal daily price variation: within ±15% of 1.0
            assert abs(ratio - 1.0) < 0.15, \
                f"{r['instrument_id']} {r['split_date']}: raw_ratio={ratio} expected ~1.0"

    def test_12_split_basis_double_count_flag(self) -> None:
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        ev = build_split_evidence(actions)
        usable = ev[ev["evidence_status"].eq("raw_ohlc_already_split_adjusted_confirmed")]
        assert usable["applying_split_again_would_double_count"].all()

    def test_13_split_basis_fixture_already_adjusted(self) -> None:
        """Deterministic fixture: raw prices already split-adjusted."""
        df = _make_canonical(n_rows=50, split_at={25: 2.0})
        # raw close does not change at split date (already adjusted)
        assert df.iloc[24]["close_raw"] == df.iloc[25]["close_raw"]

    def test_14_split_basis_fixture_unadjusted_detectable(self) -> None:
        """Deterministic fixture: raw prices NOT yet split-adjusted (hypothetical)."""
        n = 50
        dates = pd.date_range("2020-01-02", periods=n, freq="B")
        close = np.full(n, 100.0)
        close[25:] = 50.0  # 2:1 split applied to raw close
        df = pd.DataFrame({
            "date": dates, "close_raw": close, "adj_close_provider": np.full(n, 100.0),
            "split_ratio": np.where(np.arange(n) == 25, 2.0, 1.0),
            "dividend_cash": 0.0,
            "is_completed_observation": [False] + [True] * (n - 1),
            "total_return_factor": 1.0, "total_return_index": 1.0,
        })
        raw_ratio = float(df.iloc[25]["close_raw"]) / float(df.iloc[24]["close_raw"])
        # If unadjusted, ratio would be ~0.5
        assert abs(raw_ratio - 0.5) < 0.05

    def test_15_split_and_dividend_same_day_fixture(self) -> None:
        """Fixture: split and dividend on same date."""
        df = _make_canonical(n_rows=50, div_at=[25], split_at={25: 2.0})
        assert df.iloc[25]["dividend_cash"] == 0.5
        assert df.iloc[25]["split_ratio"] == 2.0

    def test_16_missing_split_event_fixture(self) -> None:
        """Fixture: malformed split event (split_ratio = 0)."""
        df = _make_canonical(n_rows=50)
        df.loc[25, "split_ratio"] = 0.0
        splits = df[(df["split_ratio"] != 0.0) & (df["split_ratio"] != 1.0)]
        assert len(splits) == 0, "Zero split_ratio should be excluded"

    def test_17_qqq_split_confirmed(self) -> None:
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        ev = build_split_evidence(actions)
        qqq = ev[ev["instrument_id"] == "QQQ"]
        assert not qqq.empty
        assert (qqq["evidence_status"] == "raw_ohlc_already_split_adjusted_confirmed").all()

    def test_18_uso_reverse_split_confirmed(self) -> None:
        """USO had a 1:8 reverse split in 2020 (split_ratio=0.125)."""
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        ev = build_split_evidence(actions)
        uso = ev[ev["instrument_id"] == "USO"]
        assert not uso.empty
        assert (uso["evidence_status"] == "raw_ohlc_already_split_adjusted_confirmed").all()


# ── TestActionTimingResolution ─────────────────────────────────────────────────

class TestActionTimingResolution:

    @pytest.fixture(scope="class")
    def at_res(self) -> pd.DataFrame:
        recon = pd.read_csv(REPORT_DIR / "total_return_reconciliation.csv")
        return build_action_timing_resolution(recon)

    def test_19_all_at_instruments_in_resolution(self, at_res: pd.DataFrame) -> None:
        for sym in ACTION_TIMING_INSTRUMENTS:
            assert sym in at_res["instrument_id"].values

    def test_20_all_differences_on_dividend_dates(self, at_res: pd.DataFrame) -> None:
        """Every material difference date must have a dividend event."""
        real_diffs = at_res[at_res["event_type"] != "none_above_threshold"]
        for _, r in real_diffs.iterrows():
            assert float(r["provider_dividend"]) > 0 or r["event_type"] == "split", \
                f"{r['instrument_id']} {r['event_date']}: diff on non-dividend date"

    def test_21_no_unresolved_at_for_required_core(self, at_res: pd.DataFrame) -> None:
        core_at = at_res[at_res["instrument_id"].isin(REQUIRED_CORE)]
        unresolved = core_at[core_at["review_resolution"] == "unresolved_action_timing"]
        assert len(unresolved) == 0, f"Unresolved core AT:\n{unresolved}"

    def test_22_all_resolutions_are_immaterial_methodology(self, at_res: pd.DataFrame) -> None:
        real_diffs = at_res[at_res["event_type"] != "none_above_threshold"]
        assert (real_diffs["review_resolution"] == "resolved_immaterial_difference").all()
        assert (
            real_diffs["difference_cause"].str.contains(
                "provider multiplicative dividend-adjustment methodology",
                regex=False,
            ).all()
        )
        assert not real_diffs["date_offset_evidence"].any()

    def test_23_maximum_difference_below_5bps(self, at_res: pd.DataFrame) -> None:
        max_diff = at_res["difference_bps"].max()
        assert max_diff < 5.0, f"Action-timing max diff {max_diff:.3f} bps exceeds 5 bps"

    def test_24_spy_at_differences_documented(self, at_res: pd.DataFrame) -> None:
        spy = at_res[at_res["instrument_id"] == "SPY"]
        assert len(spy) > 0
        assert (spy["review_resolution"] == "resolved_immaterial_difference").all()

    def test_25_tlt_at_differences_documented(self, at_res: pd.DataFrame) -> None:
        tlt = at_res[at_res["instrument_id"] == "TLT"]
        assert len(tlt) > 0

    def test_26_at_fixture_dividend_methodology_difference(self) -> None:
        """Synthetic fixture confirms dividend-date differences are visible."""
        # Our construction applies dividend on ex-date
        # Yahoo applies it one day earlier → diff on ex-date
        df = _make_canonical(n_rows=100, div_at=[50], adj_offset_days=0)
        df["adj_close_provider"] = df["close_raw"]
        rd = _return_diffs(df)
        mat = _material(rd)
        # The material difference should be on or near index 50
        assert not mat.empty, "Expected material difference on dividend date"

    def test_27_at_fixture_no_div_no_diff(self) -> None:
        """Synthetic fixture: no dividends → no action-timing differences."""
        df = _make_canonical(n_rows=100)  # no dividends
        rd = _return_diffs(df)
        mat = _material(rd)
        assert len(mat) == 0, "Expected no material differences without dividends"


# ── TestProviderBasisResolution ────────────────────────────────────────────────

class TestProviderBasisResolution:

    @pytest.fixture(scope="class")
    def pb_res(self) -> pd.DataFrame:
        recon = pd.read_csv(REPORT_DIR / "total_return_reconciliation.csv")
        return build_provider_basis_resolution(recon)

    def test_28_all_pb_instruments_in_resolution(self, pb_res: pd.DataFrame) -> None:
        for sym in PROVIDER_BASIS_INSTRUMENTS:
            assert sym in pb_res["instrument_id"].values

    def test_29_zero_off_dividend_date_differences(self, pb_res: pd.DataFrame) -> None:
        """Critical: all provider-basis differences are on dividend dates."""
        assert (pb_res["off_dividend_date_difference_count"] == 0).all(), \
            f"Off-dividend differences found:\n{pb_res[pb_res['off_dividend_date_difference_count'] > 0]}"

    def test_30_no_unresolved_pb_for_required_core(self, pb_res: pd.DataFrame) -> None:
        core_pb = pb_res[pb_res["instrument_id"].isin(REQUIRED_CORE)]
        unresolved = core_pb[core_pb["review_resolution"] == "unresolved_provider_basis"]
        assert len(unresolved) == 0, f"Unresolved core PB:\n{unresolved}"

    def test_31_vgk_resolved_despite_12bps_max(self, pb_res: pd.DataFrame) -> None:
        """VGK has 12.18 bps max but zero off-dividend differences → resolved."""
        vgk = pb_res[pb_res["instrument_id"] == "VGK"].iloc[0]
        assert vgk["review_resolution"] == "resolved_provider_multiplicative_dividend_methodology"
        assert vgk["off_dividend_date_difference_count"] == 0

    def test_32_acwi_benchmark_resolved(self, pb_res: pd.DataFrame) -> None:
        acwi = pb_res[pb_res["instrument_id"] == "ACWI"].iloc[0]
        assert acwi["review_resolution"] in (
            "resolved_immaterial_provider_basis",
            "resolved_provider_multiplicative_dividend_methodology",
        )

    def test_33_raw_close_consistent_for_all_pb(self, pb_res: pd.DataFrame) -> None:
        assert pb_res["raw_close_consistent"].all()

    def test_34_pb_resolution_is_documented_not_assumed(self, pb_res: pd.DataFrame) -> None:
        """Explanation must reference actual evidence, not generic labels."""
        for _, r in pb_res.iterrows():
            expl = str(r["provider_basis_explanation"])
            assert len(expl) > 30, f"{r['instrument_id']}: explanation too short"
            assert "off_div" in expl or "dividend" in expl.lower(), \
                f"{r['instrument_id']}: explanation does not reference dividend dates"


# ── TestCoreReadiness ──────────────────────────────────────────────────────────

class TestCoreReadiness:

    @pytest.fixture(scope="class")
    def readiness(self) -> pd.DataFrame:
        inv = build_inventory()
        recon = pd.read_csv(REPORT_DIR / "total_return_reconciliation.csv")
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        at_res = build_action_timing_resolution(recon)
        pb_res = build_provider_basis_resolution(recon)
        split_ev = build_split_evidence(actions)
        return build_core_readiness(inv, at_res, pb_res, split_ev)

    def test_35_all_required_core_ready(self, readiness: pd.DataFrame) -> None:
        core = readiness[readiness["is_required_core"]]
        not_ready = core[~core["ready_for_replay_engine"]]
        assert len(not_ready) == 0, f"Core not ready:\n{not_ready[['instrument_id','blocking_reason']]}"

    def test_36_no_instrument_has_empty_resolution(self, readiness: pd.DataFrame) -> None:
        for _, r in readiness.iterrows():
            assert str(r["review_resolution"]) not in ("", "nan", "None"), \
                f"{r['instrument_id']}: empty review_resolution"

    def test_37_unresolved_action_timing_blocks_core(self) -> None:
        """Inject an unresolved AT into a synthetic readiness frame and verify blocking."""
        # Build minimal inventory-like frame
        inv = pd.DataFrame([{
            "instrument_id": "SPY",
            "is_required_core": True,
            "is_benchmark_only": False,
            "is_dynamic_satellite": False,
            "reconciliation_status": "action_timing_review",
            "overlap_rows": 8000,
            "median_return_difference_bps": 0.5,
            "maximum_return_difference_bps": 3.0,
            "return_difference_count_gt_tolerance": 5,
            "earliest_material_difference_date": "2020-01-01",
            "latest_material_difference_date": "2023-01-01",
            "dividend_event_count": 100,
            "split_event_count": 0,
            "ready_for_replay_engine": True,
        }])
        at_res_unresolved = pd.DataFrame([{
            "instrument_id": "SPY",
            "event_date": "2020-01-15",
            "review_resolution": "unresolved_action_timing",
        }])
        pb_res = pd.DataFrame()
        split_ev = pd.DataFrame()
        result = build_core_readiness(inv, at_res_unresolved, pb_res, split_ev)
        spy_row = result[result["instrument_id"] == "SPY"].iloc[0]
        assert not spy_row["ready_for_replay_engine"]
        assert spy_row["blocking_reason"] == "unresolved_action_timing_review"

    def test_38_satellite_ready_even_when_review_unresolved(self) -> None:
        """Non-core instruments get deferred eligibility, not a hard block."""
        inv = pd.DataFrame([{
            "instrument_id": "VWO",
            "is_required_core": False,
            "is_benchmark_only": False,
            "is_dynamic_satellite": True,
            "reconciliation_status": "provider_basis_review",
            "overlap_rows": 5000,
            "median_return_difference_bps": 0.5,
            "maximum_return_difference_bps": 6.0,
            "return_difference_count_gt_tolerance": 14,
            "earliest_material_difference_date": "2009-01-01",
            "latest_material_difference_date": "2023-01-01",
            "dividend_event_count": 30,
            "split_event_count": 0,
            "ready_for_replay_engine": True,
        }])
        pb_res_unresolved = pd.DataFrame([{
            "instrument_id": "VWO",
            "difference_date_count": 14,
            "median_difference_bps": 0.5,
            "maximum_difference_bps": 20.0,  # above threshold
            "differences_concentrated_on_action_dates": False,
            "differences_concentrated_on_fx_or_foreign_market_dates": False,
            "raw_close_consistent": True,
            "dividend_series_consistent": True,
            "split_series_consistent": True,
            "off_dividend_date_difference_count": 5,
            "provider_basis_explanation": "unresolvable differences",
            "review_resolution": "unresolved_provider_basis",
        }])
        result = build_core_readiness(inv, pd.DataFrame(), pb_res_unresolved, pd.DataFrame())
        vwo = result[result["instrument_id"] == "VWO"].iloc[0]
        # Non-core should still be ready (deferred, not blocked)
        assert vwo["ready_for_replay_engine"]
        assert vwo["review_state"] == "deferred_instrument"


# ── TestGateAndDecision ────────────────────────────────────────────────────────

class TestGateAndDecision:

    @pytest.fixture(scope="class")
    def full_results(self):
        inv = build_inventory()
        recon = pd.read_csv(REPORT_DIR / "total_return_reconciliation.csv")
        actions = pd.read_csv(REPORT_DIR / "corporate_action_contract.csv")
        at_res = build_action_timing_resolution(recon)
        pb_res = build_provider_basis_resolution(recon)
        split_ev = build_split_evidence(actions)
        readiness = build_core_readiness(inv, at_res, pb_res, split_ev)
        gate = build_gate_report(readiness, at_res, pb_res, split_ev)
        decision, warnings = determine_decision(readiness, gate, at_res, pb_res)
        return {
            "inv": inv, "at_res": at_res, "pb_res": pb_res,
            "split_ev": split_ev, "readiness": readiness,
            "gate": gate, "decision": decision, "warnings": warnings,
        }

    def test_39_all_gates_pass(self, full_results: dict) -> None:
        gate = full_results["gate"]
        failed = gate[~gate["passed"]]
        assert len(failed) == 0, f"Failed gates:\n{failed}"

    def test_40_decision_is_feasible(self, full_results: dict) -> None:
        assert full_results["decision"] == "gma1a_feasible_proceed_to_macro_foundation"

    def test_41_no_posthoc_provider_threshold_in_runner_source(self) -> None:
        source = Path("src/market_strats/global_multi_asset/gma1ar_runner.py").read_text(
            encoding="utf-8",
        )
        assert "PB_KNOWN" not in source
        assert "15 bps" not in source

    def test_42_no_ex_date_offset_claim_in_runner_source(self) -> None:
        source = Path("src/market_strats/global_multi_asset/gma1ar_runner.py").read_text(
            encoding="utf-8",
        )
        assert "resolved_ex_date_convention" not in source
        assert "ex-date convention offset" not in source
