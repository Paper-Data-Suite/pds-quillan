"""Tests for read-only current review detail snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_snapshot import current_review_details_text
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID

TIMESTAMP = "2026-06-22T12:00:00+00:00"


def _review() -> dict[str, Any]:
    record = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )
    record["review_state"] = "feedback_composed"
    record["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 4,
            "met": False,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    record["review_units"] = [
        {
            "unit_id": "unit_0001",
            "sequence": 1,
            "label": "Paragraph 2",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "synthetic:W.A",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": None,
                    "rationale": "Relevant evidence, uneven explanation.",
                    "include_in_feedback": True,
                    "updated_at": TIMESTAMP,
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    record["overall_standard_ratings"] = [
        {
            "standard_id": "synthetic:W.A",
            "rating": 3,
            "rationale": "Relevant evidence, uneven explanation.",
            "include_in_feedback": True,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    record["feedback"]["standard_feedback"] = [
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": ["observation_0001"],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "reusable_focus_standard_comment",
                    "text": "The evidence is relevant, but explain the connection.",
                    "reusable_comment_id": "evidence_next_step",
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": TIMESTAMP,
                    "module_details": {
                        "comment_set_id": "synthetic_argument_focus_comments"
                    },
                }
            ],
            "module_details": {},
        }
    ]
    record["private_notes"] = [
        {
            "private_note_id": "note_0001",
            "text": "Needs conference about missing counterargument.",
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    return record


def test_current_review_details_handles_missing_record(tmp_path: Path) -> None:
    text = current_review_details_text(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    assert text.startswith("No review record exists yet for this student.")
    assert "Quillan" not in text
    assert "Current Review Details" not in text
    assert "No review record exists yet for this student." in text
    assert not list(tmp_path.rglob("review.json"))


def test_current_review_details_formats_saved_artifacts(tmp_path: Path) -> None:
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    write_review_record(path, _review())
    before = path.read_bytes()

    text = current_review_details_text(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    assert text.startswith(
        "Review record: exists\n"
        "Review: feedback composed\n"
        "Observations complete: yes\n"
        "Ratings complete: yes\n"
        "Feedback composed: yes\n"
        "Feedback export: not exported"
    )
    assert "Quillan" not in text
    assert "Current Review Details" not in text
    assert "Review record: exists" in text
    assert "Minimum paragraphs: not met" in text
    assert "Paragraph 2 (paragraph)" in text
    assert (
        "synthetic:W.A: applicable; evidence present: yes; "
        "include in feedback: yes"
    ) in text
    assert "rating not recorded" not in text
    assert "Include overall rating: yes" in text
    assert "Include overall rationale: yes" in text
    assert "Included observations: 1" in text
    assert "Comments: 1" in text
    assert "Included comments: 1" in text
    assert "Source: reusable Focus Standard comment" in text
    assert "Include in feedback: yes" in text
    assert "synthetic:W.A: 3" in text
    assert "Needs conference about missing counterargument." in text
    assert path.read_bytes() == before


def test_current_review_details_formats_empty_sections(tmp_path: Path) -> None:
    review = _review()
    for field in (
        "private_notes",
        "review_units",
        "overall_standard_ratings",
        "minimum_requirement_checks",
    ):
        review[field] = []
    review["feedback"]["standard_feedback"] = []
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    write_review_record(path, review)

    text = current_review_details_text(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    assert "No review units recorded." in text
    assert "No overall standard ratings recorded." in text
    assert "No feedback composed." in text
    assert "No private notes recorded." in text


def test_current_review_details_formats_returned_phases_as_not_applicable(
    tmp_path: Path,
) -> None:
    review = _review()
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Missing required work.",
        "updated_at": TIMESTAMP,
    }
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    write_review_record(path, review)

    text = current_review_details_text(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    assert "Review: returned without full standards review" in text
    assert (
        "Observations: not applicable - returned without full standards review"
    ) in text
    assert "Ratings: not applicable - returned without full standards review" in text
    assert (
        "Feedback composition: not applicable - returned without full standards review"
    ) in text
    assert "Observations complete: no" not in text
