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
        "S. Share Results with Meridian",
        "O. Open Evidence",
        "C. Continue Review — <current continuation label>",
        "E. Export Feedback",
        "A. Advanced Actions",
        "P. Previous Student",
        "W. Next Student Needing Review",
        "`pds-core>=0.6.2,<0.7` runtime dependency",
        "The v0.10.0 candidate runtime is PDS2-only",
        "authenticated Core 0.6.2 and Core 0.6.3 endpoint wheels",
    ):
        assert expected in source

    assert "10. Export student feedback" not in source
    assert "`pds-core>=0.6,<0.7` runtime dependency" not in source
    assert "The v0.9.0 runtime is PDS2-only" not in source
    assert "exact released Core 0.6.0 wheel" not in source


def test_active_data_contract_index_uses_v010_release_boundary() -> None:
    source = _text("docs/data_contracts.md")

    assert "Quillan v0.10.0 requires `pds-core>=0.6.2,<0.7`" in source
    assert "Core 0.6.2 minimum endpoint and Core 0.6.3 current endpoint" in source
    assert "The active v0.10.0 review model is standards-based:" in source
    assert "This index documents the active v0.10.0 contracts." in source
    assert "Historical Core 0.6.0 producer" in source

    assert "The active v0.8.6 review model is standards-based:" not in source
    assert "This index documents the active v0.8.6 contracts." not in source


def test_unreleased_changelog_reflects_completed_issue393_gate() -> None:
    source = _text("CHANGELOG.md")
    current = source.split("## 0.9.0 -", maxsplit=1)[0]

    assert "#393 installed/physical candidate acceptance completed" in current
    assert "#394 final workflow/release audit" in current
    assert "explicit owner release authorization" in current
    assert "Release remains pending #393 installed/physical acceptance" not in current
