"""Issue #417 Slice 4 tests for the assignment review PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

import quillan.assignment_reporting_snapshot as snapshot_module
from quillan.assignment_reporting_snapshot import build_assignment_reporting_snapshot
from quillan.assignment_review_report_export import (
    AssignmentReviewReportExportError,
    export_assignment_review_report_from_snapshot,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_assignment_reporting_snapshot_issue417 import _prepare_workspace
from tests.test_class_summary_export import (
    TIMESTAMP,
    _write_json,
    _write_records,
)


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_assignment_review_pdf_is_readable_complete_and_privacy_bounded(
    tmp_path: Path,
) -> None:
    _prepare_workspace(tmp_path)

    _, extra_review_path, extra_review = _write_records(tmp_path, "00300")
    extra_review["review_state"] = "observations_in_progress"
    extra_review["minimum_requirement_outcome"]["status"] = "met"
    extra_review["minimum_requirement_outcome"]["updated_at"] = (
        extra_review["updated_at"]
    )
    extra_review["overall_standard_ratings"] = []
    extra_review["private_notes"] = [
        {
            "private_note_id": "private_0001",
            "text": "PRIVATE TEACHER NOTE MUST NOT LEAK",
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_json(extra_review_path, extra_review)

    source_files = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    result = export_assignment_review_report_from_snapshot(
        snapshot,
        created_at=TIMESTAMP,
    )

    text = _pdf_text(result.report_path)
    for expected in (
        "Assignment Review Report",
        "Synthetic Essay",
        ASSIGNMENT_ID,
        CLASS_ID,
        "Argument",
        TIMESTAMP,
        "Review and Completion Overview",
        "Rostered students",
        "Unrostered submissions",
        "Focus Standard Performance",
        "W.NW.11-12.3.D",
        "Narrative Writing",
        "3 - Secure",
        "100.0%",
        "Rated denominator: 1",
        "Student Detail",
        "Avery Rivera",
        "Attention and Data Quality",
    ):
        assert expected in text

    for private in (
        "PRIVATE TEACHER NOTE MUST NOT LEAK",
        "Teacher-entered rationale.",
        "Write a synthetic argument.",
        "private_notes",
        "module_details",
        "submission.json",
        "review.json",
        "retained_source",
    ):
        assert private not in text

    assert len(PdfReader(str(result.report_path)).pages) >= 2
    for path, original in source_files.items():
        assert path.read_bytes() == original


def test_assignment_review_pdf_uses_snapshot_without_source_reread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_workspace(tmp_path)
    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    def fail_if_reloaded(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("canonical reporting source was reloaded after snapshot")

    monkeypatch.setattr(snapshot_module, "load_assignment", fail_if_reloaded)
    monkeypatch.setattr(snapshot_module, "discover_students", fail_if_reloaded)
    monkeypatch.setattr(snapshot_module, "load_student_record", fail_if_reloaded)
    monkeypatch.setattr(
        snapshot_module,
        "load_workspace_standards_library",
        fail_if_reloaded,
    )
    monkeypatch.setattr(snapshot_module, "feedback_status", fail_if_reloaded)

    result = export_assignment_review_report_from_snapshot(
        snapshot,
        created_at=TIMESTAMP,
    )
    assert "Assignment Review Report" in _pdf_text(result.report_path)


def test_assignment_review_pdf_is_create_only_then_explicitly_overwritable(
    tmp_path: Path,
) -> None:
    _prepare_workspace(tmp_path)
    snapshot = build_assignment_reporting_snapshot(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    first = export_assignment_review_report_from_snapshot(
        snapshot,
        created_at=TIMESTAMP,
    )
    original = first.report_path.read_bytes()

    with pytest.raises(AssignmentReviewReportExportError, match="--overwrite"):
        export_assignment_review_report_from_snapshot(
            snapshot,
            created_at="2026-10-03T01:00:00+00:00",
        )
    assert first.report_path.read_bytes() == original

    second = export_assignment_review_report_from_snapshot(
        snapshot,
        overwrite=True,
        created_at="2026-10-03T01:00:00+00:00",
    )
    assert second.overwrote_existing is True
    assert "2026-10-03T01:00:00+00:00" in _pdf_text(second.report_path)
