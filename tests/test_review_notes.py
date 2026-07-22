"""Tests for teacher-entered private notes on v2 review records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from quillan.review_notes import AddedReviewNote, ReviewNoteError, add_review_note
from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from tests.review_test_support import _write_assignment

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
FIRST_NOTE_TIMESTAMP = "2026-06-22T13:30:00-04:00"
SECOND_NOTE_TIMESTAMP = "2026-06-22T14:00:00-04:00"


@pytest.fixture(autouse=True)
def canonical_assignment(tmp_path: Path) -> None:
    _write_assignment(tmp_path)


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
                            f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/"
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
        created_at=FIRST_NOTE_TIMESTAMP,
    )
    record["review_state"] = state
    record["private_notes"] = [
        {
            "private_note_id": "note_0001",
            "text": "Existing note.",
            "created_at": FIRST_NOTE_TIMESTAMP,
            "updated_at": FIRST_NOTE_TIMESTAMP,
            "module_details": {"preserve": True},
        }
    ]
    record["module_details"] = {"preserve": True}
    return record


def _write_manifest(workspace: Path, manifest: dict[str, Any] | None = None) -> Path:
    return write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest() if manifest is None else manifest,
    )


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    return write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )


def test_creates_v2_review_record_with_private_note(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    manifest_before = manifest_path.read_bytes()

    result = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "  Strong claim.  ",
        created_at=FIRST_NOTE_TIMESTAMP,
    )

    expected_relative_path = (
        f"classes/{CLASS_ID}/modules/quillan/work/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/review.json"
    )
    assert result == AddedReviewNote(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        review_record_path=review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review_record_relative_path=expected_relative_path,
        note_id="note_0001",
        review_state="not_started",
        created_at=FIRST_NOTE_TIMESTAMP,
    )
    written = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "2"
    assert "notes" not in written
    assert written["private_notes"] == [
        {
            "private_note_id": "note_0001",
            "text": "Strong claim.",
            "created_at": FIRST_NOTE_TIMESTAMP,
            "updated_at": FIRST_NOTE_TIMESTAMP,
            "module_details": {},
        }
    ]
    assert written["created_at"] == written["updated_at"] == FIRST_NOTE_TIMESTAMP
    assert manifest_path.read_bytes() == manifest_before


def test_appends_private_note_and_preserves_existing_v2_sections(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    original = _review("ready_for_export")
    path = _write_review(tmp_path, original)

    result = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "Second note.",
        created_at=SECOND_NOTE_TIMESTAMP,
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.note_id == "note_0002"
    assert written["private_notes"][:-1] == original["private_notes"]
    assert written["private_notes"][-1]["private_note_id"] == "note_0002"
    assert written["module_details"] == original["module_details"]
    assert written["created_at"] == original["created_at"]
    assert written["updated_at"] == SECOND_NOTE_TIMESTAMP
    assert written["review_state"] == "ready_for_export"


def test_note_id_skips_nonconforming_ids_and_uses_highest_sequence(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["private_notes"].extend(
        [
            {
                "private_note_id": "custom-note",
                "text": "Custom identifier.",
                "created_at": FIRST_NOTE_TIMESTAMP,
                "updated_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {},
            },
            {
                "private_note_id": "note_0004",
                "text": "Later sequence.",
                "created_at": FIRST_NOTE_TIMESTAMP,
                "updated_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {},
            },
        ]
    )
    _write_review(tmp_path, review)

    result = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "Next sequence.",
        created_at=SECOND_NOTE_TIMESTAMP,
    )

    assert result.note_id == "note_0005"


@pytest.mark.parametrize("text", ["", " \t "])
def test_blank_text_is_rejected_without_creating_review(tmp_path: Path, text: str) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(ReviewNoteError, match="non-empty"):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            text,
            created_at=FIRST_NOTE_TIMESTAMP,
        )

    assert not review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


def test_missing_submission_is_rejected_without_creating_review(tmp_path: Path) -> None:
    with pytest.raises(ReviewNoteError, match="not review-ready yet"):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "A note.",
            created_at=FIRST_NOTE_TIMESTAMP,
        )

    assert not review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


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
def test_identity_mismatch_is_rejected_without_writing(
    tmp_path: Path,
    record_kind: str,
    field: str,
    value: str,
) -> None:
    manifest = _manifest()
    review = _review()
    if record_kind == "submission":
        manifest[field] = value
    else:
        review[field] = value
        review["submission_manifest_path"] = (
            f"classes/{review['class_id']}/modules/quillan/work/{review['assignment_id']}"
            f"/submissions/{review['student_id']}/submission.json"
        )
        review["assignment_path"] = (
            f"classes/{review['class_id']}/modules/quillan/work/{review['assignment_id']}/assignment.json"
        )
    _write_manifest(tmp_path, manifest)
    review_path = _write_review(tmp_path, review) if record_kind == "review" else None
    original = review_path.read_bytes() if review_path else None

    with pytest.raises(ReviewNoteError, match=field):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "A note.",
            created_at=SECOND_NOTE_TIMESTAMP,
        )

    if review_path:
        assert review_path.read_bytes() == original
    else:
        assert not review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


@pytest.mark.parametrize("record_kind", ["submission", "review"])
def test_invalid_existing_record_is_rejected_without_review_write(
    tmp_path: Path, record_kind: str
) -> None:
    manifest_path = _write_manifest(tmp_path)
    review_path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    if record_kind == "submission":
        manifest_path.write_text("{", encoding="utf-8")
    else:
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text("{", encoding="utf-8")
    original = review_path.read_bytes() if review_path.exists() else None

    with pytest.raises(ReviewNoteError, match="not valid JSON"):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "A note.",
            created_at=SECOND_NOTE_TIMESTAMP,
        )

    assert (review_path.read_bytes() if review_path.exists() else None) == original


@pytest.mark.parametrize(
    "timestamp",
    ["not-a-time", "2026-06-22T13:30:00", datetime(2026, 6, 22, 13, 30), 123],
)
def test_invalid_timestamp_is_rejected_without_writing(
    tmp_path: Path, timestamp: object
) -> None:
    _write_manifest(tmp_path)

    with pytest.raises(ReviewNoteError, match="timezone-aware"):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "A note.",
            created_at=timestamp,  # type: ignore[arg-type]
        )

    assert not review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID).exists()


def test_timezone_aware_datetime_is_normalized(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    timestamp = datetime(2026, 6, 22, 17, 30, tzinfo=timezone.utc)

    result = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "A note.",
        created_at=timestamp,
    )

    assert result.created_at == timestamp.isoformat()
