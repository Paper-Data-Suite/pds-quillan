"""Focused release-audit regression coverage for issue #394."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_development_install_validator_matches_v010_core_floor() -> None:
    source = _text("scripts/validate_development_install.ps1")

    assert "Quillan requires pds-core>=0.6.2,<0.7" in source
    assert "{'>=0.6.2', '<0.7'}" in source
    assert "SpecifierSet('>=0.6.2,<0.7')" in source

    assert "Quillan requires pds-core>=0.6,<0.7" not in source
    assert "== {'>=0.6', '<0.7'}" not in source
    assert "SpecifierSet('>=0.6,<0.7')" not in source


def test_readme_describes_final_compact_review_and_release_endpoints() -> None:
    source = _text("README.md")

    for expected in (
        "C. Manage active context",
        "R. Resolve Scan Review Items",
        "7. Review class progress",
        "F. Batch Feedback Export",
        "G. Prepare Feedback for Printing / Sharing",
        "S. Share Results with Meridian",
        "O. Open Evidence",
        "C. Continue Review — <current continuation label>",
        "E. Export Feedback",
        "A. Advanced Actions",
        "P. Previous Student",
        "W. Next Student Needing Review",
        "`pds-core>=0.6.2,<0.7` runtime dependency",
        "The v0.10.1 candidate runtime is PDS2-only",
        "authenticated Core 0.6.2 and Core 0.6.3 endpoint wheels",
    ):
        assert expected in source

    assert "10. Export student feedback" not in source
    assert "`pds-core>=0.6,<0.7` runtime dependency" not in source
    assert "The v0.9.0 runtime is PDS2-only" not in source
    assert "exact released Core 0.6.0 wheel" not in source


def test_active_data_contract_index_uses_v010_release_boundary() -> None:
    source = _text("docs/data_contracts.md")

    assert "Quillan v0.10.1 requires `pds-core>=0.6.2,<0.7`" in source
    assert "Core 0.6.2 minimum endpoint and Core 0.6.3 current endpoint" in source
    assert "The active v0.10.1 review model is standards-based:" in source
    assert "This index documents the active v0.10.1 contracts." in source
    assert "Historical Core 0.6.0 producer" in source

    assert "The active v0.8.6 review model is standards-based:" not in source
    assert "This index documents the active v0.8.6 contracts." not in source


def test_unreleased_changelog_reflects_issue412_patch_boundary() -> None:
    source = _text("CHANGELOG.md")
    current = source.split("## 0.10.0 -", maxsplit=1)[0]

    assert "feedback batch assembly (#412)" in current
    assert "pypdf>=5,<7" in current
    assert "per-student PDFs" in current
