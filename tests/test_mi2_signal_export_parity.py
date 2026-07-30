from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from market_strats.intelligence.mi2.signal_export_parity import (
    EXPORT_COLUMNS,
    PROHIBITED_FIELDS,
    SignalExportContractError,
    canonical_export_sha256,
    export_mi2_research_signals,
)

SOURCE_HASH = "a" * 64
AVAILABILITY_REFERENCE = "mi1_decision_panel_availability_audit_sha256:" + "b" * 64
ROOT = Path(__file__).resolve().parents[1]


def _source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "session_date": ["2024-01-31", "2024-01-31", "2024-01-31", "2024-02-29"],
            "instrument_id": ["mi1_etf_spy", "mi1_etf_qqq", "mi1_etf_iwm", "mi1_etf_spy"],
            "model_name": ["ridge_fixed_alpha_1_0"] * 4,
            "prediction": [0.02, 0.02, -0.01, 0.03],
            "target_value": [0.9, 0.8, 0.7, 0.6],
        }
    )


def _export(source: pd.DataFrame | None = None) -> pd.DataFrame:
    return export_mi2_research_signals(
        _source() if source is None else source,
        source_artifact_sha256=SOURCE_HASH,
        data_cutoff_or_availability_reference=AVAILABILITY_REFERENCE,
    )


def test_identical_input_produces_identical_export_and_hash() -> None:
    first = _export()
    second = _export()
    pd.testing.assert_frame_equal(first, second)
    assert canonical_export_sha256(first) == canonical_export_sha256(second)


def test_scores_and_identities_reconcile_exactly() -> None:
    source = _source()
    exported = _export(source)
    source_identity = {
        (row.session_date, row.instrument_id, row.model_name): row.prediction
        for row in source.itertuples(index=False)
    }
    exported_identity = {
        (row.decision_date, row.asset_identifier, row.model_identifier): row.signal_score
        for row in exported.itertuples(index=False)
    }
    assert exported_identity == source_identity


def test_rank_ties_use_asset_identifier_and_ignore_input_order() -> None:
    first = _export()
    shuffled = _export(_source().sample(frac=1.0, random_state=9).reset_index(drop=True))
    pd.testing.assert_frame_equal(first, shuffled)
    january = first[first["decision_date"] == "2024-01-31"]
    assert january["asset_identifier"].tolist() == [
        "mi1_etf_qqq",
        "mi1_etf_spy",
        "mi1_etf_iwm",
    ]
    assert january["signal_rank"].tolist() == [1, 2, 3]
    assert january["signal_percentile"].tolist() == [1.0, 0.5, 0.0]


def test_output_is_research_only_and_has_no_prohibited_fields() -> None:
    exported = _export()
    assert tuple(exported.columns) == EXPORT_COLUMNS
    assert exported["research_only"].eq(True).all()  # noqa: E712
    assert exported["portfolio_influence"].eq(0).all()
    assert not (set(exported.columns) & PROHIBITED_FIELDS)


@pytest.mark.parametrize("field", sorted(PROHIBITED_FIELDS))
def test_prohibited_source_fields_fail_closed(field: str) -> None:
    source = _source()
    source[field] = "forbidden"
    with pytest.raises(SignalExportContractError, match="prohibited"):
        _export(source)


def test_missing_provenance_or_point_in_time_fields_fail_closed() -> None:
    with pytest.raises(SignalExportContractError, match="source_artifact_sha256"):
        export_mi2_research_signals(
            _source(),
            source_artifact_sha256="",
            data_cutoff_or_availability_reference=AVAILABILITY_REFERENCE,
        )
    with pytest.raises(SignalExportContractError, match="availability_reference"):
        export_mi2_research_signals(
            _source(),
            source_artifact_sha256=SOURCE_HASH,
            data_cutoff_or_availability_reference="",
        )
    with pytest.raises(SignalExportContractError, match="session_date"):
        _export(_source().drop(columns="session_date"))


def test_duplicate_identity_and_non_finite_score_fail_closed() -> None:
    duplicate = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(SignalExportContractError, match="duplicate"):
        _export(duplicate)
    invalid = _source()
    invalid.loc[0, "prediction"] = float("nan")
    with pytest.raises(SignalExportContractError, match="non-finite"):
        _export(invalid)


def test_frozen_contract_matches_research_only_export_boundary() -> None:
    contract = yaml.safe_load(
        (ROOT / "configs" / "intelligence" / "mi2_signal_export_parity_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert contract["export"]["research_only"] is True
    assert contract["export"]["portfolio_influence"] == 0
    assert set(contract["prohibited_fields"]) == PROHIBITED_FIELDS
    assert contract["boundaries"]["model_training"] is False
    assert contract["boundaries"]["portfolio_simulation"] is False
    assert contract["boundaries"]["market_strats_lab_influence"] is False
