"""Tests for teacher-entered criterion review scores."""

from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record_paths import review_record_path, write_review_record
from quillan.review_scores import (
    ReviewScoreError,
    UpdatedReviewScore,
    set_review_score,
)
from quillan.submission_manifest_paths import (
    submission_manifest_path,
    write_submission_manifest,
)
from tests.test_review_tags import (
    ASSIGNMENT_ID,
    CLASS_ID,
    ORIGINAL_TIMESTAMP,
    STUDENT_ID,
    _manifest,
    _review,
)

FIRST_SCORE_TIMESTAMP = "2026-06-22T14:20:00-04:00"
SECOND_SCORE_TIMESTAMP = "2026-06-22T15:10:00-04:00"


def _write_manifest(
    workspace: Path, manifest: dict[str, Any] | None = None
) -> Path:
    path = submission_manifest_path(
        workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    return write_submission_manifest(
        path, _manifest() if manifest is None else manifest
    )


def _write_review(workspace: Path, review: dict[str, Any]) -> Path:
    path = review_record_path(workspace, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID)
    return write_review_record(path, review)


def test_creates_score_without_mutating_submission_or_evidence(
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
    retained_path = (
        tmp_path / "routing" / "source_scans" / "scan_001" / "source_1.pdf"
    )
    evidence_path.parent.mkdir(parents=True)
    retained_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"routed evidence")
    retained_path.write_bytes(b"retained source")
    original_manifest = manifest_path.read_bytes()

    result = set_review_score(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        criterion_id=" evidence ",
        label=" Evidence ",
        score=3,
        max_score=4,
        scale=" 4_point ",
        teacher_note=" Relevant but not fully explained. ",
        updated_at=FIRST_SCORE_TIMESTAMP,
    )

    expected_relative_path = (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
        f"{STUDENT_ID}/review.json"
    )
    assert result == UpdatedReviewScore(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        review_record_path=review_record_path(
            tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
        ),
        review_record_relative_path=expected_relative_path,
        score_id="score_0001",
        criterion_id="evidence",
        score=3,
        max_score=4,
        review_state="in_progress",
        updated_at=FIRST_SCORE_TIMESTAMP,
        was_created=True,
    )
    written = json.loads(result.review_record_path.read_text(encoding="utf-8"))
    assert written["class_id"] == CLASS_ID
    assert written["assignment_id"] == ASSIGNMENT_ID
    assert written["student_id"] == STUDENT_ID
    assert written["submission_manifest_path"] == expected_relative_path.replace(
        "review.json", "submission.json"
    )
    assert written["review_state"] == "in_progress"
    assert written["notes"] == written["tags"] == written["comments"] == []
    assert written["created_at"] == written["updated_at"] == FIRST_SCORE_TIMESTAMP
    assert written["scores"] == [
        {
            "score_id": "score_0001",
            "criterion_id": "evidence",
            "label": "Evidence",
            "score": 3,
            "max_score": 4,
            "updated_at": FIRST_SCORE_TIMESTAMP,
            "module_details": {},
            "scale": "4_point",
            "teacher_note": "Relevant but not fully explained.",
        }
    ]
    assert manifest_path.read_bytes() == original_manifest
    assert evidence_path.read_bytes() == b"routed evidence"
    assert retained_path.read_bytes() == b"retained source"


def test_appends_new_criterion_and_uses_highest_conforming_score_id(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    original = _review()
    original["scores"].extend(
        [
            {
                "score_id": "custom-score",
                "criterion_id": "style",
                "label": "Style",
                "score": 2,
                "max_score": 4,
                "updated_at": ORIGINAL_TIMESTAMP,
                "module_details": {},
            },
            {
                "score_id": "score_0004",
                "criterion_id": "conventions",
                "label": "Conventions",
                "score": 4,
                "max_score": 4,
                "updated_at": ORIGINAL_TIMESTAMP,
                "module_details": {},
            },
        ]
    )
    path = _write_review(tmp_path, copy.deepcopy(original))

    result = set_review_score(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        criterion_id="organization",
        label="Organization",
        score=3.5,
        max_score=4,
        updated_at=SECOND_SCORE_TIMESTAMP,
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.score_id == "score_0005"
    assert result.was_created is True
    assert written["scores"][:-1] == original["scores"]
    assert written["scores"][-1]["criterion_id"] == "organization"


def test_updates_matching_criterion_and_preserves_unrelated_review_data(
    tmp_path: Path,
) -> None:
    _write_manifest(tmp_path)
    original = _review("ready_for_export")
    original["scores"][0]["scale"] = "old_scale"
    original["scores"][0]["teacher_note"] = "Old note."
    original["scores"].append(
        {
            "score_id": "score_0002",
            "criterion_id": "organization",
            "label": "Organization",
            "score": 2,
            "max_score": 4,
            "updated_at": ORIGINAL_TIMESTAMP,
            "module_details": {"preserve": True},
        }
    )
    path = _write_review(tmp_path, copy.deepcopy(original))

    result = set_review_score(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        criterion_id="evidence",
        label="Use of Evidence",
        score=4,
        max_score=5,
        updated_at=SECOND_SCORE_TIMESTAMP,
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert result.score_id == "score_0001"
    assert result.was_created is False
    assert result.review_state == "ready_for_export"
    assert [item["criterion_id"] for item in written["scores"]].count("evidence") == 1
    assert written["scores"][0] == {
        "score_id": "score_0001",
        "criterion_id": "evidence",
        "label": "Use of Evidence",
        "score": 4,
        "max_score": 5,
        "updated_at": SECOND_SCORE_TIMESTAMP,
        "module_details": {},
    }
    assert written["scores"][1] == original["scores"][1]
    for field in ("notes", "tags", "comments", "module_details"):
        assert written[field] == original[field]
    assert written["created_at"] == original["created_at"]
    assert written["updated_at"] == SECOND_SCORE_TIMESTAMP


@pytest.mark.parametrize(
    ("initial_state", "expected_state"),
    [
        ("not_started", "in_progress"),
        ("in_progress", "in_progress"),
        ("ready_for_export", "ready_for_export"),
        ("exported", "exported"),
    ],
)
def test_score_uses_narrow_review_state_transition(
    tmp_path: Path,
    initial_state: str,
    expected_state: str,
) -> None:
    _write_manifest(tmp_path)
    _write_review(tmp_path, _review(initial_state))

    result = set_review_score(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        criterion_id="evidence",
        label="Evidence",
        score=3,
        max_score=4,
        updated_at=SECOND_SCORE_TIMESTAMP,
    )

    assert result.review_state == expected_state


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"criterion_id": " "}, "criterion_id"),
        ({"label": " "}, "label"),
        ({"score": -1}, "score"),
        ({"score": True}, "score"),
        ({"score": math.inf}, "score"),
        ({"score": math.nan}, "score"),
        ({"score": "3"}, "score"),
        ({"max_score": 0}, "max_score"),
        ({"max_score": -1}, "max_score"),
        ({"max_score": True}, "max_score"),
        ({"max_score": math.inf}, "max_score"),
        ({"max_score": math.nan}, "max_score"),
        ({"max_score": "4"}, "max_score"),
        ({"score": 5}, "less than or equal"),
        ({"scale": " "}, "scale"),
        ({"teacher_note": " "}, "teacher_note"),
    ],
)
def test_invalid_score_input_is_rejected_without_writing(
    tmp_path: Path,
    overrides: dict[str, Any],
    message: str,
) -> None:
    _write_manifest(tmp_path)
    arguments: dict[str, Any] = {
        "criterion_id": "evidence",
        "label": "Evidence",
        "score": 3,
        "max_score": 4,
        "updated_at": FIRST_SCORE_TIMESTAMP,
    }
    arguments.update(overrides)

    with pytest.raises(ReviewScoreError, match=message):
        set_review_score(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            **arguments,
        )

    assert not review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    ).exists()


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-time",
        "2026-06-22T14:20:00",
        datetime(2026, 6, 22, 14, 20),
        123,
    ],
)
def test_invalid_timestamp_is_rejected(tmp_path: Path, timestamp: object) -> None:
    _write_manifest(tmp_path)
    with pytest.raises(ReviewScoreError, match="timezone-aware"):
        set_review_score(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            criterion_id="evidence",
            label="Evidence",
            score=3,
            max_score=4,
            updated_at=timestamp,  # type: ignore[arg-type]
        )


