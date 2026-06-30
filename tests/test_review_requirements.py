"""Tests for teacher-entered assignment requirement checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import ReviewRecordError, validate_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_requirements import (
    ReviewRequirementError,
    set_requirement_check,
)
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
FIRST_TIMESTAMP = "2026-06-29T12:00:00+00:00"
SECOND_TIMESTAMP = "2026-06-29T13:00:00+00:00"


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [
            {
                "page_number": 1,
                "page_state": "present",
                "selected_evidence_id": "evidence_001",
                "evidence": [
                    {
                        "evidence_id": "evidence_001",
                        "routed_evidence_path": (
                            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/"
                            "scans/response_00107_pg_001.pdf"
                        ),
                        "evidence_role": "selected",
                        "evidence_state": "active",
                        "duplicate_number": None,
                        "created_at": ORIGINAL_TIMESTAMP,
                        "retained_source": None,
                        "module_details": {},
                    }
                ],
            }
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {},
    }


def _review(state: str = "not_started") -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_review",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
        "submission_manifest_path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json"
        ),
        "review_state": state,
        "notes": [
            {
                "note_id": "note_0001",
                "text": "Existing note.",
                "created_at": ORIGINAL_TIMESTAMP,
                "updated_at": ORIGINAL_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "tags": [],
        "scores": [
            {
                "score_id": "score_0001",
                "criterion_id": "evidence",
                "label": "Evidence",
                "score": 3,
                "max_score": 4,
                "updated_at": ORIGINAL_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "comments": [],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {"preserve": True},
    }


def _write_manifest(workspace: Path) -> Path:
    return write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )


def test_creates_review_record_with_requirement_check(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    manifest_before = manifest_path.read_bytes()

    result = set_requirement_check(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="paragraphs_min",
        label="Minimum paragraphs",
        expected=5,
        met=True,
        updated_at=FIRST_TIMESTAMP,
    )

    review = json.loads(
        review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert result.requirement_check_id == "requirement_check_0001"
    assert result.was_created is True
    assert review["review_state"] == "in_progress"
    assert review["requirement_checks"] == [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 5,
            "met": True,
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]
    assert manifest_path.read_bytes() == manifest_before


def test_updates_existing_check_by_key_and_preserves_other_data(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    review = _review("ready_for_export")
    review["requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "required_elements:thesis_statement",
            "label": "Required element: thesis_statement",
            "expected": "thesis_statement",
            "met": True,
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {"preserve": True},
        }
    ]
    path = write_review_record(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )

    result = set_requirement_check(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="required_elements:thesis_statement",
        label="Required element: thesis_statement",
        expected="thesis_statement",
        met=False,
        teacher_note="Missing a clear thesis statement.",
        updated_at=SECOND_TIMESTAMP,
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.requirement_check_id == "requirement_check_0001"
    assert result.was_created is False
    assert written["review_state"] == "ready_for_export"
    assert written["notes"] == review["notes"]
    assert written["scores"] == review["scores"]
    assert written["module_details"] == review["module_details"]
    assert written["requirement_checks"] == [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "required_elements:thesis_statement",
            "label": "Required element: thesis_statement",
            "expected": "thesis_statement",
            "met": False,
            "updated_at": SECOND_TIMESTAMP,
            "module_details": {},
            "teacher_note": "Missing a clear thesis statement.",
        }
    ]


def test_existing_review_without_requirement_checks_remains_valid() -> None:
    validate_review_record(_review())


def test_requirement_check_validation_accepts_new_shape() -> None:
    review = _review()
    review["requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "word_count_max",
            "label": "Maximum word count",
            "expected": 800,
            "met": False,
            "teacher_note": "The submission is too long.",
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]

    validate_review_record(review)


def test_rejects_non_boolean_met(tmp_path: Path) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(ReviewRequirementError, match="met must be a boolean"):
        set_requirement_check(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            requirement_key="paragraphs_min",
            label="Minimum paragraphs",
            expected=5,
            met="true",  # type: ignore[arg-type]
            updated_at=FIRST_TIMESTAMP,
        )


def test_rejects_blank_requirement_key(tmp_path: Path) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(ReviewRequirementError, match="requirement_key"):
        set_requirement_check(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            requirement_key=" ",
            label="Minimum paragraphs",
            expected=5,
            met=True,
            updated_at=FIRST_TIMESTAMP,
        )


def test_validation_rejects_invalid_requirement_checks() -> None:
    review = _review()
    review["requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 5,
            "met": "yes",
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]

    with pytest.raises(ReviewRecordError, match="met.*boolean"):
        validate_review_record(review)


def test_missing_submission_manifest_errors_without_review_write(
    tmp_path: Path,
) -> None:
    with pytest.raises(ReviewRequirementError):
        set_requirement_check(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            requirement_key="paragraphs_min",
            label="Minimum paragraphs",
            expected=5,
            met=True,
            updated_at=FIRST_TIMESTAMP,
        )

    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
