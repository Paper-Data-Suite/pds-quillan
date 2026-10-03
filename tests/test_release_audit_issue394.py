"""Focused release-audit regression coverage for current Quillan release."""

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


def test_readme_describes_current_compact_review_and_release_endpoints() -> None:
    source = _text("README.md")
    for expected in (
        "C. Manage active context",
        "R. Resolve Scan Review Items",
        "7. Review class progress",
        "8. Review resubmissions / rescans",
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
        "The v0.10.5 candidate runtime is PDS2-only",
        "released Core 0.6.4 wheel",
    ):
        assert expected in source


def test_active_data_contract_index_uses_v0105_release_boundary() -> None:
    source = _text("docs/data_contracts.md")
    assert "Quillan v0.10.5 requires `pds-core>=0.6.2,<0.7`" in source
    assert "released Core 0.6.3 endpoint" in source
    assert "released Core 0.6.4 endpoint" in source
    assert "The active v0.10.5 review model is standards-based:" in source
    assert "This index documents the active v0.10.5 contracts." in source
    assert "Historical Core 0.6.0 producer" in source


def test_unreleased_changelog_reflects_issue417_patch_boundary() -> None:
    source = _text("CHANGELOG.md")
    current = source.split("## 0.10.4 - 2026-10-01", maxsplit=1)[0]
    assert "assignment-reporting snapshot" in current
    assert "assignment_review_report.pdf" in current
    assert "assignment_results_manifest.json" in current
    assert "spreadsheet-safe" in current
    assert "Selected Student Review" in current
    assert "B. Back" in current
    assert "pds-core>=0.6.2,<0.7" in current
