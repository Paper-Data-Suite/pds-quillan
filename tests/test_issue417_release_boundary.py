"""Issue #417 Quillan 0.10.5 release-boundary contracts."""

from __future__ import annotations

from pathlib import Path

from scripts.inspect_release_artifacts import REQUIRED_PACKAGE_FILES

ROOT = Path(__file__).resolve().parents[1]


def test_reporting_runtime_modules_are_required_in_release_artifacts() -> None:
    for relative in (
        "quillan/assignment_reporting_snapshot.py",
        "quillan/assignment_reporting_packet.py",
        "quillan/assignment_review_report_export.py",
        "quillan/assignment_results_manifest_export.py",
        "quillan/report_csv.py",
    ):
        assert relative in REQUIRED_PACKAGE_FILES


def test_issue417_historical_evidence_and_new_core_are_independent() -> None:
    historical = (ROOT / "docs/v0.10.5_installed_reporting_review_acceptance.md").read_text(encoding="utf-8")
    current = (ROOT / "docs/release_process.md").read_text(encoding="utf-8")
    assert "released Core 0.6.4" in historical
    assert "pds-core>=0.6.5,<0.7" in current

def test_reporting_contract_matches_implemented_consolidated_pdf() -> None:
    text = (ROOT / "docs" / "assignment_reporting_contract.md").read_text(
        encoding="utf-8"
    )
    assert "assignment_review_report.pdf" in text
    assert "/exports/class_summary.pdf" not in text
    assert "/exports/standards_summary.pdf" not in text
    assert "explicit rated-student denominator" in text
    assert "Reports must not convert ratings into percentages or grades." not in text


def test_current_ci_runs_one_core_065_wheel_gate() -> None:
    current = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "installed-wheel:" in current
    assert "--expected-core-version 0.6.5" in current

def test_historical_issue417_is_not_repeated_in_current_candidate() -> None:
    current = (ROOT / "scripts/validate_release_candidate.ps1").read_text(encoding="utf-8")
    assert "verify_installed_issue417_acceptance.py" not in current
    assert "verify_installed_issue419_recovery.py" in current
    assert "verify_installed_issue421_reader_contract.py" in current
