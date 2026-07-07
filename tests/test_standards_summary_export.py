"""Tests for teacher-facing assignment-local Focus Standard summary CSV export."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from quillan.standards_summary_export import (
    CSV_COLUMNS,
    ExportedStandardsSummary,
    StandardsSummaryExportError,
    export_standards_summary,
    standards_summary_export_path,
)
from tests.test_class_summary_export import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STANDARD_A,
    STANDARD_A_KEY,
    STANDARD_B,
    STANDARD_B_KEY,
    TIMESTAMP,
    _records,
    _student_dir,
    _write_assignment,
    _write_json,
    _write_roster,
)


def _write_review(
    workspace: Path,
    student_id: str,
    *,
    ratings: list[dict[str, Any]],
    returned_without_full_review: bool = False,
) -> tuple[Path, Path, dict[str, Any]]:
    manifest, review = _records(student_id)
    if returned_without_full_review:
        review["review_state"] = "returned_without_full_review"
        review["minimum_requirement_outcome"] = {
            "status": "returned_without_full_review",
            "returned_without_full_review": True,
            "teacher_note": None,
            "updated_at": review["updated_at"],
        }
    else:
        review["minimum_requirement_outcome"] = {
            "status": "met",
            "returned_without_full_review": False,
            "teacher_note": None,
            "updated_at": review["updated_at"],
        }
    review["overall_standard_ratings"] = ratings
    student_dir = _student_dir(workspace, student_id)
    return (
        _write_json(student_dir / "submission.json", manifest),
        _write_json(student_dir / "review.json", review),
        review,
    )


def _rating(
    standard_id: str,
    value: int,
    *,
    include_in_feedback: bool = True,
) -> dict[str, Any]:
    return {
        "standard_id": standard_id,
        "rating": value,
        "rationale": "Teacher-entered rating.",
        "include_in_feedback": include_in_feedback,
        "updated_at": TIMESTAMP,
        "module_details": {"debug": "must not leak"},
    }


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_focus_standard_rows_follow_assignment_order_and_count_ratings(
    tmp_path: Path,
) -> None:
    assignment_path = _write_assignment(tmp_path)
    roster_path = _write_roster(tmp_path)
    first_manifest, first_review_path, first_review = _write_review(
        tmp_path,
        "00100",
        ratings=[
            _rating(STANDARD_A, 3),
            _rating(STANDARD_B, 2, include_in_feedback=False),
        ],
    )
    second_manifest, second_review_path, _ = _write_review(
        tmp_path,
        "00200",
        ratings=[_rating(STANDARD_A, 2)],
    )
    returned_manifest, returned_review_path, _ = _write_review(
        tmp_path,
        "00300",
        ratings=[],
        returned_without_full_review=True,
    )
    outside_manifest, outside_review_path, outside_review = _write_review(
        tmp_path,
        "00400",
        ratings=[_rating("synthetic:outside", 1)],
    )
    pdf_path = _student_dir(tmp_path, "00100") / "exports" / "feedback.pdf"
    stale_pdf_path = _student_dir(tmp_path, "00200") / "exports" / "feedback.pdf"
    pdf_path.parent.mkdir()
    stale_pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF")
    stale_pdf_path.write_bytes(b"%PDF")
    first_review["exports"]["feedback_pdf"] = {
        "path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            "00100/exports/feedback.pdf"
        ),
        "generated_at": TIMESTAMP,
        "source_review_updated_at": first_review["updated_at"],
        "module_details": {},
    }
    _write_json(first_review_path, first_review)
    stale_review = json.loads(second_review_path.read_text(encoding="utf-8"))
    stale_review["exports"]["feedback_pdf"] = {
        "path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            "00200/exports/feedback.pdf"
        ),
        "generated_at": TIMESTAMP,
        "source_review_updated_at": "2026-06-20T12:30:00+00:00",
        "module_details": {},
    }
    _write_json(second_review_path, stale_review)
    originals = {
        assignment_path: assignment_path.read_bytes(),
        roster_path: roster_path.read_bytes(),
        first_manifest: first_manifest.read_bytes(),
        first_review_path: first_review_path.read_bytes(),
        second_manifest: second_manifest.read_bytes(),
        second_review_path: second_review_path.read_bytes(),
        returned_manifest: returned_manifest.read_bytes(),
        returned_review_path: returned_review_path.read_bytes(),
        outside_manifest: outside_manifest.read_bytes(),
        outside_review_path: outside_review_path.read_bytes(),
        pdf_path: pdf_path.read_bytes(),
        stale_pdf_path: stale_pdf_path.read_bytes(),
    }

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    expected_path = standards_summary_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    assert result == ExportedStandardsSummary(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        summary_path=expected_path,
        summary_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/exports/"
            "standards_summary.csv"
        ),
        row_count=2,
        standard_count=2,
        student_count=5,
        review_count=4,
        missing_review_count=0,
        invalid_review_count=0,
        missing_submission_count=1,
        invalid_submission_count=0,
        identity_mismatch_count=0,
        returned_without_full_review_count=1,
        created_at=TIMESTAMP,
        overwrote_existing=False,
    )
    with expected_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        assert tuple(reader.fieldnames or ()) == CSV_COLUMNS
        rows = list(reader)
    assert [row["standard_id"] for row in rows] == [STANDARD_A, STANDARD_B]
    assert [row["standard_column_key"] for row in rows] == [
        STANDARD_A_KEY,
        STANDARD_B_KEY,
    ]
    assert "tag_count" not in rows[0]
    assert "positive_tag_count" not in rows[0]

    first = rows[0]
    assert first["standards_profile_id"] == "synthetic_profile"
    assert first["focus_standard_order"] == "1"
    assert first["students_expected"] == "5"
    assert first["students_with_submissions"] == "4"
    assert first["students_with_valid_reviews"] == "4"
    assert first["students_reviewed_for_standard"] == "2"
    assert first["students_returned_without_full_review"] == "1"
    assert first["students_missing_rating"] == "1"
    assert first["students_with_rating_included_in_feedback"] == "2"
    assert first["feedback_pdf_present_count"] == "1"
    assert first["feedback_pdf_stale_count"] == "1"
    assert json.loads(first["rating_counts_json"]) == {"1": 0, "2": 1, "3": 1}
    assert "rating_for_non_assignment_standard" in first["warnings"]
    assert "standard_metadata_missing" in first["warnings"]

    second = rows[1]
    assert second["students_reviewed_for_standard"] == "1"
    assert second["students_missing_rating"] == "2"
    assert second["students_with_rating_included_in_feedback"] == "0"
    assert json.loads(second["rating_counts_json"]) == {"1": 0, "2": 1, "3": 0}
    csv_text = expected_path.read_text(encoding="utf-8")
    assert "Teacher-entered rating" not in csv_text
    assert "module_details" not in csv_text
    assert "synthetic:outside" not in csv_text
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_non_ready_counts_repeat_on_rows_and_do_not_abort(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_review(tmp_path, "00100", ratings=[_rating(STANDARD_A, 3)])
    _student_dir(tmp_path, "00200").mkdir(parents=True)
    manifest, _ = _records("00300")
    _write_json(_student_dir(tmp_path, "00300") / "submission.json", manifest)
    manifest, _ = _records("00400")
    _write_json(_student_dir(tmp_path, "00400") / "submission.json", manifest)
    (_student_dir(tmp_path, "00400") / "review.json").write_text(
        "{", encoding="utf-8"
    )
    _write_json(
        _student_dir(tmp_path, "00500") / "submission.json", {"invalid": True}
    )
    manifest, review = _records("other_student")
    _write_json(_student_dir(tmp_path, "00600") / "submission.json", manifest)
    _write_json(_student_dir(tmp_path, "00600") / "review.json", review)

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.review_count == 1
    assert result.missing_submission_count == 1
    assert result.missing_review_count == 1
    assert result.invalid_review_count == 1
    assert result.invalid_submission_count == 1
    assert result.identity_mismatch_count == 1
    row = _read_rows(result.summary_path)[0]
    assert row["students_with_valid_reviews"] == "1"
    assert row["students_with_submissions"] == "3"


def test_no_valid_reviews_writes_focus_standard_rows_with_counts(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _student_dir(tmp_path, "00100").mkdir(parents=True)

    result = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )

    assert result.row_count == result.standard_count == 2
    assert result.review_count == 0
    assert result.missing_submission_count == 1
    rows = _read_rows(result.summary_path)
    assert [row["standard_id"] for row in rows] == [STANDARD_A, STANDARD_B]
    assert all(row["students_reviewed_for_standard"] == "0" for row in rows)


def test_missing_assignment_config_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(StandardsSummaryExportError, match="assignment config"):
        export_standards_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )


def test_overwrite_replaces_only_the_derived_csv(tmp_path: Path) -> None:
    assignment_path = _write_assignment(tmp_path)
    manifest_path, review_path, _ = _write_review(
        tmp_path,
        "00100",
        ratings=[_rating(STANDARD_A, 3)],
    )
    originals = {
        assignment_path: assignment_path.read_bytes(),
        manifest_path: manifest_path.read_bytes(),
        review_path: review_path.read_bytes(),
    }
    first = export_standards_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
    )
    first.summary_path.write_text("manual edit", encoding="utf-8")

    with pytest.raises(StandardsSummaryExportError, match="--overwrite"):
        export_standards_summary(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, created_at=TIMESTAMP
        )
    assert first.summary_path.read_text(encoding="utf-8") == "manual edit"

    second = export_standards_summary(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        overwrite=True,
        created_at=TIMESTAMP,
    )
    assert second.overwrote_existing is True
    assert _read_rows(second.summary_path)[0]["standard_id"] == STANDARD_A
    for path, original in originals.items():
        assert path.read_bytes() == original


@pytest.mark.parametrize(
    "timestamp",
    ["not-a-time", "2026-06-23T13:00:00", datetime(2026, 6, 23, 13), 123],
)
def test_invalid_timestamp_is_rejected(
    tmp_path: Path, timestamp: object
) -> None:
    with pytest.raises(StandardsSummaryExportError, match="timezone-aware"):
        export_standards_summary(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            created_at=timestamp,  # type: ignore[arg-type]
        )
