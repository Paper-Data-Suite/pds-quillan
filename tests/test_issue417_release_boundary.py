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


def test_release_docs_use_final_released_core_064_identity() -> None:
    process = (ROOT / "docs" / "release_process.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "release_checklist.md").read_text(
        encoding="utf-8"
    )
    for text in (process, checklist):
        assert "48cea9317f2967bdc0f2d4c14349a56677c7c3f8211f0f33978ccb1a1c75859b" in text
        assert "152d1c65064c4f8fe55249ff2ca3379d7c4d6ccb" in text
        assert "released Core 0.6.4" in text
        assert "pds-core>=0.6.2,<0.7" in text


def test_reporting_contract_matches_implemented_consolidated_pdf() -> None:
    text = (ROOT / "docs" / "assignment_reporting_contract.md").read_text(
        encoding="utf-8"
    )
    assert "assignment_review_report.pdf" in text
    assert "/exports/class_summary.pdf" not in text
    assert "/exports/standards_summary.pdf" not in text
    assert "explicit rated-student denominator" in text
    assert "Reports must not convert ratings into percentages or grades." not in text


def test_ci_operations_wheel_matrix_includes_released_core_064() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    matrix = text.split("operations-wheel-qualification:", 1)[1]
    assert 'core: "0.6.4"' in matrix
    assert "releases/download/v{version}/{filename}" in matrix
    assert "--core-version ${{ matrix.core }}" in matrix
    harness = (
        ROOT / "scripts" / "run_operations_wheel_acceptance.py"
    ).read_text(encoding="utf-8")
    assert 'choices=("0.6.2", "0.6.3", "0.6.4")' in harness


def test_candidate_validator_runs_issue417_before_core064_specific_regression() -> None:
    text = (ROOT / "scripts" / "validate_release_candidate.ps1").read_text(
        encoding="utf-8"
    )
    issue417 = text.index("Installed Issue #417 reporting/review Core $CoreVersion")
    issue416 = text.index("if ($CoreVersion -eq '0.6.4')")
    assert issue417 < issue416
    assert "verify_installed_issue417_acceptance.py" in text
    assert "'--expected-quillan-version', '0.10.5'" in text
    assert "READY FOR #417 RELEASE AUTHORIZATION: NO" in text
    assert "READY FOR #416 RELEASE AUTHORIZATION" not in text
