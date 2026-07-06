"""Tests for Quillan schema version 2 review record loading and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.review_record import (
    ReviewRecordError,
    build_empty_review_record,
    load_review_record,
    validate_review_record,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00107"
TIMESTAMP = "2026-06-22T00:00:00+00:00"
LATER_TIMESTAMP = "2026-06-22T01:00:00+00:00"
EXAMPLE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "submissions"
    / "review_record_v2_synthetic.json"
)


def _record() -> dict[str, Any]:
    return build_empty_review_record(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=STUDENT_ID,
        created_at=TIMESTAMP,
    )


def _populated_record() -> dict[str, Any]:
    record = _record()
    record["review_state"] = "feedback_composed"
    record["updated_at"] = LATER_TIMESTAMP
    record["minimum_requirement_checks"] = [
        {
            "requirement_check_id": "requirement_check_0001",
            "requirement_key": "paragraphs_min",
            "label": "Minimum paragraphs",
            "expected": 5,
            "met": True,
            "teacher_note": None,
            "updated_at": LATER_TIMESTAMP,
            "module_details": {},
        }
    ]
    record["minimum_requirement_outcome"] = {
        "status": "met",
        "returned_without_full_review": False,
        "teacher_note": "Ready for full review.",
        "updated_at": LATER_TIMESTAMP,
    }
    record["review_units"] = [
        {
            "unit_id": "paragraph_1",
            "sequence": 1,
            "label": "Paragraph 1",
            "unit_type": "paragraph",
            "page_number": 1,
            "evidence_id": "evidence_001",
            "standard_observations": [
                {
                    "observation_id": "observation_0001",
                    "standard_id": "njsls-ela:W.AW.11-12.1",
                    "applicable": True,
                    "evidence_present": True,
                    "rating": 3,
                    "rationale": "Clear claim with relevant evidence.",
                    "include_in_feedback": True,
                    "updated_at": LATER_TIMESTAMP,
                    "module_details": {},
                },
                {
                    "observation_id": "observation_0002",
                    "standard_id": "njsls-ela:W.WP.11-12.4",
                    "applicable": False,
                    "evidence_present": None,
                    "rating": None,
                    "rationale": None,
                    "include_in_feedback": False,
                    "updated_at": LATER_TIMESTAMP,
                    "module_details": {},
                },
            ],
            "module_details": {},
        }
    ]
    record["overall_standard_ratings"] = [
        {
            "standard_id": "njsls-ela:W.AW.11-12.1",
            "rating": 3,
            "rationale": "The argument is focused.",
            "include_in_feedback": True,
            "updated_at": LATER_TIMESTAMP,
            "module_details": {},
        }
    ]
    record["feedback"] = {
        "include_review_unit_observations": True,
        "include_overall_standard_ratings": True,
        "standard_feedback": [
            {
                "standard_id": "njsls-ela:W.AW.11-12.1",
                "include_overall_rating": True,
                "include_overall_rationale": True,
                "included_observation_ids": ["observation_0001"],
                "comments": [
                    {
                        "feedback_comment_id": "feedback_comment_0001",
                        "source": "custom",
                        "text": "Keep connecting evidence back to the claim.",
                        "reusable_comment_id": None,
                        "save_for_reuse": False,
                        "include_in_feedback": True,
                        "created_at": LATER_TIMESTAMP,
                        "module_details": {},
                    },
                    {
                        "feedback_comment_id": "feedback_comment_0002",
                        "source": "reusable_focus_standard_comment",
                        "text": "Your claim is clear.",
                        "reusable_comment_id": "reusable_comment_0001",
                        "save_for_reuse": False,
                        "include_in_feedback": True,
                        "created_at": LATER_TIMESTAMP,
                        "module_details": {},
                    },
                ],
                "module_details": {},
            }
        ],
    }
    record["exports"] = {
        "feedback_pdf": {
            "path": (
                f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/submissions/"
                f"{STUDENT_ID}/feedback.pdf"
            ),
            "generated_at": LATER_TIMESTAMP,
            "source_review_updated_at": LATER_TIMESTAMP,
            "module_details": {},
        },
        "feedback_markdown": None,
    }
    record["private_notes"] = [
        {
            "private_note_id": "private_note_0001",
            "text": "Conference follow-up.",
            "created_at": TIMESTAMP,
            "updated_at": LATER_TIMESTAMP,
            "module_details": {},
        }
    ]
    return record


def _assert_invalid(record: dict[str, Any], match: str) -> None:
    with pytest.raises(ReviewRecordError, match=match):
        validate_review_record(record)


def _with(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    record = _populated_record()
    target: Any = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return record


def test_build_empty_review_record_returns_valid_v2_record() -> None:
    record = _record()

    validate_review_record(record)
    assert record["schema_version"] == "2"
    assert record["review_state"] == "not_started"
    assert record["assignment_path"] == (
        f"classes/{CLASS_ID}/assignments/{ASSIGNMENT_ID}/assignment.json"
    )
    assert record["minimum_requirement_outcome"] == {
        "status": "not_checked",
        "returned_without_full_review": False,
        "teacher_note": None,
        "updated_at": None,
    }


def test_existing_v2_synthetic_example_loads() -> None:
    record = load_review_record(EXAMPLE_PATH)

    assert record["schema_version"] == "2"
    assert record["review_units"]


def test_populated_v2_record_validates() -> None:
    validate_review_record(_populated_record())


def test_valid_json_file_loads_successfully(tmp_path: Path) -> None:
    record = _populated_record()
    path = tmp_path / "review.json"
    path.write_text(json.dumps(record), encoding="utf-8")

    assert load_review_record(path) == record


@pytest.mark.parametrize("value", [[], "review", 1, None])
def test_non_object_json_is_rejected(tmp_path: Path, value: Any) -> None:
    path = tmp_path / "review.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ReviewRecordError, match="JSON object"):
        load_review_record(path)


def test_missing_file_and_invalid_json_raise_review_record_error(tmp_path: Path) -> None:
    with pytest.raises(ReviewRecordError, match="not found"):
        load_review_record(tmp_path / "missing.json")

    path = tmp_path / "review.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ReviewRecordError, match="not valid JSON"):
        load_review_record(path)


@pytest.mark.parametrize("field", sorted(_record().keys()))
def test_missing_required_top_level_field_is_rejected(field: str) -> None:
    record = _record()
    del record[field]

    _assert_invalid(record, field)


@pytest.mark.parametrize("field", ["notes", "tags", "scores", "comments", "requirement_checks"])
def test_legacy_top_level_fields_are_rejected(field: str) -> None:
    record = _record()
    record[field] = []

    _assert_invalid(record, field)


def test_schema_version_one_is_rejected_as_legacy() -> None:
    record = _record()
    record["schema_version"] = "1"

    _assert_invalid(record, "legacy")


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "3"), ("module", "other"), ("record_type", "review")],
)
def test_invalid_fixed_values_are_rejected(field: str, value: str) -> None:
    record = _record()
    record[field] = value

    _assert_invalid(record, field)


@pytest.mark.parametrize(
    ("field", "value"),
    [("class_id", "../unsafe"), ("assignment_id", "bad assignment"), ("student_id", "")],
)
def test_invalid_identifier_is_rejected(field: str, value: str) -> None:
    record = _record()
    record[field] = value

    _assert_invalid(record, field)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("submission_manifest_path", "submission.json"),
        ("submission_manifest_path", r"C:\workspace\submission.json"),
        ("assignment_path", "assignment.json"),
        ("assignment_path", f"classes/{CLASS_ID}/assignments/../{ASSIGNMENT_ID}/assignment.json"),
    ],
)
def test_invalid_canonical_paths_are_rejected(field: str, value: str) -> None:
    record = _record()
    record[field] = value

    _assert_invalid(record, field)


@pytest.mark.parametrize("value", ["reviewed", "in_progress"])
def test_invalid_review_state_is_rejected(value: str) -> None:
    _assert_invalid(_with(("review_state",), value), "review_state")


@pytest.mark.parametrize("value", ["", "not-a-time", "2026-06-22T10:00:00"])
def test_invalid_or_naive_timestamp_is_rejected(value: str) -> None:
    _assert_invalid(_with(("created_at",), value), "created_at")


def test_updated_at_before_created_at_is_rejected() -> None:
    _assert_invalid(_with(("updated_at",), "2026-06-21T23:59:59+00:00"), "precede")


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("minimum_requirement_checks",), {}, "minimum_requirement_checks"),
        (("minimum_requirement_checks",), [_populated_record()["minimum_requirement_checks"][0]] * 2, "Duplicate requirement_check_id"),
        (("minimum_requirement_checks",), [{**_populated_record()["minimum_requirement_checks"][0], "label": " "}], "label"),
        (("minimum_requirement_checks",), [{**_populated_record()["minimum_requirement_checks"][0], "expected": True}], "expected"),
        (("minimum_requirement_checks",), [{**_populated_record()["minimum_requirement_checks"][0], "met": "yes"}], "met"),
        (("minimum_requirement_checks",), [{**_populated_record()["minimum_requirement_checks"][0], "teacher_note": " "}], "teacher_note"),
        (("minimum_requirement_outcome", "status"), "bad", "status"),
        (("minimum_requirement_outcome", "returned_without_full_review"), "yes", "returned_without_full_review"),
        (("minimum_requirement_outcome", "teacher_note"), " ", "teacher_note"),
        (("minimum_requirement_outcome", "updated_at"), None, "updated_at"),
        (("review_units",), {}, "review_units"),
        (("review_units",), [_populated_record()["review_units"][0]] * 2, "Duplicate unit_id"),
        (("review_units", 0, "sequence"), 0, "sequence"),
        (("review_units", 0, "label"), " ", "label"),
        (("review_units", 0, "standard_observations"), {}, "standard_observations"),
        (("review_units", 0, "standard_observations", 0, "applicable"), "yes", "applicable"),
        (("review_units", 0, "standard_observations", 0, "evidence_present"), None, "evidence_present"),
        (("review_units", 0, "standard_observations", 0, "rating"), None, "rating"),
        (("review_units", 0, "standard_observations", 0, "rationale"), " ", "rationale"),
        (("review_units", 0, "standard_observations", 0, "include_in_feedback"), 1, "include_in_feedback"),
        (("overall_standard_ratings",), {}, "overall_standard_ratings"),
        (("overall_standard_ratings",), [_populated_record()["overall_standard_ratings"][0]] * 2, "Duplicate standard_id"),
        (("overall_standard_ratings", 0, "rating"), 3.5, "rating"),
        (("feedback",), [], "feedback"),
        (("feedback", "include_review_unit_observations"), "yes", "include_review_unit_observations"),
        (("feedback", "standard_feedback"), {}, "standard_feedback"),
        (("feedback", "standard_feedback", 0, "included_observation_ids"), ["missing"], "unknown observation_id"),
        (("feedback", "standard_feedback", 0, "comments"), {}, "comments"),
        (("feedback", "standard_feedback", 0, "comments", 0, "source"), "generated", "source"),
        (("feedback", "standard_feedback", 0, "comments", 0, "text"), " ", "text"),
        (("feedback", "standard_feedback", 0, "comments", 0, "reusable_comment_id"), "not-null", "reusable_comment_id"),
        (("exports",), [], "exports"),
        (("exports", "feedback_pdf", "path"), "/absolute.pdf", "path"),
        (("exports", "feedback_pdf", "path"), "exports/../feedback.pdf", "path"),
        (("exports", "feedback_pdf", "generated_at"), "not-a-time", "generated_at"),
        (("private_notes",), {}, "private_notes"),
        (("private_notes",), [_populated_record()["private_notes"][0]] * 2, "Duplicate private_note_id"),
        (("private_notes", 0, "text"), " ", "text"),
        (("private_notes", 0, "updated_at"), "2026-06-21T23:00:00+00:00", "precede"),
    ],
)
def test_invalid_nested_v2_fields_are_rejected(
    path: tuple[Any, ...], value: Any, match: str
) -> None:
    record = _populated_record()
    target: Any = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    _assert_invalid(record, match)


def test_returned_without_full_review_consistency_is_enforced() -> None:
    record = _record()
    record["review_state"] = "returned_without_full_review"
    record["minimum_requirement_outcome"] = {
        "status": "returned_without_full_review",
        "returned_without_full_review": True,
        "teacher_note": "Return for missing required elements.",
        "updated_at": LATER_TIMESTAMP,
    }
    validate_review_record(record)

    invalid = copy.deepcopy(record)
    invalid["review_state"] = "requirements_checked"
    _assert_invalid(invalid, "returned_without_full_review")

    invalid = copy.deepcopy(record)
    invalid["minimum_requirement_outcome"]["returned_without_full_review"] = False
    _assert_invalid(invalid, "returned_without_full_review")


def test_unknown_top_level_field_is_rejected() -> None:
    record = _record()
    record["extra"] = "not in schema version 2"

    _assert_invalid(record, "Unknown field 'extra'")
