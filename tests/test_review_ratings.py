"""Tests for overall Focus Standard rating helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_ratings import (
    ReviewRatingError,
    mark_overall_ratings_complete,
    set_overall_standard_rating,
    summarize_focus_standard_observations,
)
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
FIRST_TIMESTAMP = "2026-07-02T12:00:00+00:00"
SECOND_TIMESTAMP = "2026-07-02T13:00:00+00:00"
THIRD_TIMESTAMP = "2026-07-02T14:00:00+00:00"


def _assignment() -> dict[str, Any]:
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write an argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["njsls-ela:W.1", "njsls-ela:L.2"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {"value": 1, "label": "Developing", "description": "Limited."},
                {"value": 2, "label": "Secure", "description": "Clear."},
            ],
        },
        "basic_requirements": {"paragraphs_min": 1},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
    }


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


def _write_workspace(root: Path, review: dict[str, Any] | None = None) -> None:
    assignment_dir = root / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True)
    (assignment_dir / "assignment.json").write_text(
        json.dumps(_assignment()),
        encoding="utf-8",
    )
    write_submission_manifest(
        submission_manifest_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )
    if review is None:
        review = _review_record()
    write_review_record(
        review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )


def _review_record() -> dict[str, Any]:
    review = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=ORIGINAL_TIMESTAMP,
    )
    review["review_state"] = "observations_complete"
    review["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 1,
            "met": True,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {},
        }
    ]
    review["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": ORIGINAL_TIMESTAMP,
    }
    review["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "njsls-ela:W.1",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": None,
                    "rationale": "Clear claim.",
                    "include_in_feedback": True,
                    "updated_at": ORIGINAL_TIMESTAMP,
                    "module_details": {},
                },
                {
                    "observation_id": "observation_0002",
                    "standard_id": "njsls-ela:L.2",
                    "applicable": False,
                    "evidence_present": None,
                    "rating": None,
                    "rationale": "Not applicable here.",
                    "include_in_feedback": False,
                    "updated_at": ORIGINAL_TIMESTAMP,
                    "module_details": {},
                },
            ],
            "module_details": {},
        },
        {
            "unit_id": "paragraph_2",
            "sequence": 2,
            "label": "Paragraph 2",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0003",
                    "standard_id": "njsls-ela:W.1",
                    "applicable": True,
                    "evidence_present": False,
                    "rating": None,
                    "rationale": "Evidence is attempted but missing.",
                    "include_in_feedback": False,
                    "updated_at": ORIGINAL_TIMESTAMP,
                    "module_details": {},
                }
            ],
            "module_details": {},
        },
    ]
    review["feedback"]["standard_feedback"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": ["observation_0001"],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Explain the evidence connection.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": ORIGINAL_TIMESTAMP,
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    review["private_notes"] = [
        {
            "private_note_id": "note_0001",
            "text": "Conference note.",
            "created_at": ORIGINAL_TIMESTAMP,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {},
        }
    ]
    return review


def _read_review(root: Path) -> dict[str, Any]:
    return json.loads(
        review_record_path(root, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )


def test_set_overall_rating_creates_record_and_preserves_review_data(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)
    before = _read_review(tmp_path)

    result = set_overall_standard_rating(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        rating=2,
        rationale="Clear claim with uneven explanation.",
        include_in_feedback=True,
        updated_at=FIRST_TIMESTAMP,
    )

    review = _read_review(tmp_path)
    assert result.was_created is True
    assert result.rating_label == "Secure"
    assert result.review_state == "observations_complete"
    assert review["overall_standard_ratings"] == [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 2,
            "rationale": "Clear claim with uneven explanation.",
            "include_in_feedback": True,
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]
    assert review["updated_at"] == FIRST_TIMESTAMP
    assert review["created_at"] == before["created_at"]
    for field in (
        "minimum_requirement_checks",
        "minimum_requirement_outcome",
        "review_units",
        "feedback",
        "private_notes",
        "exports",
    ):
        assert review[field] == before[field]
    for legacy_field in ("scores", "tags", "comments", "notes"):
        assert legacy_field not in review


def test_set_overall_rating_updates_existing_standard_only(tmp_path: Path) -> None:
    review = _review_record()
    review["overall_standard_ratings"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 1,
            "rationale": "Earlier rationale.",
            "include_in_feedback": False,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {},
        },
        {
            "standard_id": "njsls-ela:L.2",
            "rating": 2,
            "rationale": None,
            "include_in_feedback": True,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {},
        },
    ]
    _write_workspace(tmp_path, review)

    result = set_overall_standard_rating(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        standard_id="njsls-ela:W.1",
        rating=2,
        rationale=" ",
        include_in_feedback=True,
        updated_at=SECOND_TIMESTAMP,
    )

    ratings = _read_review(tmp_path)["overall_standard_ratings"]
    assert result.was_created is False
    assert ratings[0]["standard_id"] == "njsls-ela:W.1"
    assert ratings[0]["rating"] == 2
    assert ratings[0]["rationale"] is None
    assert ratings[0]["include_in_feedback"] is True
    assert ratings[1] == review["overall_standard_ratings"][1]


def test_set_overall_rating_validates_assignment_scale_and_standard(
    tmp_path: Path,
) -> None:
    _write_workspace(tmp_path)

    with pytest.raises(ReviewRatingError, match="not a Focus Standard"):
        set_overall_standard_rating(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            standard_id="njsls-ela:MISSING",
            rating=2,
            rationale=None,
            include_in_feedback=True,
            updated_at=FIRST_TIMESTAMP,
        )
    with pytest.raises(ReviewRatingError, match="rating"):
        set_overall_standard_rating(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            standard_id="njsls-ela:W.1",
            rating=3,
            rationale=None,
            include_in_feedback=True,
            updated_at=FIRST_TIMESTAMP,
        )
    with pytest.raises(ReviewRatingError, match="include_in_feedback"):
        set_overall_standard_rating(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            standard_id="njsls-ela:W.1",
            rating=2,
            rationale=None,
            include_in_feedback=1,  # type: ignore[arg-type]
            updated_at=FIRST_TIMESTAMP,
        )


def test_focus_standard_summary_groups_counts_and_current_rating(
    tmp_path: Path,
) -> None:
    review = _review_record()
    review["overall_standard_ratings"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 2,
            "rationale": "Overall rationale.",
            "include_in_feedback": True,
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_workspace(tmp_path, review)

    summaries = summarize_focus_standard_observations(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )

    first = summaries[0]
    assert first.standard_id == "njsls-ela:W.1"
    assert first.total_review_units == 2
    assert first.observation_count == 2
    assert first.applicable_count == 2
    assert first.not_applicable_count == 0
    assert first.evidence_present_count == 1
    assert first.evidence_missing_count == 1
    assert first.included_for_feedback_count == 1
    assert [detail.unit_label for detail in first.details] == [
        "Paragraph 1",
        "Paragraph 2",
    ]
    assert first.current_rating == 2
    assert first.current_rationale == "Overall rationale."
    assert "recommended" not in repr(first).lower()


def test_mark_overall_ratings_complete_reports_missing_and_preserves_data(
    tmp_path: Path,
) -> None:
    review = _review_record()
    review["overall_standard_ratings"] = [
        {
            "standard_id": "njsls-ela:W.1",
            "rating": 2,
            "rationale": None,
            "include_in_feedback": True,
            "updated_at": FIRST_TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_workspace(tmp_path, review)
    before = copy.deepcopy(_read_review(tmp_path))

    result = mark_overall_ratings_complete(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        updated_at=THIRD_TIMESTAMP,
    )

    after = _read_review(tmp_path)
    assert result.review_state == "ratings_complete"
    assert result.focus_standard_count == 2
    assert result.rating_count == 1
    assert result.missing_rating_count == 1
    assert after["review_state"] == "ratings_complete"
    assert after["updated_at"] == THIRD_TIMESTAMP
    for field in (
        "minimum_requirement_checks",
        "minimum_requirement_outcome",
        "review_units",
        "overall_standard_ratings",
        "feedback",
        "private_notes",
        "exports",
        "created_at",
    ):
        assert after[field] == before[field]


def test_returned_without_full_review_records_reject_rating_changes(
    tmp_path: Path,
) -> None:
    review = _review_record()
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Missing required work.",
        "updated_at": ORIGINAL_TIMESTAMP,
    }
    _write_workspace(tmp_path, review)

    with pytest.raises(ReviewRatingError, match="returned without full standards review"):
        set_overall_standard_rating(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            standard_id="njsls-ela:W.1",
            rating=2,
            rationale=None,
            include_in_feedback=True,
            updated_at=FIRST_TIMESTAMP,
        )
    with pytest.raises(ReviewRatingError, match="returned without full standards review"):
        mark_overall_ratings_complete(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            updated_at=FIRST_TIMESTAMP,
        )
