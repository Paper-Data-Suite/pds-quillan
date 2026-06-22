"""Tests for teacher-entered quick review notes."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import quillan.cli
from quillan.cli import main
from quillan.review_notes import (
    AddedReviewNote,
    ReviewNoteError,
    add_review_note,
)
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
ORIGINAL_TIMESTAMP = "2026-06-20T12:00:00+00:00"
FIRST_NOTE_TIMESTAMP = "2026-06-22T13:30:00-04:00"
SECOND_NOTE_TIMESTAMP = "2026-06-22T14:00:00-04:00"


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
                        "retained_source": {
                            "source_scan_id": "scan_001",
                            "source_filename": "source.pdf",
                            "source_sha256": "a" * 64,
                            "retained_source_path": (
                                "routing/source_scans/scan_001/source.pdf"
                            ),
                            "source_page_number": 1,
                        },
                        "module_details": {"source": "synthetic"},
                    }
                ],
            }
        ],
        "created_at": ORIGINAL_TIMESTAMP,
        "updated_at": ORIGINAL_TIMESTAMP,
        "module_details": {"teacher_workflow": "paper"},
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
                "created_at": FIRST_NOTE_TIMESTAMP,
                "updated_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "tags": [
            {
                "tag_id": "tag_0001",
                "label": "Clear claim",
                "polarity": "positive",
                "created_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "scores": [
            {
                "score_id": "score_0001",
                "criterion_id": "evidence",
                "label": "Evidence",
                "score": 3,
                "max_score": 4,
                "updated_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "comments": [
            {
                "comment_record_id": "comment_0001",
                "label": "Explain evidence",
                "text": "Explain how the evidence supports the claim.",
                "source": "custom",
                "include_in_feedback": True,
                "created_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {"preserve": True},
            }
        ],
        "created_at": FIRST_NOTE_TIMESTAMP,
        "updated_at": FIRST_NOTE_TIMESTAMP,
        "module_details": {"preserve": True},
    }


def _write_manifest(workspace: Path, manifest: dict[str, Any] | None = None) -> Path:
    path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    return write_submission_manifest(
        path, _manifest() if manifest is None else manifest
    )


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_review_record(path, review)


def test_creates_review_record_from_valid_submission_without_mutating_evidence(
    tmp_path: Path,
) -> None:
    manifest_path = _write_manifest(tmp_path)
    evidence_path = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "scans"
        / "response_00107_pg_001.pdf"
    )
    retained_path = tmp_path / "routing" / "source_scans" / "scan_001" / "source.pdf"
    evidence_path.parent.mkdir(parents=True)
    retained_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"routed evidence")
    retained_path.write_bytes(b"retained source")
    original_manifest = manifest_path.read_bytes()

    result = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "  Strong claim.  ",
        created_at=FIRST_NOTE_TIMESTAMP,
    )

    expected_relative_path = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/review.json"
    )
    assert result == AddedReviewNote(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        review_record_path=review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ),
        review_record_relative_path=expected_relative_path,
        note_id="note_0001",
        review_state="in_progress",
        created_at=FIRST_NOTE_TIMESTAMP,
    )
    written = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert written["submission_manifest_path"] == expected_relative_path.replace(
        "review.json", "submission.json"
    )
    assert written["review_state"] == "in_progress"
    assert written["tags"] == written["scores"] == written["comments"] == []
    assert written["created_at"] == written["updated_at"] == FIRST_NOTE_TIMESTAMP
    assert written["notes"] == [
        {
            "note_id": "note_0001",
            "text": "Strong claim.",
            "created_at": FIRST_NOTE_TIMESTAMP,
            "updated_at": FIRST_NOTE_TIMESTAMP,
            "module_details": {},
        }
    ]
    assert manifest_path.read_bytes() == original_manifest
    assert evidence_path.read_bytes() == b"routed evidence"
    assert retained_path.read_bytes() == b"retained source"


def test_appends_note_and_preserves_existing_review_sections(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    original = _review()
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
    assert written["notes"][:-1] == original["notes"]
    assert written["notes"][-1]["note_id"] == "note_0002"
    for field in ("tags", "scores", "comments", "module_details"):
        assert written[field] == original[field]
    assert written["created_at"] == original["created_at"]
    assert written["updated_at"] == SECOND_NOTE_TIMESTAMP
    assert written["review_state"] == "in_progress"


@pytest.mark.parametrize(
    ("initial_state", "expected_state"),
    [
        ("not_started", "in_progress"),
        ("in_progress", "in_progress"),
        ("ready_for_export", "ready_for_export"),
        ("exported", "exported"),
    ],
)
def test_append_uses_narrow_review_state_transition(
    tmp_path: Path,
    initial_state: str,
    expected_state: str,
) -> None:
    _write_manifest(tmp_path)
    _write_review(tmp_path, _review(initial_state))

    result = add_review_note(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        "State policy note.",
        created_at=SECOND_NOTE_TIMESTAMP,
    )

    assert result.review_state == expected_state


def test_note_id_skips_nonconforming_ids_and_uses_highest_sequence(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    review = _review()
    review["notes"].extend(
        [
            {
                "note_id": "custom-note",
                "text": "Custom identifier.",
                "created_at": FIRST_NOTE_TIMESTAMP,
                "updated_at": FIRST_NOTE_TIMESTAMP,
                "module_details": {},
            },
            {
                "note_id": "note_0004",
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
def test_blank_text_is_rejected_without_creating_review(
    tmp_path: Path, text: str
) -> None:
    _write_manifest(tmp_path)
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)

    with pytest.raises(ReviewNoteError, match="non-empty"):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            text,
            created_at=FIRST_NOTE_TIMESTAMP,
        )

    assert not path.exists()


def test_missing_submission_is_rejected_without_creating_review(
    tmp_path: Path,
) -> None:
    with pytest.raises(ReviewNoteError, match="does not exist"):
        add_review_note(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "A note.",
            created_at=FIRST_NOTE_TIMESTAMP,
        )

    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


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
            f"classes/{review['class_id']}/assignments/{review['assignment_id']}"
            f"/submissions/{review['student_id']}/submission.json"
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
        assert not review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).exists()


@pytest.mark.parametrize("record_kind", ["submission", "review"])
def test_invalid_existing_record_is_rejected_without_review_write(
    tmp_path: Path, record_kind: str
) -> None:
    manifest_path = _write_manifest(tmp_path)
    review_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
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

    assert (
        review_path.read_bytes() if review_path.exists() else None
    ) == original


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-time",
        "2026-06-22T13:30:00",
        datetime(2026, 6, 22, 13, 30),
        123,
    ],
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

    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


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


def test_cli_success_creates_note_and_prints_teacher_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_manifest(tmp_path)
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-note",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--text",
            "CLI note.",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Added teacher note:" in output
    assert f"Class: {CLASS_ID}" in output
    assert f"Assignment: {ASSIGNMENT_ID}" in output
    assert f"Student: {STUDENT_ID}" in output
    assert "Note: note_0001" in output
    assert "Review state: in_progress" in output
    assert (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/review.json"
    ) in output
    written = json.loads(
        review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ).read_text(encoding="utf-8")
    )
    assert written["notes"][0]["text"] == "CLI note."


@pytest.mark.parametrize("prepare_submission", [True, False])
def test_cli_handled_failure_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    prepare_submission: bool,
) -> None:
    if prepare_submission:
        _write_manifest(tmp_path)
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)
    text = " " if prepare_submission else "A note."

    result = main(
        [
            "add-note",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--text",
            text,
        ]
    )

    assert result == 1
    assert "Error: could not add teacher note:" in capsys.readouterr().out


def test_cli_append_preserves_existing_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_manifest(tmp_path)
    original = _review("ready_for_export")
    path = _write_review(tmp_path, copy.deepcopy(original))
    monkeypatch.setattr(quillan.cli, "resolve_workspace_root", lambda: tmp_path)

    assert main(
        [
            "add-note",
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            "--text",
            "CLI append.",
        ]
    ) == 0

    written = json.loads(path.read_text(encoding="utf-8"))
    for field in ("tags", "scores", "comments", "module_details"):
        assert written[field] == original[field]
    assert written["review_state"] == "ready_for_export"
