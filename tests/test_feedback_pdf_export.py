"""Tests for student-facing PDF feedback export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

import quillan.feedback_export as feedback_export
from quillan.feedback_export import (
    ExportedFeedbackPdf,
    FeedbackExportError,
    export_student_feedback_pdf,
    feedback_export_path,
    feedback_pdf_export_path,
)
from quillan.review_record_paths import review_record_path
from tests.test_feedback_export import (
    STANDARD_DESCRIPTION,
    TIMESTAMP,
    _write_assignment,
    _write_standards_library,
)
from tests.review_test_support import _write_manifest, _write_review
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID, _review


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _write_roster(root: Path) -> None:
    class_dir = root / "classes" / CLASS_ID
    class_dir.mkdir(parents=True, exist_ok=True)
    (class_dir / "roster.csv").write_text(
        "class_id,student_id,last_name,first_name,period\n"
        f"{CLASS_ID},{STUDENT_ID},Rivera,Avery,3\n",
        encoding="utf-8",
    )


def _write_assignment_with_rating_labels(root: Path) -> None:
    _write_assignment(root)
    path = root / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID / "assignment.json"
    assignment = json.loads(path.read_text(encoding="utf-8"))
    assignment["rating_scale"]["levels"].append(
        {"value": 3, "label": "Meeting", "description": "Meets expectations."}
    )
    path.write_text(json.dumps(assignment), encoding="utf-8")


def _feedback_ready_review() -> dict[str, Any]:
    review = _review("feedback_composed")
    review["private_notes"].append(
        {
            "private_note_id": "private_note_0001",
            "text": "PRIVATE TEACHER NOTE",
            "created_at": review["created_at"],
            "updated_at": review["updated_at"],
            "module_details": {},
        }
    )
    review["overall_standard_ratings"] = [
        {
            "standard_id": "synthetic:W.A",
            "rating": 3,
            "rationale": "Uses evidence clearly.",
            "include_in_feedback": True,
            "updated_at": review["updated_at"],
            "module_details": {"debug": "rating metadata"},
        }
    ]
    review["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "synthetic:W.A",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": None,
                    "rationale": "Selected observation.",
                    "include_in_feedback": True,
                    "updated_at": review["updated_at"],
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    review["feedback"]["include_review_unit_observations"] = True
    review["feedback"]["standard_feedback"] = [
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": ["observation_0001"],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "reusable_focus_standard_comment",
                    "text": "Student-facing comment.",
                    "reusable_comment_id": "private_reusable_comment",
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {"comment_set_id": "private_set"},
                },
                {
                    "feedback_comment_id": "feedback_comment_0002",
                    "source": "custom",
                    "text": "EXCLUDED COMMENT",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": False,
                    "created_at": review["created_at"],
                    "module_details": {},
                },
            ],
            "module_details": {},
        }
    ]
    return review


def test_normal_pdf_export_creates_student_facing_pdf_and_metadata(
    tmp_path: Path,
) -> None:
    _write_roster(tmp_path)
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    review = _feedback_ready_review()
    source_review_updated_at = review["updated_at"]
    review_path = _write_review(tmp_path, review)

    result = export_student_feedback_pdf(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    expected_path = feedback_pdf_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    assert result == ExportedFeedbackPdf(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        student_display_name="Avery Rivera",
        assignment_title="Synthetic Essay",
        review_record_path=review_path,
        review_record_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/review.json"
        ),
        feedback_pdf_path=expected_path,
        feedback_pdf_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/exports/feedback.pdf"
        ),
        feedback_markdown_path=None,
        feedback_markdown_relative_path=None,
        included_standard_rating_count=1,
        included_comment_count=1,
        included_observation_count=1,
        created_at=TIMESTAMP,
        overwrote_existing=False,
    )
    text = _pdf_text(expected_path)
    for expected in (
        "Student Feedback",
        "Avery Rivera",
        STUDENT_ID,
        CLASS_ID,
        "Synthetic Essay",
        ASSIGNMENT_ID,
        TIMESTAMP,
        "synthetic:W.A",
        "Meeting",
        "Uses evidence clearly.",
        "Student-facing comment.",
        "Paragraph 1",
        "Selected observation.",
    ):
        assert expected in text
    for private in (
        "PRIVATE TEACHER NOTE",
        "private_notes",
        "module_details",
        "feedback_comment_id",
        "reusable_comment_id",
        "comment_set_id",
        "observation_id",
        "unit_id",
        "review.json",
        "private_reusable_comment",
        "private_set",
        "EXCLUDED COMMENT",
        "scores",
        "tags",
    ):
        assert private not in text

    review_after = json.loads(review_path.read_text(encoding="utf-8"))
    metadata = review_after["exports"]["feedback_pdf"]
    assert review_after["review_state"] == "exported"
    assert metadata == {
        "path": (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/exports/feedback.pdf"
        ),
        "generated_at": TIMESTAMP,
        "source_review_updated_at": source_review_updated_at,
        "module_details": {},
    }
    assert review_after["exports"]["feedback_markdown"] is None


def test_pdf_uses_resolved_standard_heading_and_full_description(tmp_path: Path) -> None:
    _write_roster(tmp_path)
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    _write_standards_library(tmp_path)
    _write_review(tmp_path, _feedback_ready_review())

    result = export_student_feedback_pdf(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    text = _pdf_text(result.feedback_pdf_path)

    assert "RL.CR.9-10.1" in text
    assert "Cite Textual Evidence" in text
    assert STANDARD_DESCRIPTION in text
    assert text.index("RL.CR.9-10.1") < text.index(STANDARD_DESCRIPTION)
    assert text.index(STANDARD_DESCRIPTION) < text.index("Rating:")
    assert text.index("Rating:") < text.index("Feedback:")
    assert text.index("Feedback:") < text.index("Review-unit observations:")
    assert "synthetic:W.A" not in text


def test_pdf_export_falls_back_to_student_id_without_roster(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    _write_review(tmp_path, _feedback_ready_review())

    result = export_student_feedback_pdf(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    assert result.student_display_name == STUDENT_ID
    assert STUDENT_ID in _pdf_text(result.feedback_pdf_path)


def test_pdf_overwrite_policy(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    _write_review(tmp_path, _feedback_ready_review())
    first = export_student_feedback_pdf(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    with pytest.raises(FeedbackExportError, match="--overwrite"):
        export_student_feedback_pdf(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    second = export_student_feedback_pdf(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        overwrite=True,
        created_at=TIMESTAMP,
    )
    assert second.overwrote_existing is True
    assert first.feedback_pdf_path.is_file()


def test_pdf_export_can_write_markdown_companion_and_metadata(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    _write_review(tmp_path, _feedback_ready_review())

    result = export_student_feedback_pdf(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        include_markdown_companion=True,
        created_at=TIMESTAMP,
    )

    assert result.feedback_markdown_path == feedback_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    assert result.feedback_markdown_path.is_file()
    review_after = json.loads(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).read_text(
            encoding="utf-8"
        )
    )
    assert review_after["exports"]["feedback_markdown"]["path"].endswith(
        "/exports/feedback.md"
    )


def test_returned_work_pdf_export(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    review = _review()
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 5,
            "met": False,
            "teacher_note": "Only three paragraphs were submitted.",
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Please revise to meet the assignment minimums.",
        "updated_at": TIMESTAMP,
    }
    _write_review(tmp_path, review)

    result = export_student_feedback_pdf(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    text = _pdf_text(result.feedback_pdf_path)
    assert "Returned for Revision" in text
    assert "Minimum paragraphs" in text
    assert "Expected: 5" in text
    assert "Only three paragraphs were submitted." in text
    assert "Please revise to meet the assignment minimums." in text
    assert "No full Focus Standard ratings were completed" in text


def test_no_metadata_update_occurs_if_pdf_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path)
    _write_assignment_with_rating_labels(tmp_path)
    review_path = _write_review(tmp_path, _feedback_ready_review())
    before = review_path.read_text(encoding="utf-8")

    def fail_render(_path: Path, _feedback: object) -> None:
        raise OSError("simulated PDF failure")

    monkeypatch.setattr(feedback_export, "_render_pdf_to_path", fail_render)

    with pytest.raises(FeedbackExportError, match="simulated PDF failure"):
        export_student_feedback_pdf(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    assert review_path.read_text(encoding="utf-8") == before
    assert not feedback_pdf_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()
