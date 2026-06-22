"""Tests for Quillan submission review record loading and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import (
    ReviewRecordError,
    load_review_record,
    validate_review_record,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
EXAMPLE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "submissions"
    / "review_record_synthetic.json"
)


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
        "module_details": {},
    }


def _note(note_id: str = "note_0001") -> dict[str, Any]:
    return {
        "note_id": note_id,
        "text": "Teacher observation.",
        "created_at": "2026-06-22T10:00:00-04:00",
        "updated_at": "2026-06-22T10:05:00-04:00",
        "module_details": {},
    }


def _tag(tag_id: str = "tag_0001") -> dict[str, Any]:
    return {
        "tag_id": tag_id,
        "label": "Clear claim",
        "polarity": "positive",
        "created_at": "2026-06-22T10:00:00-04:00",
        "module_details": {},
    }


def _score(
    score_id: str = "score_0001",
    criterion_id: str = "evidence",
) -> dict[str, Any]:
    return {
        "score_id": score_id,
        "criterion_id": criterion_id,
        "label": "Evidence",
        "score": 3,
        "max_score": 4,
        "updated_at": "2026-06-22T10:00:00-04:00",
        "module_details": {},
    }


def _comment(comment_record_id: str = "comment_0001") -> dict[str, Any]:
    return {
        "comment_record_id": comment_record_id,
        "label": "Explain evidence",
        "text": "Explain how the evidence supports the claim.",
        "source": "custom",
        "include_in_feedback": True,
        "created_at": "2026-06-22T10:00:00-04:00",
        "module_details": {},
    }


def _write_json(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_minimal_review_record() -> None:
    validate_review_record(_record())


def test_valid_populated_synthetic_review_record_loads() -> None:
    record = load_review_record(EXAMPLE_PATH)

    assert record["record_type"] == "submission_review"
    assert len(record["tags"]) == 2


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "module",
        "record_type",
        "class_id",
        "assignment_id",
        "student_id",
        "submission_manifest_path",
        "review_state",
        "notes",
        "tags",
        "scores",
        "comments",
        "created_at",
        "updated_at",
        "module_details",
    ],
)
def test_missing_required_top_level_field_is_rejected(field: str) -> None:
    record = _record()
    del record[field]

    with pytest.raises(ReviewRecordError, match=field):
        validate_review_record(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2"),
        ("module", "other"),
        ("record_type", "review"),
    ],
)
def test_invalid_fixed_value_is_rejected(field: str, value: str) -> None:
    record = _record()
    record[field] = value

    with pytest.raises(ReviewRecordError, match=field):
        validate_review_record(record)


def test_unknown_top_level_field_is_rejected() -> None:
    record = _record()
    record["extra"] = "not in schema version 1"

    with pytest.raises(ReviewRecordError, match="Unknown field 'extra'"):
        validate_review_record(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_id", "../unsafe"),
        ("assignment_id", "bad assignment"),
        ("student_id", ""),
    ],
)
def test_invalid_identifier_is_rejected(field: str, value: str) -> None:
    record = _record()
    record[field] = value

    with pytest.raises(ReviewRecordError, match=field):
        validate_review_record(record)


@pytest.mark.parametrize(
    "path",
    [
        "/classes/class/assignment/submission.json",
        r"C:\workspace\submission.json",
        (
            f"classes/{CLASS_ID}/./assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json"
        ),
        (
            f"classes/{CLASS_ID}/assignments/../{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json"
        ),
        (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            f"{STUDENT_ID}/submission.json\0"
        ),
        "submission.json",
        (
            f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
            "different_student/submission.json"
        ),
    ],
)
def test_invalid_submission_manifest_path_is_rejected(path: str) -> None:
    record = _record()
    record["submission_manifest_path"] = path

    with pytest.raises(ReviewRecordError, match="submission_manifest_path"):
        validate_review_record(record)


def test_invalid_review_state_is_rejected() -> None:
    record = _record()
    record["review_state"] = "reviewed"

    with pytest.raises(ReviewRecordError, match="review_state"):
        validate_review_record(record)


@pytest.mark.parametrize("value", ["", "not-a-time", "2026-06-22T10:00:00"])
def test_invalid_or_naive_top_level_timestamp_is_rejected(value: str) -> None:
    record = _record()
    record["created_at"] = value

    with pytest.raises(ReviewRecordError, match="created_at"):
        validate_review_record(record)


def test_top_level_updated_at_before_created_at_is_rejected() -> None:
    record = _record()
    record["created_at"] = "2026-06-22T11:00:00+00:00"
    record["updated_at"] = "2026-06-22T10:59:59+00:00"

    with pytest.raises(ReviewRecordError, match="must not precede"):
        validate_review_record(record)


def test_notes_must_be_a_list() -> None:
    record = _record()
    record["notes"] = {}

    with pytest.raises(ReviewRecordError, match="notes.*list"):
        validate_review_record(record)


def test_duplicate_note_id_is_rejected() -> None:
    record = _record()
    record["notes"] = [_note(), _note()]

    with pytest.raises(ReviewRecordError, match="Duplicate note_id"):
        validate_review_record(record)


def test_blank_note_text_is_rejected() -> None:
    record = _record()
    note = _note()
    note["text"] = " \t"
    record["notes"] = [note]

    with pytest.raises(ReviewRecordError, match="text"):
        validate_review_record(record)


def test_note_updated_at_before_created_at_is_rejected() -> None:
    record = _record()
    note = _note()
    note["updated_at"] = "2026-06-22T09:59:59-04:00"
    record["notes"] = [note]

    with pytest.raises(ReviewRecordError, match="must not precede"):
        validate_review_record(record)


def test_invalid_tag_polarity_is_rejected() -> None:
    record = _record()
    tag = _tag()
    tag["polarity"] = "mixed"
    record["tags"] = [tag]

    with pytest.raises(ReviewRecordError, match="polarity"):
        validate_review_record(record)


def test_duplicate_tag_id_is_rejected() -> None:
    record = _record()
    record["tags"] = [_tag(), _tag()]

    with pytest.raises(ReviewRecordError, match="Duplicate tag_id"):
        validate_review_record(record)


@pytest.mark.parametrize(
    "location",
    [
        {"type": "word", "value": 1},
        {"type": "page", "value": 0},
        {"type": "paragraph", "value": "one"},
        {"type": "section", "value": ""},
        {"type": "whole_submission", "value": 1},
        {"type": "page"},
        {"type": "page", "value": 1, "extra": True},
    ],
)
def test_malformed_tag_location_is_rejected(location: dict[str, Any]) -> None:
    record = _record()
    tag = _tag()
    tag["location"] = location
    record["tags"] = [tag]

    with pytest.raises(ReviewRecordError, match="location"):
        validate_review_record(record)


def test_page_location_must_agree_with_page_number() -> None:
    record = _record()
    tag = _tag()
    tag["page_number"] = 2
    tag["location"] = {"type": "page", "value": 1}
    record["tags"] = [tag]

    with pytest.raises(ReviewRecordError, match="agree"):
        validate_review_record(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("severity", -1),
        ("severity", True),
        ("page_number", 0),
        ("teacher_note", " "),
        ("evidence_id", ""),
    ],
)
def test_invalid_optional_tag_field_is_rejected(field: str, value: Any) -> None:
    record = _record()
    tag = _tag()
    tag[field] = value
    record["tags"] = [tag]

    with pytest.raises(ReviewRecordError, match=field):
        validate_review_record(record)


def test_duplicate_score_id_is_rejected() -> None:
    record = _record()
    record["scores"] = [_score(), _score(criterion_id="organization")]

    with pytest.raises(ReviewRecordError, match="Duplicate score_id"):
        validate_review_record(record)


def test_duplicate_criterion_id_is_rejected() -> None:
    record = _record()
    record["scores"] = [_score(), _score(score_id="score_0002")]

    with pytest.raises(ReviewRecordError, match="Duplicate criterion_id"):
        validate_review_record(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", "3"),
        ("score", True),
        ("score", -1),
        ("score", float("inf")),
        ("max_score", 0),
        ("max_score", float("nan")),
    ],
)
def test_invalid_score_value_is_rejected(field: str, value: Any) -> None:
    record = _record()
    score = _score()
    score[field] = value
    record["scores"] = [score]

    with pytest.raises(ReviewRecordError, match=field):
        validate_review_record(record)


def test_score_greater_than_max_score_is_rejected() -> None:
    record = _record()
    score = _score()
    score["score"] = 5
    record["scores"] = [score]

    with pytest.raises(ReviewRecordError, match="must not exceed"):
        validate_review_record(record)


def test_invalid_comment_source_is_rejected() -> None:
    record = _record()
    comment = _comment()
    comment["source"] = "generated"
    record["comments"] = [comment]

    with pytest.raises(ReviewRecordError, match="source"):
        validate_review_record(record)


def test_non_boolean_include_in_feedback_is_rejected() -> None:
    record = _record()
    comment = _comment()
    comment["include_in_feedback"] = 1
    record["comments"] = [comment]

    with pytest.raises(ReviewRecordError, match="include_in_feedback"):
        validate_review_record(record)


def test_duplicate_comment_record_id_is_rejected() -> None:
    record = _record()
    record["comments"] = [_comment(), _comment()]

    with pytest.raises(ReviewRecordError, match="Duplicate comment_record_id"):
        validate_review_record(record)


@pytest.mark.parametrize(
    ("container", "item_factory"),
    [
        ("notes", _note),
        ("tags", _tag),
        ("scores", _score),
        ("comments", _comment),
    ],
)
def test_nested_module_details_must_be_an_object(
    container: str,
    item_factory: Any,
) -> None:
    record = _record()
    item = item_factory()
    item["module_details"] = []
    record[container] = [item]

    with pytest.raises(ReviewRecordError, match="module_details"):
        validate_review_record(record)


def test_top_level_module_details_must_be_an_object() -> None:
    record = _record()
    record["module_details"] = []

    with pytest.raises(ReviewRecordError, match="module_details"):
        validate_review_record(record)


def test_valid_json_file_loads_successfully(tmp_path: Path) -> None:
    record = _record()
    path = _write_json(tmp_path / "review.json", record)

    assert load_review_record(path) == record


def test_missing_file_raises_review_record_error(tmp_path: Path) -> None:
    with pytest.raises(ReviewRecordError, match="not found"):
        load_review_record(tmp_path / "missing.json")


def test_invalid_json_raises_review_record_error(tmp_path: Path) -> None:
    path = tmp_path / "review.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ReviewRecordError, match="not valid JSON"):
        load_review_record(path)


@pytest.mark.parametrize("value", [[], "review", 1, None])
def test_non_object_json_is_rejected(tmp_path: Path, value: Any) -> None:
    path = _write_json(tmp_path / "review.json", value)

    with pytest.raises(ReviewRecordError, match="JSON object"):
        load_review_record(path)


def test_structurally_invalid_json_object_is_rejected(tmp_path: Path) -> None:
    record = copy.deepcopy(_record())
    record["review_state"] = "invalid"
    path = _write_json(tmp_path / "review.json", record)

    with pytest.raises(ReviewRecordError, match="review_state"):
        load_review_record(path)
