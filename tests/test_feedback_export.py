"""Tests for student-facing Markdown feedback export."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from quillan.feedback_export import (
    ExportedFeedback,
    FeedbackExportError,
    export_student_feedback,
    feedback_export_path,
)
from tests.test_review_scores import _write_manifest, _write_review
from tests.test_review_tags import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _manifest,
    _review,
)

TIMESTAMP = "2026-06-23T12:30:00+00:00"


def test_exports_ordered_student_content_without_mutating_sources(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    review = _review("ready_for_export")
    review["notes"][0]["text"] = "PRIVATE TEACHER NOTE"
    review["tags"][0]["label"] = "PRIVATE STRUCTURED TAG"
    review["scores"][0]["teacher_note"] = "PRIVATE SCORE NOTE"
    review["scores"][0]["scale"] = "4 point"
    review["scores"].append(
        {
            "score_id": "score_0002",
            "criterion_id": "organization",
            "label": "Organization",
            "score": 3.5,
            "max_score": 4,
            "updated_at": review["updated_at"],
            "module_details": {"private": "score metadata"},
        }
    )
    review["comments"][0].update(
        {
            "text": "First student comment.\nWith a second line.",
            "source": "comment_bank",
            "bank_id": "private_bank",
            "comment_id": "private_comment_id",
            "standard_code": "PRIVATE.STANDARD",
            "module_details": {"private": "comment metadata"},
        }
    )
    review["comments"].extend(
        [
            {
                "comment_record_id": "comment_0002",
                "label": "Excluded",
                "text": "EXCLUDED COMMENT",
                "source": "custom",
                "include_in_feedback": False,
                "created_at": review["created_at"],
                "module_details": {},
            },
            {
                "comment_record_id": "comment_0003",
                "label": "Second",
                "text": "Second student comment.",
                "source": "custom",
                "include_in_feedback": True,
                "created_at": review["created_at"],
                "module_details": {},
            },
        ]
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
    assert content.index("- Evidence: 3 / 4 (4 point)") < content.index(
        "- Organization: 3.5 / 4"
    )
    assert content.index(
        "- First student comment. With a second line."
    ) < content.index("- Second student comment.")
    for private_text in (
        "PRIVATE TEACHER NOTE",
        "PRIVATE STRUCTURED TAG",
        "PRIVATE SCORE NOTE",
        "EXCLUDED COMMENT",
        "private_bank",
        "private_comment_id",
        "PRIVATE.STANDARD",
        "comment metadata",
        "score metadata",
    ):
        assert private_text not in content
    for path, original in originals.items():
        assert path.read_bytes() == original


def test_empty_scores_and_comments_have_clear_messages(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["scores"] = []
    review["comments"][0]["include_in_feedback"] = False
    _write_review(tmp_path, review)

    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )

    content = result.feedback_path.read_text(encoding="utf-8")
    assert "No scores recorded." in content
    assert "No feedback comments selected." in content


@pytest.mark.parametrize("record_kind", ["submission", "review"])
def test_missing_record_is_rejected(tmp_path: Path, record_kind: str) -> None:
    if record_kind == "review":
        _write_manifest(tmp_path)
    with pytest.raises(FeedbackExportError, match="does not exist"):
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
    _write_manifest(tmp_path, manifest)
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
    review["comments"][0].update(
        {
            "source": "comment_bank",
            "bank_id": "missing_bank",
            "comment_id": "missing_comment",
        }
    )
    _write_review(tmp_path, review)
    result = export_student_feedback(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, created_at=TIMESTAMP
    )
    assert "Existing selected language." in result.feedback_path.read_text(
        encoding="utf-8"
    )
