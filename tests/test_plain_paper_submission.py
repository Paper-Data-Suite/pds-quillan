from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from quillan.plain_paper_submission import (
    PlainPaperSubmissionError,
    create_plain_paper_submission,
)
from quillan.review_record import load_review_record
import quillan.review_menu as review_menu
from quillan.submission_manifest import load_submission_manifest
from quillan.submission_status import list_assignment_submission_status

CLASS_ID = "english10_p2"
ASSIGNMENT_ID = "literary_analysis"
STUDENT_ID = "stu_001"
TIMESTAMP = "2026-07-12T12:30:00-04:00"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    class_dir = tmp_path / "classes" / CLASS_ID
    assignment_dir = class_dir / "assignments" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)
    with (class_dir / "roster.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("class_id", "student_id", "last_name", "first_name", "period"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "class_id": CLASS_ID,
                "student_id": STUDENT_ID,
                "last_name": "Johnson",
                "first_name": "Mack",
                "period": "2",
            }
        )
    assignment = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Literary Analysis",
        "class_ids": [CLASS_ID],
        "writing_type": "analysis",
        "student_prompt": "Analyze the text.",
        "standards_profile_id": "ela",
        "focus_standard_ids": ["W.9"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "two_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Developing."}
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {"allow_return_without_full_review": True},
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment), encoding="utf-8"
    )
    return tmp_path


def test_creates_valid_evidence_less_manifest_and_empty_review(workspace: Path) -> None:
    created = create_plain_paper_submission(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    manifest = load_submission_manifest(created.submission_manifest_path)
    assert manifest == {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": None,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {
            "submission_entry_method": "plain_paper_manual",
            "physical_evidence_status": "teacher_has_external_plain_paper",
            "created_by_workflow": "plain_paper_submission",
        },
    }
    review = load_review_record(created.review_record_path)
    assert review["schema_version"] == "2"
    assert review["submission_manifest_path"] == created.submission_manifest_relative_path
    assert review["review_state"] == "not_started"
    assert review["review_units"] == []
    assert review["overall_standard_ratings"] == []
    assert review["feedback"]["standard_feedback"] == []
    assert review["private_notes"] == []
    assert review["module_details"] == {
        "review_entry_method": "plain_paper_manual",
        "created_by_workflow": "plain_paper_submission",
    }
    assert {path.name for path in created.submission_manifest_path.parent.iterdir()} == {
        "submission.json",
        "review.json",
    }


def test_rejects_student_not_in_roster(workspace: Path) -> None:
    with pytest.raises(PlainPaperSubmissionError, match="not in the roster"):
        create_plain_paper_submission(
            workspace, CLASS_ID, ASSIGNMENT_ID, "stu_999", created_at=TIMESTAMP
        )


def test_does_not_overwrite_existing_submission(workspace: Path) -> None:
    created = create_plain_paper_submission(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    original = created.submission_manifest_path.read_bytes()

    with pytest.raises(PlainPaperSubmissionError, match="already exists"):
        create_plain_paper_submission(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    assert created.submission_manifest_path.read_bytes() == original


def test_rejects_orphan_review_without_writing_manifest(workspace: Path) -> None:
    student_dir = (
        workspace
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
    )
    student_dir.mkdir(parents=True)
    review_path = student_dir / "review.json"
    review_path.write_text("existing review", encoding="utf-8")

    with pytest.raises(PlainPaperSubmissionError, match="without a submission"):
        create_plain_paper_submission(
            workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    assert review_path.read_text(encoding="utf-8") == "existing review"
    assert not (student_dir / "submission.json").exists()


def test_status_and_evidence_opening_are_teacher_friendly(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    create_plain_paper_submission(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    status = list_assignment_submission_status(workspace, CLASS_ID, ASSIGNMENT_ID)

    assert review_menu._student_status_label(status.student_statuses[0]) == (
        "plain-paper manual submission; no digital evidence"
    )
    review_menu._open_submission_evidence(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    output = capsys.readouterr().out
    assert "No digital evidence is attached" in output
    assert "Review the physical paper" in output
