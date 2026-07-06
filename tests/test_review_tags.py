"""Tests for legacy tag helper fail-closed behavior under v2 reviews."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path
from quillan.review_tags import ReviewTagError, add_review_tag

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
TIMESTAMP = "2026-06-22T13:30:00+00:00"


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


def _review(state: str = "ready_for_export", student_id: str = STUDENT_ID) -> dict[str, Any]:
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
    from quillan.submission_manifest_paths import (
        submission_manifest_path,
        write_submission_manifest,
    )

    return write_submission_manifest(
        submission_manifest_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID),
        _manifest(),
    )


def test_add_review_tag_fails_closed_without_creating_v1_record(tmp_path: Path) -> None:
    with pytest.raises(ReviewTagError, match="schema version 2"):
        add_review_tag(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            label="Clear claim",
            polarity="positive",
        )

    assert not review_record_path(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
    ).exists()
