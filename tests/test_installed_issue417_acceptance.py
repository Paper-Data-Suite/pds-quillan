"""Regression coverage for the installed Issue #417 acceptance program."""

from __future__ import annotations

from pathlib import Path

from scripts.verify_installed_issue417_acceptance import (
    _exercise_navigation,
    _exercise_reporting,
    _prepare_workspace,
)

ROOT = Path(__file__).resolve().parents[1]


def test_issue417_acceptance_fixture_exercises_reporting_and_navigation(
    tmp_path: Path,
) -> None:
    _prepare_workspace(tmp_path)
    reporting = _exercise_reporting(tmp_path)
    navigation = _exercise_navigation()

    assert reporting["csv_utf8_bom"] is True
    assert reporting["unicode_round_trip"] is True
    assert reporting["pdf_readable"] is True
    assert reporting["json_inventory_complete"] is True
    assert reporting["canonical_source_mutations"] == 0
    assert reporting["private_content_leaks"] == 0
    assert navigation["numbered_back_entries"] == 0
    assert navigation["shared_navigation_rendering"] == [
        "B. Back",
        "M. Main Menu",
        "Q. Quit",
    ]


def test_issue417_installed_program_uses_only_production_modules() -> None:
    source = (
        ROOT / "scripts" / "verify_installed_issue417_acceptance.py"
    ).read_text(encoding="utf-8")

    assert "tests." not in source
    assert "export_assignment_reporting_packet" in source
    assert "assignment_results_manifest" in source
    assert "PdfReader" in source
    assert "BOM" in source
    assert "ReturnToMainMenu" in source
    assert "QuitQuillan" in source
    assert 'metadata.version("quillan")' in source
    assert 'metadata.version("pds-core")' in source
    assert "is_relative_to(repository)" in source


def test_release_validator_runs_issue417_acceptance_at_every_core_endpoint() -> None:
    source = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )

    assert "verify_installed_issue417_acceptance.py" in source
    assert "Installed Issue #417 reporting/review Core $CoreVersion" in source
    assert "'--expected-quillan-version', '0.10.5'" in source
    assert "'--expected-core-version', $CoreVersion" in source
    assert source.index("Installed Issue #417 reporting/review Core $CoreVersion") < (
        source.index("if ($CoreVersion -eq '0.6.4')")
    )
