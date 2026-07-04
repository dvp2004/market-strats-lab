"""Static portability-boundary test for GMA-8B/B.0 public templates.

Verifies that:
- the two public non-runnable templates exist and contain no machine-specific path
  fragments;
- each template declares at least one required private-input placeholder;
- the public boundary document contains all required safety statements;
- the frozen local GMA-8B/B.0 YAML contracts remain byte-identical to their
  preflight SHA-256 values recorded during the GMA-PUB1 publication audit.

This test reads no private market data, runs no GMA-8B or GMA-8C logic, calculates
no indicators, creates no targets, and makes no network requests. All assertions use
only the local filesystem and hashlib.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Filesystem roots (all relative to the worktree, which contains this file's
# parent directory).
# ---------------------------------------------------------------------------

_WORKTREE = Path(__file__).parent.parent
_PUBLIC_TEMPLATES_DIR = _WORKTREE / "configs" / "global_multi_asset_alpha" / "public_templates"

_TEMPLATE_PROVENANCE = (
    _PUBLIC_TEMPLATES_DIR / "gma8b_historical_data_provenance_public_template_v1.yaml"
)
_TEMPLATE_SOURCE_POINTER = (
    _PUBLIC_TEMPLATES_DIR / "gma8b_source_pointer_intake_public_template_v1.yaml"
)
_BOUNDARY_DOC = (
    _WORKTREE / "docs" / "global_multi_asset_alpha" / "gma8_public_private_evidence_boundary_v1.md"
)

# Frozen local contracts — must remain byte-identical to GMA-PUB1 preflight values.
_FROZEN_PROVENANCE = (
    _WORKTREE
    / "configs"
    / "global_multi_asset_alpha"
    / "gma8b_historical_data_provenance_contract_v1.yaml"
)
_FROZEN_SOURCE_POINTER = (
    _WORKTREE
    / "configs"
    / "global_multi_asset_alpha"
    / "gma8b_source_pointer_intake_contract_v1.yaml"
)

# SHA-256 values recorded during the GMA-PUB1 preflight inspection.
# These constants are the single source of truth for frozen-contract integrity.
_FROZEN_PROVENANCE_SHA256 = "ee63194d7f2aabac332ee301503755298c3dc342909446406fa6ff53bf109663"
_FROZEN_SOURCE_POINTER_SHA256 = "0b24d803f85122e5769eefaf3f2a8014babb9639468898e21e93369b74439c98"

# ---------------------------------------------------------------------------
# Path fragments that must NOT appear in any public template.
# These are machine-specific or user-specific Windows path components.
# ---------------------------------------------------------------------------
_PROHIBITED_FRAGMENTS = [
    "C:\\",
    "C:/",
    "Users",
    "Devesh",
    "Personal_Projects",
]

# ---------------------------------------------------------------------------
# Placeholder tokens that MUST appear in the public templates.
# At least one must be present in each template.
# ---------------------------------------------------------------------------
_REQUIRED_PLACEHOLDERS = [
    "REQUIRED_PRIVATE_EVIDENCE_ROOT",
    "REQUIRED_PRIVATE_EVIDENCE_PATH",
    "REQUIRED_PRIVATE_SOURCE_MANIFEST",
]

# ---------------------------------------------------------------------------
# Safety phrases that MUST appear in the public boundary document.
# ---------------------------------------------------------------------------
_REQUIRED_BOUNDARY_PHRASES = [
    "private immutable adjusted-price",
    "fail closed",
    "synthetic fixtures",
    "observed development evidence",
    "no execution or promotion decision",
    "machine-specific",
    "public templates",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------


class TestPublicTemplatesExist:
    """Verify each required public file is present on disk."""

    def test_provenance_template_exists(self) -> None:
        assert _TEMPLATE_PROVENANCE.is_file(), (
            f"Missing public provenance template: {_TEMPLATE_PROVENANCE}"
        )

    def test_source_pointer_template_exists(self) -> None:
        assert _TEMPLATE_SOURCE_POINTER.is_file(), (
            f"Missing public source-pointer template: {_TEMPLATE_SOURCE_POINTER}"
        )

    def test_boundary_document_exists(self) -> None:
        assert _BOUNDARY_DOC.is_file(), f"Missing public boundary document: {_BOUNDARY_DOC}"


class TestNoProhibitedPathFragments:
    """Verify public templates contain no machine-specific path fragments."""

    @pytest.mark.parametrize("fragment", _PROHIBITED_FRAGMENTS)
    def test_provenance_template_no_prohibited_fragment(self, fragment: str) -> None:
        content = _read(_TEMPLATE_PROVENANCE)
        assert fragment not in content, (
            f"Prohibited fragment {fragment!r} found in public provenance template"
        )

    @pytest.mark.parametrize("fragment", _PROHIBITED_FRAGMENTS)
    def test_source_pointer_template_no_prohibited_fragment(self, fragment: str) -> None:
        content = _read(_TEMPLATE_SOURCE_POINTER)
        assert fragment not in content, (
            f"Prohibited fragment {fragment!r} found in public source-pointer template"
        )


class TestRequiredPlaceholders:
    """Verify each public template declares at least one private-input placeholder."""

    def test_provenance_template_has_placeholder(self) -> None:
        content = _read(_TEMPLATE_PROVENANCE)
        found = [ph for ph in _REQUIRED_PLACEHOLDERS if ph in content]
        assert found, (
            "Public provenance template contains no required placeholder; "
            f"expected at least one of {_REQUIRED_PLACEHOLDERS}"
        )

    def test_source_pointer_template_has_placeholder(self) -> None:
        content = _read(_TEMPLATE_SOURCE_POINTER)
        found = [ph for ph in _REQUIRED_PLACEHOLDERS if ph in content]
        assert found, (
            "Public source-pointer template contains no required placeholder; "
            f"expected at least one of {_REQUIRED_PLACEHOLDERS}"
        )


class TestBoundaryDocumentSafetyStatements:
    """Verify the boundary document contains each required safety phrase."""

    @pytest.mark.parametrize("phrase", _REQUIRED_BOUNDARY_PHRASES)
    def test_boundary_doc_contains_phrase(self, phrase: str) -> None:
        content = _read(_BOUNDARY_DOC)
        assert phrase in content, (
            f"Required safety statement {phrase!r} not found in boundary document"
        )


class TestFrozenContractIntegrity:
    """Verify the frozen local GMA-8B/B.0 YAML contracts remain byte-identical
    to their SHA-256 values recorded during the GMA-PUB1 preflight inspection.

    A hash mismatch means an existing file was modified, which violates the
    portability-amendment safety boundary.
    """

    def test_frozen_provenance_contract_is_unchanged(self) -> None:
        assert _FROZEN_PROVENANCE.is_file(), (
            f"Frozen provenance contract is missing: {_FROZEN_PROVENANCE}"
        )
        actual = _sha256_file(_FROZEN_PROVENANCE)
        assert actual == _FROZEN_PROVENANCE_SHA256, (
            f"Frozen provenance contract has changed.\n"
            f"  expected : {_FROZEN_PROVENANCE_SHA256}\n"
            f"  actual   : {actual}"
        )

    def test_frozen_source_pointer_contract_is_unchanged(self) -> None:
        assert _FROZEN_SOURCE_POINTER.is_file(), (
            f"Frozen source-pointer contract is missing: {_FROZEN_SOURCE_POINTER}"
        )
        actual = _sha256_file(_FROZEN_SOURCE_POINTER)
        assert actual == _FROZEN_SOURCE_POINTER_SHA256, (
            f"Frozen source-pointer contract has changed.\n"
            f"  expected : {_FROZEN_SOURCE_POINTER_SHA256}\n"
            f"  actual   : {actual}"
        )
