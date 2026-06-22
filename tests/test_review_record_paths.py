"""Tests for canonical review record paths and safe writing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_record_paths import (
    ReviewRecordPathError,
    review_record_dir,
    review_record_path,
    write_review_record,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"


def _record() -> dict[str, Any]:
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
        "review_state": "not_started",
        "notes": [],
        "tags": [],
        "scores": [],
        "comments": [],
        "created_at": "2026-06-22T00:00:00+00:00",
        "updated_at": "2026-06-22T00:00:00+00:00",
        "module_details": {"teacher_note": "Café"},
    }


def test_review_record_paths_use_canonical_quillan_layout(tmp_path: Path) -> None:
    expected_dir = (
        tmp_path
        / "classes"
        / CLASS_ID
        / "assignments"
        / ASSIGNMENT_ID
        / "submissions"
        / STUDENT_ID
    )

    result_dir = review_record_dir(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    result_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )

    assert result_dir == expected_dir
    assert result_path == expected_dir / "review.json"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_id", "../unsafe"),
        ("assignment_id", "bad assignment"),
        ("student_id", ""),
    ],
)
def test_review_record_paths_reject_invalid_identifiers(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    identifiers = {
        "class_id": CLASS_ID,
        "assignment_id": ASSIGNMENT_ID,
        "student_id": STUDENT_ID,
    }
    identifiers[field] = value

    with pytest.raises(ReviewRecordPathError, match=field):
        review_record_dir(tmp_path, **identifiers)


def test_valid_record_is_written_readably_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "review.json"
    record = _record()

    result = write_review_record(path, record)

    raw = path.read_bytes()
    assert result == path
    assert path.parent.is_dir()
    assert raw.endswith(b"\n")
    assert b'\n  "schema_version"' in raw
    assert "Café" in raw.decode("utf-8")
    assert load_review_record(path) == record


def test_invalid_record_is_rejected_before_filesystem_write(tmp_path: Path) -> None:
    path = tmp_path / "not-created" / "review.json"
    record = _record()
    del record["schema_version"]

    with pytest.raises(ReviewRecordError, match="schema_version"):
        write_review_record(path, record)

    assert not path.exists()
    assert not path.parent.exists()


def test_existing_record_is_not_overwritten_by_default(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    path.write_text("original\n", encoding="utf-8")

    with pytest.raises(ReviewRecordPathError, match="already exists"):
        write_review_record(path, _record())

    assert path.read_text(encoding="utf-8") == "original\n"


def test_existing_record_is_replaced_only_when_overwrite_enabled(
    tmp_path: Path,
) -> None:
    path = tmp_path / "review.json"
    path.write_text("original\n", encoding="utf-8")
    record = _record()
    record["review_state"] = "in_progress"

    result = write_review_record(path, record, overwrite=True)

    assert result == path
    assert json.loads(path.read_text(encoding="utf-8")) == record


def test_parent_path_that_is_a_file_raises(tmp_path: Path) -> None:
    parent = tmp_path / "review-parent"
    parent.write_text("not a directory", encoding="utf-8")
    path = parent / "review.json"

    with pytest.raises(
        ReviewRecordPathError,
        match="Could not create review record directory",
    ):
        write_review_record(path, _record())

    assert parent.read_text(encoding="utf-8") == "not a directory"
