"""Focused release-audit regression coverage for current Quillan release."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_development_install_validator_matches_core_065_floor() -> None:
    source = _text("scripts/validate_development_install.ps1")
    assert "Quillan requires pds-core>=0.6.5,<0.7" in source
    assert "{'>=0.6.5', '<0.7'}" in source
    assert "SpecifierSet('>=0.6.5,<0.7')" in source

def test_readme_preserves_review_commands_and_current_release() -> None:
    source = _text("README.md")
    for expected in (
        "R. Resolve Scan Review Items", "7. Review class progress",
        "8. Review resubmissions / rescans", "O. Open Evidence",
        "S. Share Results with Meridian", "pds-core>=0.6.5,<0.7",
        "Quillan 0.10.6",
    ):
        assert expected in source

def test_active_data_contract_index_uses_v0106_release_boundary() -> None:
    source = _text("docs/data_contracts.md")
    assert "Quillan v0.10.6 requires `pds-core>=0.6.5,<0.7`" in source
    assert "quillan_academic_result_reader_v1" in source
    assert "The active v0.10.6 review model is standards-based:" in source
    assert "This index documents the active v0.10.6 contracts." in source

def test_unreleased_changelog_reflects_issue421_reader_boundary() -> None:
    source = _text("CHANGELOG.md")
    current = source.split("## 0.10.5 - 2026-10-03", maxsplit=1)[0]
    assert "quillan_academic_result_reader_v1" in current
    assert "#419" in current
    assert "pds-core>=0.6.5,<0.7" in current