def test_timezone_aware_datetime_is_normalized(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    timestamp = datetime(2026, 6, 22, 18, 20, tzinfo=timezone.utc)
    result = set_review_score(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        STUDENT_ID,
        criterion_id="evidence",
        label="Evidence",
        score=3,
        max_score=4,
        updated_at=timestamp,
    )
    assert result.updated_at == timestamp.isoformat()


def test_missing_submission_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReviewScoreError, match="does not exist"):
        set_review_score(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            criterion_id="evidence",
            label="Evidence",
            score=3,
            max_score=4,
            updated_at=FIRST_SCORE_TIMESTAMP,
        )


@pytest.mark.parametrize("record_kind", ["submission", "review"])
def test_invalid_existing_record_is_rejected_without_review_write(
    tmp_path: Path, record_kind: str
) -> None:
    manifest_path = _write_manifest(tmp_path)
    record_path = review_record_path(
        tmp_path, CLASS_ID, ASSIGNMENT_ID, STUDENT_ID
    )
    if record_kind == "submission":
        manifest_path.write_text("{", encoding="utf-8")
    else:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text("{", encoding="utf-8")
    original = record_path.read_bytes() if record_path.exists() else None

    with pytest.raises(ReviewScoreError, match="not valid JSON"):
        set_review_score(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            criterion_id="evidence",
            label="Evidence",
            score=3,
            max_score=4,
            updated_at=FIRST_SCORE_TIMESTAMP,
        )

    assert (
        record_path.read_bytes() if record_path.exists() else None
    ) == original


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
            f"classes/{review['class_id']}/assignments/"
            f"{review['assignment_id']}/submissions/{review['student_id']}/"
            "submission.json"
        )
    _write_manifest(tmp_path, manifest)
    if record_kind == "review":
        _write_review(tmp_path, review)

    with pytest.raises(ReviewScoreError, match=field):
        set_review_score(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            STUDENT_ID,
            criterion_id="evidence",
            label="Evidence",
            score=3,
            max_score=4,
            updated_at=FIRST_SCORE_TIMESTAMP,
        )
