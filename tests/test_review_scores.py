"""Tests for legacy score helper fail-closed behavior under v2 reviews."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import build_empty_review_record
from quillan.review_record_paths import review_record_path
from quillan.review_record_paths import write_review_record
from quillan.review_scores import ReviewScoreError, set_review_score
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
TIMESTAMP = "2026-06-22T14:20:00+00:00"


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
        "pages": [],
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "module_details": {},
    }


def _review(state: str = "ready_for_export") -> dict[str, Any]:
    record = build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
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


def test_set_review_score_fails_closed_without_creating_v1_record(tmp_path: Path) -> None:
    with pytest.raises(ReviewScoreError, match="schema version 2"):
        set_review_score(
            tmp_path,
            "english12_p3_synthetic",
            "essay_01_synthetic",
            "00107",
            criterion_id="evidence",
            label="Evidence",
            score=3,
            max_score=4,
        )

    assert not review_record_path(
        tmp_path,
        "english12_p3_synthetic",
        "essay_01_synthetic",
        "00107",
    ).exists()
