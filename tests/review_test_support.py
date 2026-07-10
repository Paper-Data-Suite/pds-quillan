"""Shared synthetic review records used by active export and snapshot tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path, write_review_record
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
TIMESTAMP = "2026-06-22T14:20:00+00:00"


def _manifest(student_id: str = STUDENT_ID) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "module": "quillan",
        "record_type": "submission_manifest",
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": student_id,
        "expected_pages": 1,
        "submission_state": "unreviewed",
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _review(
    state: str = "ready_for_export", student_id: str = STUDENT_ID
) -> dict[str, Any]:
    record = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=student_id,
        created_at=TIMESTAMP,
    )
    record["review_state"] = state
    record["updated_at"] = TIMESTAMP
    return record


def _write_manifest(workspace: Path) -> Path:
    return write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    return write_review_record(
        review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        review,
    )
