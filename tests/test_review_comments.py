"""Tests for selecting shared-bank comments into review records."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from quillan.review_comments import ReviewCommentError, add_review_comment
from quillan.review_record_paths import review_record_path
from tests.test_review_scores import _write_manifest, _write_review
from tests.test_review_tags import (
    ASSIGNMENT_ID,
    CLASS_ID,
    STUDENT_ID,
    _review,
)

BANK_ID = "general_writing_synthetic"
TIMESTAMP = "2026-06-22T15:00:00+00:00"
EXAMPLE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "comment_banks"
    / f"{BANK_ID}.json"
)


def _bank() -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    )


def _write_bank(workspace: Path, bank: dict[str, Any] | None = None) -> Path:
    path = workspace / "shared" / "comment_banks" / f"{BANK_ID}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_bank() if bank is None else bank), encoding="utf-8")
    return path


def _add(workspace: Path, **overrides: Any) -> Any:
    arguments: dict[str, Any] = {
        "bank_id": BANK_ID,
        "comment_id": "evidence_needs_explanation",
        "created_at": TIMESTAMP,
    }
    arguments.update(overrides)
    return add_review_comment(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID, **arguments
    )


def test_creates_snapshotted_comment_without_mutating_sources(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    bank_path = _write_bank(tmp_path)
    manifest_before = manifest_path.read_bytes()
    bank_before = bank_path.read_bytes()

    result = _add(tmp_path)

    written = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert result.comment_record_id == "comment_record_0001"
    assert result.include_in_feedback is True
    assert written["review_state"] == "in_progress"
    assert written["created_at"] == written["updated_at"] == TIMESTAMP
    assert written["notes"] == written["tags"] == written["scores"] == []
    assert written["comments"] == [
        {
            "comment_record_id": "comment_record_0001",
            "source": "comment_bank",
            "bank_id": BANK_ID,
            "comment_id": "evidence_needs_explanation",
            "label": "Evidence needs explanation",
            "text": (
                "Your evidence is relevant, but explain more clearly how it "
                "supports your central idea."
            ),
            "include_in_feedback": True,
            "created_at": TIMESTAMP,
            "module_details": {},
            "standard_id": "njsls-ela:W.AW.11-12.1",
        }
    ]
    assert manifest_path.read_bytes() == manifest_before
    assert bank_path.read_bytes() == bank_before


@pytest.mark.parametrize(
    ("override", "expected"),
    [(True, True), (False, False), (None, True)],
)
def test_feedback_inclusion_policy(
    tmp_path: Path, override: bool | None, expected: bool
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    result = _add(tmp_path, include_in_feedback=override)
    assert result.include_in_feedback is expected


def test_standard_selection_policy(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    bank = _bank()
    bank["comments"][0]["standard_ids"] = []
    bank["comments"][3]["standard_ids"] = ["A", "B"]
    _write_bank(tmp_path, bank)

    first = _add(tmp_path, comment_id="focus_is_clear")
    second = _add(tmp_path, comment_id="sentence_boundaries_need_review")
    third = _add(
        tmp_path,
        comment_id="sentence_boundaries_need_review",
        standard_id="B",
    )
    comments = json.loads(
        third.review_record_path.read_text(encoding="utf-8")
    )["comments"]
    assert "standard_id" not in comments[0]
    assert "standard_id" not in comments[1]
    assert comments[2]["standard_id"] == "B"
    assert first.comment_record_id == "comment_record_0001"
    assert second.comment_record_id == "comment_record_0002"


def test_invalid_standard_and_teacher_only_comment_are_rejected(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    with pytest.raises(ReviewCommentError, match="not available"):
        _add(tmp_path, standard_id="missing")
    with pytest.raises(ReviewCommentError, match="not student-facing"):
        _add(tmp_path, comment_id="teacher_review_follow_up")
    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


def test_append_preserves_review_and_uses_highest_conforming_id(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    original = _review("ready_for_export")
    original["comments"].extend(
        [
            {
                "comment_record_id": "custom-id",
                "label": "Custom",
                "text": "Preserve me.",
                "source": "custom",
                "include_in_feedback": False,
                "created_at": original["created_at"],
                "module_details": {"preserve": True},
            },
            {
                "comment_record_id": "comment_record_0004",
                "label": "Older",
                "text": "Also preserve me.",
                "source": "custom",
                "include_in_feedback": True,
                "created_at": original["created_at"],
                "module_details": {},
            },
        ]
    )
    path = _write_review(tmp_path, copy.deepcopy(original))

    result = _add(tmp_path)

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.comment_record_id == "comment_record_0005"
    assert result.review_state == "ready_for_export"
    assert written["comments"][:-1] == original["comments"]
    for field in ("notes", "tags", "scores", "module_details", "created_at"):
        assert written[field] == original[field]
    assert written["updated_at"] == TIMESTAMP


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("not_started", "in_progress"),
        ("in_progress", "in_progress"),
        ("ready_for_export", "ready_for_export"),
        ("exported", "exported"),
    ],
)
def test_narrow_review_state_transition(
    tmp_path: Path, state: str, expected: str
) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    _write_review(tmp_path, _review(state))
    assert _add(tmp_path).review_state == expected


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("missing_bank", "not found"),
        ("invalid_bank", "not valid JSON"),
        ("missing_comment", "has no comment"),
        ("missing_submission", "not review-ready yet"),
        ("invalid_review", "not valid JSON"),
    ],
)
def test_failures_do_not_mutate_existing_review(
    tmp_path: Path, setup: str, message: str
) -> None:
    if setup != "missing_submission":
        _write_manifest(tmp_path)
    if setup != "missing_bank":
        bank_path = _write_bank(tmp_path)
        if setup == "invalid_bank":
            bank_path.write_text("{", encoding="utf-8")
    path = review_record_path(tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    if setup == "invalid_review":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
    before = path.read_bytes() if path.exists() else None
    overrides = {"comment_id": "missing"} if setup == "missing_comment" else {}

    with pytest.raises(ReviewCommentError, match=message):
        _add(tmp_path, **overrides)
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize(
    "timestamp",
    ["bad", "2026-06-22T15:00:00", datetime(2026, 6, 22, 15), 123],
)
def test_invalid_timestamp_is_rejected(tmp_path: Path, timestamp: object) -> None:
    _write_manifest(tmp_path)
    _write_bank(tmp_path)
    with pytest.raises(ReviewCommentError, match="timezone-aware"):
        _add(tmp_path, created_at=timestamp)
