"""Contract tests for Issue #414 installed selected-review acceptance."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_installed_selected_review_reads.py"


def test_installed_selected_review_acceptance_is_source_isolated_and_bounded() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for required in (
        'metadata.version("quillan")',
        'metadata.version("pds-core")',
        'for module_name in ("quillan", "pds_core"):',
        "_module_origin(module_name)",
        'STUDENT_IDS = tuple(f"{index:05d}" for index in range(1, 31))',
        '"assignment": 1',
        '"roster": 1',
        '"observations": 1',
        "list_assignment_submission_status = forbidden_legacy",
        "build_student_review_status = forbidden_legacy",
        "build_review_student_navigation = forbidden_legacy",
        "discover_scan_review_items = forbidden_scan",
        "_snapshot(workspace) != before",
    ):
        assert required in text
    assert "tests." not in text
    assert "pytest" not in text


def test_installed_selected_review_acceptance_requires_explicit_versions() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--expected-quillan-version"' in text
    assert '"--expected-core-version"' in text
    assert '"--repository"' in text
    assert '"--workspace"' in text
