"""Tests for student-facing Markdown feedback export."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    StandardsProfile,
    write_workspace_standards_library,
)

from quillan.feedback_export import (
    ExportedFeedback,
    FeedbackExportError,
    export_student_feedback,
    feedback_export_path,
)
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import submission_manifest_path, write_submission_manifest
from tests.test_review_scores import _write_manifest, _write_review
from tests.test_review_tags import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _manifest,
    _review,
)

TIMESTAMP = "2026-06-23T12:30:00+00:00"
STANDARD_DESCRIPTION = (
    "Cite a range of thorough textual evidence and make relevant connections "
    "to support analysis."
)


def _write_assignment(root: Path) -> None:
    assignment_dir = root / "classes" / CLASS_ID / "assignments" / ASSIGNMENT_ID
    assignment_dir.mkdir(parents=True, exist_ok=True)
    assignment = {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": ASSIGNMENT_ID,
        "title": "Synthetic Essay",
        "class_ids": [CLASS_ID],
        "writing_type": "argument",
        "student_prompt": "Write a synthetic argument.",
        "standards_profile_id": "synthetic_profile",
        "focus_standard_ids": ["synthetic:W.A"],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_2_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence.",
                }
            ],
        },
        "basic_requirements": {"paragraphs_min": 5},
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
    }
    (assignment_dir / "assignment.json").write_text(
        json.dumps(assignment), encoding="utf-8"
    )


def _write_standards_library(root: Path) -> None:
    write_workspace_standards_library(
        root,
        StandardsLibrary(
            standards=(
                StandardDefinition(
                    standard_id="synthetic:W.A",
                    code="RL.CR.9-10.1",
                    source="Synthetic standards",
                    short_name="Cite Textual Evidence",
                    description=STANDARD_DESCRIPTION,
                    available_modules=("quillan",),
                ),
            ),
            profiles=(
                StandardsProfile(
                    profile_id="synthetic_profile",
                    standards=("synthetic:W.A",),
                ),
            ),
        ),
    )


def test_exports_ordered_student_content_without_mutating_sources(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    review = _review("ready_for_export")
    review["private_notes"].append(
        {
            "private_note_id": "note_0001",
            "text": "PRIVATE TEACHER NOTE",
            "created_at": review["created_at"],
            "updated_at": review["updated_at"],
            "module_details": {},
        }
    )
    review["overall_standard_ratings"].extend(
        [
            {
                "standard_id": "synthetic:W.A",
                "rating": 3,
                "rationale": "Uses evidence.",
                "include_in_feedback": True,
                "updated_at": review["updated_at"],
                "module_details": {"private": "rating metadata"},
            },
            {
                "standard_id": "synthetic:W.B",
                "rating": 4,
                "rationale": None,
                "include_in_feedback": True,
                "updated_at": review["updated_at"],
                "module_details": {},
            },
        ]
    )
    review["feedback"]["standard_feedback"].append(
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": [],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "reusable_focus_standard_comment",
                    "text": "First student comment.\nWith a second line.",
                    "reusable_comment_id": "private_comment_id",
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {"private": "comment metadata"},
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
                {
                    "feedback_comment_id": "feedback_comment_0003",
                    "source": "custom",
                    "text": "Second student comment.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {},
                },
            ],
            "module_details": {},
        }
    )
    review_path = _write_review(tmp_path, review)
    evidence_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_00107_pg_001.pdf"
    )
    retained_path = (
        tmp_path / "routing" / "source_scans" / "scan_001" / "source_1.pdf"
    )
    evidence_path.parent.mkdir(parents=True)
    retained_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"evidence")
    retained_path.write_bytes(b"source")
    originals = {
        manifest_path: manifest_path.read_bytes(),
        review_path: review_path.read_bytes(),
        evidence_path: evidence_path.read_bytes(),
        retained_path: retained_path.read_bytes(),
    }

    result = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=TIMESTAMP,
    )

    expected_path = feedback_export_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    assert result == ExportedFeedback(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        review_record_path=review_path,
        review_record_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/review.json"
        ),
        feedback_path=expected_path,
        feedback_relative_path=(
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/exports/feedback.md"
        ),
        included_comment_count=2,
        score_count=2,
        created_at=TIMESTAMP,
        overwrote_existing=False,
    )
    content = expected_path.read_text(encoding="utf-8")
    assert f"Class: {CLASS_ID}" in content
    assert f"Assignment: {ASSIGNMENT_ID}" in content
    assert f"Student: {STUDENT_ID}" in content
    assert f"Generated: {TIMESTAMP}" in content
    assert content.index("### synthetic:W.A") < content.index("### synthetic:W.B")
    assert "Rating: 3" in content
    assert "Rationale:\nUses evidence." in content
    assert content.index(
        "- First student comment. With a second line."
    ) < content.index("- Second student comment.")
    for private_text in (
        "PRIVATE TEACHER NOTE",
        "EXCLUDED COMMENT",
        "private_comment_id",
        "comment metadata",
        "rating metadata",
    ):
        assert private_text not in content
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_empty_scores_and_comments_have_clear_messages(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    review = _review()
    _write_review(tmp_path, review)

    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    content = result.feedback_path.read_text(encoding="utf-8")
    assert "No Focus Standard feedback selected." in content


def test_groups_feedback_under_resolved_standard_with_full_description(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    _write_assignment(tmp_path)
    _write_standards_library(tmp_path)
    review = _review("feedback_composed")
    review["overall_standard_ratings"] = [
        {
            "standard_id": "synthetic:W.A",
            "rating": 1,
            "rationale": "Teacher rationale unchanged.",
            "include_in_feedback": True,
            "updated_at": review["updated_at"],
            "module_details": {},
        }
    ]
    review["feedback"]["standard_feedback"] = [
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": True,
            "include_overall_rationale": True,
            "included_observation_ids": [],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "custom",
                    "text": "Student comment unchanged.",
                    "reusable_comment_id": None,
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    ]
    _write_review(tmp_path, review)

    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    content = result.feedback_path.read_text(encoding="utf-8")

    heading = "### RL.CR.9-10.1 — Cite Textual Evidence"
    assert heading in content
    assert STANDARD_DESCRIPTION in content
    assert "Rating: 1 (Developing)" in content
    assert content.index(heading) < content.index(STANDARD_DESCRIPTION)
    assert content.index(STANDARD_DESCRIPTION) < content.index("Rating: 1 (Developing)")
    assert content.index("Rating: 1 (Developing)") < content.index("Feedback:")
    assert "synthetic:W.A" not in content
    assert "\n---\n" in content


def test_exports_returned_work_notice_without_standards_ratings(
    tmp_path: Path,
) -> None:
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
    review["overall_standard_ratings"] = [
        {
            "standard_id": "synthetic:W.A",
            "rating": 4,
            "rationale": "Should not render.",
            "include_in_feedback": True,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    _write_review(tmp_path, review)

    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    content = result.feedback_path.read_text(encoding="utf-8")
    assert content.startswith("# Returned for Revision")
    assert "returned without full standards review" in content
    assert "Minimum paragraphs" in content
    assert "Expected: 5" in content
    assert "Only three paragraphs were submitted." in content
    assert "Please revise to meet the assignment minimums." in content
    assert "No full standards ratings were completed" in content
    assert "synthetic:W.A: 4" not in content
    assert "No standards ratings recorded." not in content
    assert "tags" not in content
    assert "scores" not in content


def test_returned_work_export_requires_outcome_note_and_unmet_requirement(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_manifest(tmp_path)
    review = _review()
    review["review_state"] = "returned_without_full_review"
    review["minimum_requirement_checks"] = []
    review["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Return note.",
        "updated_at": TIMESTAMP,
    }
    _write_review(tmp_path, review)

    with pytest.raises(FeedbackExportError, match="marked not met"):
        export_student_feedback(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )

    review["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 5,
            "met": False,
            "updated_at": TIMESTAMP,
            "module_details": {},
        }
    ]
    review["minimum_requirement_outcome"]["teacher_note"] = None
    write_review_record(
        review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
        overwrite=True,
    )

    with pytest.raises(FeedbackExportError, match="teacher note"):
        export_student_feedback(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )


@pytest.mark.parametrize(
    ("record_kind", "message"),
    [("submission", "not review-ready yet"), ("review", "does not exist")],
)
def test_missing_record_is_rejected(
    tmp_path: Path, record_kind: str, message: str
) -> None:
    if record_kind == "review":
        _write_manifest(tmp_path)
    with pytest.raises(FeedbackExportError, match=message):
        export_student_feedback(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )


@pytest.mark.parametrize("record_kind", ["submission", "review"])
def test_invalid_record_is_rejected(tmp_path: Path, record_kind: str) -> None:
    manifest_path = _write_manifest(tmp_path)
    if record_kind == "submission":
        manifest_path.write_text("{", encoding="utf-8")
    else:
        review_path = feedback_export_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).parent.parent / "review.json"
        review_path.write_text("{", encoding="utf-8")
    with pytest.raises(FeedbackExportError, match="not valid JSON"):
        export_student_feedback(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )


@pytest.mark.parametrize(
    ("record_kind", "field", "value"),
    [
        ("submission", "class_id", "other_class"),
        ("submission", "assignment_id", "other_assignment"),
        ("submission", "student_id", "00108"),
        ("review", "class_id", "other_class"),
        ("review", "assignment_id", "other_assignment"),
        ("review", "student_id", "00108"),
    ],
)
def test_identity_mismatch_is_rejected(
    tmp_path: Path, record_kind: str, field: str, value: str
) -> None:
    manifest = _manifest()
    review = _review()
    if record_kind == "submission":
        manifest[field] = value
    else:
        review[field] = value
        review["submission_manifest_path"] = (
            f"classes/{review['class_id']}/assignments/"
            f"{review['assignment_id']}/submissions/{review['student_id']}/"
            "submission.json"
        )
        review["assignment_path"] = (
            f"classes/{review['class_id']}/assignments/{review['assignment_id']}/"
            "assignment.json"
        )
    write_submission_manifest(
        submission_manifest_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        manifest,
    )
    if record_kind == "review":
        _write_review(tmp_path, review)
    with pytest.raises(FeedbackExportError, match=field):
        export_student_feedback(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )


def test_overwrite_policy(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    review_path = _write_review(tmp_path, _review())
    original_review = review_path.read_bytes()
    first = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    first.feedback_path.write_text("manually edited", encoding="utf-8")

    with pytest.raises(FeedbackExportError, match="--overwrite"):
        export_student_feedback(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
        )
    assert first.feedback_path.read_text(encoding="utf-8") == "manually edited"

    second = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        overwrite=True,
        created_at=TIMESTAMP,
    )
    assert second.overwrote_existing is True
    assert second.feedback_path.read_text(encoding="utf-8").startswith("# Feedback")
    assert review_path.read_bytes() == original_review


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-time",
        "2026-06-23T12:30:00",
        datetime(2026, 6, 23, 12, 30),
        123,
    ],
)
def test_invalid_timestamp_is_rejected(
    tmp_path: Path, timestamp: object
) -> None:
    with pytest.raises(FeedbackExportError, match="timezone-aware"):
        export_student_feedback(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            created_at=timestamp,  # type: ignore[arg-type]
        )


def test_aware_datetime_is_normalized(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_review(tmp_path, copy.deepcopy(_review()))
    timestamp = datetime(2026, 6, 23, 12, 30, tzinfo=timezone.utc)
    result = export_student_feedback(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        created_at=timestamp,
    )
    assert result.created_at == timestamp.isoformat()


def test_source_comment_bank_is_not_read(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["feedback"]["standard_feedback"].append(
        {
            "standard_id": "synthetic:W.A",
            "include_overall_rating": False,
            "include_overall_rationale": False,
            "included_observation_ids": [],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "reusable_focus_standard_comment",
                    "text": "Existing selected language.",
                    "reusable_comment_id": "missing_comment",
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {},
                }
            ],
            "module_details": {},
        }
    )
    _write_review(tmp_path, review)
    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    assert "Existing selected language." in result.feedback_path.read_text(
        encoding="utf-8"
    )


def test_export_respects_composed_feedback_options_and_selected_observations(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["overall_standard_ratings"] = [
        {
            "standard_id": "synthetic:W.A",
            "rating": 3,
            "rationale": "Hidden rationale.",
            "include_in_feedback": True,
            "updated_at": review["updated_at"],
            "module_details": {},
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
            "include_overall_rationale": False,
            "included_observation_ids": ["observation_0001"],
            "comments": [
                {
                    "feedback_comment_id": "feedback_comment_0001",
                    "source": "reusable_focus_standard_comment",
                    "text": "Reusable snapshot text.",
                    "reusable_comment_id": "claim_next_step",
                    "save_for_reuse": False,
                    "include_in_feedback": True,
                    "created_at": review["created_at"],
                    "module_details": {
                        "comment_set_id": "synthetic_argument_focus_comments"
                    },
                },
                {
                    "feedback_comment_id": "feedback_comment_0002",
                    "source": "custom",
                    "text": "Excluded custom text.",
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
    _write_review(tmp_path, review)

    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    text = result.feedback_path.read_text(encoding="utf-8")

    assert "### synthetic:W.A" in text
    assert "Rating: 3" in text
    assert "Hidden rationale." not in text
    assert "Reusable snapshot text." in text
    assert "Excluded custom text." not in text
    assert "Selected observation." in text
