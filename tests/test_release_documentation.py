"""Release documentation integrity and governance tests."""

from __future__ import annotations

from pathlib import Path

from scripts.check_documentation import documentation_failures

ROOT = Path(__file__).resolve().parents[1]


def test_markdown_links_encoding_and_anchors_are_valid() -> None:
    assert documentation_failures(ROOT) == ()


def test_required_release_documents_and_owner_boundaries_are_explicit() -> None:
    required = (
        "docs/releases/v0.8.9.md",
        "docs/release_process.md",
        "docs/release_checklist.md",
        "docs/physical_acceptance_v0.8.9.md",
        "docs/releases/v0.8.9_acceptance_matrix.md",
    )
    for relative in required:
        assert (ROOT / relative).is_file(), relative
    physical = (ROOT / required[3]).read_text(encoding="utf-8")
    assert "owner-only" in physical
    assert all(value in physical for value in ("PASS", "PASS WITH DOCUMENTED LIMITATION", "FAIL"))
    checklist = (ROOT / required[2]).read_text(encoding="utf-8")
    for prohibited in ("tag", "GitHub Release", "upload", "publication", "deployment"):
        assert prohibited in checklist
