"""Tests for read-only current review detail snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_snapshot import current_review_details_text
from tests.test_review_tags import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID

TIMESTAMP = "2026-06-22T12:00:00+00:00"


def _review() -> dict[str, Any]:
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
        "review_state": "in_progress",
        "notes": [
            {
                "note_id": "note_0001",
                "text": "Needs conference about missing counterargument.",
                "created_at": TIMESTAMP,
                "updated_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "tags": [
            {
                "tag_id": "tag_0001",
                "label": "Evidence needs more explanation",
                "polarity": "developing",
                "source": "custom",
                "page_number": 1,
                "location": {"type": "paragraph", "value": [3, 4]},
                "created_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "scores": [
            {
                "score_id": "score_0001",
                "criterion_id": "evidence",
                "label": "Evidence",
                "score": 3,
                "max_score": 4,
                "teacher_note": "Relevant evidence, uneven explanation.",
                "updated_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "comments": [
            {
                "comment_record_id": "comment_record_0001",
                "source": "comment_bank",
                "bank_id": "argument_writing",
                "comment_id": "evidence_needs_explanation",
                "label": "Evidence needs more explanation",
                "text": "The evidence is relevant, but explain the connection.",
                "include_in_feedback": True,
                "location": {"type": "paragraph", "value": 2},
                "created_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "requirement_checks": [
            {
                "requirement_check_id": "requirement_check_0001",
                "requirement_key": "paragraphs_min",
                "label": "Minimum paragraphs",
                "expected": 4,
                "met": False,
                "updated_at": TIMESTAMP,
                "module_details": {},
            }
        ],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


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

    assert text.startswith("Review record: exists\nReview state: in_progress")
    assert "Quillan" not in text
    assert "Current Review Details" not in text
    assert "Review record: exists" in text
    assert "Minimum paragraphs: not met" in text
    assert "[developing] Evidence needs more explanation" in text
    assert "Target: Page 1, paragraphs 3-4" in text
    assert "Target: Paragraph 2" in text
    assert "Include in feedback: yes" in text
    assert "Evidence: 3 / 4" in text
    assert "Needs conference about missing counterargument." in text
    assert path.read_bytes() == before


def test_current_review_details_formats_empty_sections(tmp_path: Path) -> None:
    review = _review()
    for field in ("notes", "tags", "scores", "comments", "requirement_checks"):
        review[field] = []
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    write_review_record(path, review)

    text = current_review_details_text(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    assert "No tags recorded." in text
    assert "No comments recorded." in text
    assert "No scores recorded." in text
    assert "No notes recorded." in text
    assert json.loads(path.read_text(encoding="utf-8")) == review
