"""Tests for teacher-entered v2 minimum requirement checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import ReviewRecordError, build_empty_review_record, validate_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_requirements import (
    ReviewRequirementError,
    set_minimum_requirement_outcome,
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
    record = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=ORIGINAL_TIMESTAMP,
    )
    record["review_state"] = state
    record["module_details"] = {"preserve": True}
    return record


def _write_manifest(workspace: Path) -> Path:
    return write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )


def test_creates_v2_review_record_with_minimum_requirement_check(
    tmp_path: Path,
) -> None:
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
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert result.requirement_check_id == "requirement_check_0001"
    assert result.was_created is True
    assert review["schema_version"] == "2"
    assert review["review_state"] == "requirements_checked"
    assert "requirement_checks" not in review
    assert review["minimum_requirement_checks"] == [
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
    review["minimum_requirement_checks"] = [
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
    assert written["module_details"] == review["module_details"]
    assert written["minimum_requirement_checks"] == [
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


def test_requirement_check_validation_accepts_v2_shape() -> None:
    review = _review()
    review["minimum_requirement_checks"] = [
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


def test_validation_rejects_invalid_minimum_requirement_checks() -> None:
    review = _review()
    review["minimum_requirement_checks"] = [
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

    assert not review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


def test_sets_minimum_requirement_outcome_to_met_and_preserves_data(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    review = _review("requirements_checked")
    review["created_at"] = ORIGINAL_TIMESTAMP
    review["updated_at"] = FIRST_TIMESTAMP
    review["minimum_requirement_checks"] = [
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
    review["private_notes"] = [
        {
            "private_note_id": "note_0001",
            "text": "Preserve me.",
            "created_at": FIRST_TIMESTAMP,
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]
    path = write_review_record(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )

    result = set_minimum_requirement_outcome(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        status="met",
        teacher_note="Ready for standards review.",
        updated_at=SECOND_TIMESTAMP,
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.status == "met"
    assert result.returned_without_full_review is False
    assert result.review_state == "requirements_checked"
    assert written["schema_version"] == "2"
    assert written["review_state"] == "requirements_checked"
    assert written["created_at"] == ORIGINAL_TIMESTAMP
    assert written["updated_at"] == SECOND_TIMESTAMP
    assert written["minimum_requirement_checks"] == review["minimum_requirement_checks"]
    assert written["private_notes"] == review["private_notes"]
    assert written["minimum_requirement_outcome"] == {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": "Ready for standards review.",
        "updated_at": SECOND_TIMESTAMP,
    }
    for legacy_field in ("notes", "tags", "scores", "comments", "requirement_checks"):
        assert legacy_field not in written


def test_sets_minimum_requirement_outcome_to_unmet_continue_review(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)

    result = set_minimum_requirement_outcome(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        status="unmet_continue_review",
        updated_at=FIRST_TIMESTAMP,
    )

    written = json.loads(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert result.status == "unmet_continue_review"
    assert written["review_state"] == "requirements_checked"
    assert written["minimum_requirement_outcome"]["teacher_note"] is None


def test_sets_minimum_requirement_outcome_to_returned_without_full_review(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    set_requirement_check(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        requirement_key="paragraphs_min",
        label="Minimum paragraphs",
        expected=5,
        met=False,
        teacher_note="Only three paragraphs.",
        updated_at=FIRST_TIMESTAMP,
    )

    result = set_minimum_requirement_outcome(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        status="returned_without_full_review",
        teacher_note="Revise to meet the paragraph minimum.",
        updated_at=SECOND_TIMESTAMP,
        allow_return_without_full_review=True,
    )

    written = json.loads(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert result.returned_without_full_review is True
    assert written["review_state"] == "returned_without_full_review"
    assert written["minimum_requirement_outcome"] == {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Revise to meet the paragraph minimum.",
        "updated_at": SECOND_TIMESTAMP,
    }
    assert len(written["minimum_requirement_checks"]) == 1


def test_returned_without_full_review_requires_note_policy_and_unmet_check(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(ReviewRequirementError, match="teacher_note"):
        set_minimum_requirement_outcome(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            status="returned_without_full_review",
            teacher_note=" ",
            updated_at=FIRST_TIMESTAMP,
            allow_return_without_full_review=True,
        )

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

    with pytest.raises(ReviewRequirementError, match="does not allow"):
        set_minimum_requirement_outcome(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            status="returned_without_full_review",
            teacher_note="Revise first.",
            updated_at=SECOND_TIMESTAMP,
            allow_return_without_full_review=False,
        )

    with pytest.raises(ReviewRequirementError, match="marked not met"):
        set_minimum_requirement_outcome(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            status="returned_without_full_review",
            teacher_note="Revise first.",
            updated_at=SECOND_TIMESTAMP,
            allow_return_without_full_review=True,
        )
