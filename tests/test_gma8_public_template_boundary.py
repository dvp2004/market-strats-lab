"""Static public-template boundary test for GMA-8B/B.0.

Verifies that:
- the two public non-runnable templates exist and contain no machine-specific path fragments;
- each template declares at least one required private-input placeholder;
- the public boundary document contains all required safety statements.

This test does not refer to or read any private frozen local YAML contracts.
It reads no private market data, runs no logic, and makes no network requests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Filesystem roots
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

# ---------------------------------------------------------------------------
# Path fragments that must NOT appear in any public template.
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


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
        content = _TEMPLATE_PROVENANCE.read_text(encoding="utf-8")
        assert fragment not in content, (
            f"Prohibited fragment {fragment!r} found in public provenance template"
        )

    @pytest.mark.parametrize("fragment", _PROHIBITED_FRAGMENTS)
    def test_source_pointer_template_no_prohibited_fragment(self, fragment: str) -> None:
        content = _TEMPLATE_SOURCE_POINTER.read_text(encoding="utf-8")
        assert fragment not in content, (
            f"Prohibited fragment {fragment!r} found in public source-pointer template"
        )


class TestRequiredPlaceholders:
    """Verify each public template declares at least one private-input placeholder."""

    def test_provenance_template_has_placeholder(self) -> None:
        content = _TEMPLATE_PROVENANCE.read_text(encoding="utf-8")
        found = [ph for ph in _REQUIRED_PLACEHOLDERS if ph in content]
        assert found, (
            "Public provenance template contains no required placeholder; "
            f"expected at least one of {_REQUIRED_PLACEHOLDERS}"
        )

    def test_source_pointer_template_has_placeholder(self) -> None:
        content = _TEMPLATE_SOURCE_POINTER.read_text(encoding="utf-8")
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
        assert phrase.lower() in content, (
            f"Required safety statement {phrase!r} not found in boundary document"
        )
