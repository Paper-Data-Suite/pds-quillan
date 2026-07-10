"""Tests for the compact student performance summary export."""

from __future__ import annotations

import csv
from pathlib import Path

from quillan.student_performance_summary_export import (
    MISSING_RATING,
    export_student_performance_summary,
)
from tests.test_class_summary_export import (
    STANDARD_A,
    STANDARD_B,
    _student_dir,
    _write_assignment,
    _write_json,
    _write_records,
    _write_roster,
)
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID


def test_compact_rows_preserve_missing_and_returned_ratings(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _, reviewed_path, reviewed = _write_records(tmp_path, "00100")
    reviewed["minimum_requirement_outcome"]["status"] = "met"
    reviewed["minimum_requirement_outcome"]["updated_at"] = reviewed["updated_at"]
    reviewed["overall_standard_ratings"] = [
        {
            "standard_id": STANDARD_A,
            "rating": 3,
            "rationale": "Synthetic rationale.",
            "include_in_feedback": True,
            "updated_at": reviewed["updated_at"],
            "module_details": {},
        }
    ]
    _write_json(reviewed_path, reviewed)
    _, returned_path, returned = _write_records(tmp_path, "00200")
    returned["minimum_requirement_outcome"].update(
        {
            "status": "returned_without_full_review",
            "returned_without_full_review": True,
            "updated_at": returned["updated_at"],
        }
    )
    returned["review_state"] = "returned_without_full_review"
    _write_json(returned_path, returned)
    _student_dir(tmp_path, "00300").mkdir(parents=True)
    missing_review_manifest, _, _ = _write_records(tmp_path, "00400")
    missing_review_manifest.parent.joinpath("review.json").unlink()
    invalid_submission_dir = _student_dir(tmp_path, "00500")
    invalid_submission_dir.mkdir(parents=True)
    invalid_submission_dir.joinpath("submission.json").write_text(
        "not json", encoding="utf-8"
    )
    _, invalid_review_path, _ = _write_records(tmp_path, "00600")
    invalid_review_path.write_text("not json", encoding="utf-8")

    result = export_student_performance_summary(
        tmp_path, CLASS_ID, ASSIGNMENT_ID
    )
    with result.summary_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames or []
        rows = {row["student_id"]: row for row in reader}

    assert fields == [
        "student_id",
        "student_display_name",
        "review_status",
        "minimum_requirements",
        STANDARD_A,
        STANDARD_B,
        "notes_flags",
    ]
    assert rows["00100"][STANDARD_A] == "3 - Secure"
    assert rows["00100"][STANDARD_B] == MISSING_RATING
    assert rows["00200"]["review_status"] == "Returned"
    assert rows["00200"][STANDARD_A] == MISSING_RATING
    assert "returned_without_full_review" in rows["00200"]["notes_flags"]
    assert rows["00900"]["review_status"] == "Not submitted"
    assert "missing_submission" in rows["00900"]["notes_flags"]
    assert rows["00900"][STANDARD_A] == ""
    assert rows["00300"]["review_status"] == "Not submitted"
    assert "unrostered_submission" in rows["00300"]["notes_flags"]
    assert rows["00300"][STANDARD_A] == ""
    assert rows["00400"]["review_status"] == "Not reviewed"
    assert "missing_review" in rows["00400"]["notes_flags"]
    assert rows["00400"][STANDARD_A] == ""
    assert rows["00500"]["review_status"] == "Invalid submission"
    assert "invalid_submission" in rows["00500"]["notes_flags"]
    assert rows["00500"][STANDARD_A] == ""
    assert rows["00600"]["review_status"] == "Invalid review"
    assert "invalid_review" in rows["00600"]["notes_flags"]
    assert rows["00600"][STANDARD_A] == ""
    forbidden = {"submission_manifest_path", "review_record_path", "roster_status"}
    assert forbidden.isdisjoint(fields)
