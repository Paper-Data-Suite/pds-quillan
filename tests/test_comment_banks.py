"""Tests for shared comment-bank loading and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from quillan.comment_banks import (
    CommentBankError,
    comment_bank_path,
    load_comment_bank,
    validate_comment_bank,
)

EXAMPLE_PATH = (
    Path(__file__).parents[1]
    / "examples"
    / "comment_banks"
    / "general_writing_synthetic.json"
)


def _bank() -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    )


def test_valid_synthetic_bank_loads() -> None:
    bank = load_comment_bank(EXAMPLE_PATH)
    assert bank["bank_id"] == "general_writing_synthetic"
    assert len(bank["comments"]) > 1


def test_canonical_path_validates_identifier(tmp_path: Path) -> None:
    assert comment_bank_path(tmp_path, "general_writing") == (
        tmp_path / "shared" / "comment_banks" / "general_writing.json"
    )
    with pytest.raises(CommentBankError, match="bank_id"):
        comment_bank_path(tmp_path, "../unsafe")


def test_missing_invalid_json_and_non_object_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(CommentBankError, match="not found"):
        load_comment_bank(tmp_path / "missing.json")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(CommentBankError, match="not valid JSON"):
        load_comment_bank(invalid)
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(CommentBankError, match="JSON object"):
        load_comment_bank(invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2"),
        ("module", "other"),
        ("record_type", "other"),
        ("bank_id", "../unsafe"),
        ("title", " "),
        ("scope", "private"),
    ],
)
def test_invalid_top_level_values_are_rejected(field: str, value: Any) -> None:
    bank = _bank()
    bank[field] = value
    with pytest.raises(CommentBankError, match=field):
        validate_comment_bank(bank)


def test_filename_bank_id_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "different.json"
    path.write_text(json.dumps(_bank()), encoding="utf-8")
    with pytest.raises(CommentBankError, match="filename"):
        load_comment_bank(path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_writing_type", "duplicate"),
        ("duplicate_category", "Duplicate category_id"),
        ("duplicate_comment", "Duplicate comment_id"),
        ("unknown_category", "unknown category"),
        ("invalid_polarity", "polarity"),
        ("invalid_feedback_default", "include_in_feedback_default"),
        ("invalid_student_facing", "student_facing"),
        ("invalid_severity", "severity_default"),
        ("duplicate_tags", "duplicate"),
        ("outside_writing_type", "outside"),
        ("invalid_timestamp", "created_at"),
    ],
)
def test_nested_contract_failures_are_rejected(
    mutation: str, message: str
) -> None:
    bank = copy.deepcopy(_bank())
    comment = bank["comments"][0]
    if mutation == "duplicate_writing_type":
        bank["writing_types"].append(bank["writing_types"][0])
    elif mutation == "duplicate_category":
        bank["categories"].append(copy.deepcopy(bank["categories"][0]))
    elif mutation == "duplicate_comment":
        bank["comments"].append(copy.deepcopy(comment))
    elif mutation == "unknown_category":
        comment["category_id"] = "missing"
    elif mutation == "invalid_polarity":
        comment["polarity"] = "mixed"
    elif mutation == "invalid_feedback_default":
        comment["include_in_feedback_default"] = 1
    elif mutation == "invalid_student_facing":
        comment["student_facing"] = "yes"
    elif mutation == "invalid_severity":
        comment["severity_default"] = True
    elif mutation == "duplicate_tags":
        comment["tags"].append(comment["tags"][0])
    elif mutation == "outside_writing_type":
        comment["writing_types"] = ["unknown"]
    else:
        bank["created_at"] = "2026-06-22T00:00:00"

    with pytest.raises(CommentBankError, match=message):
        validate_comment_bank(bank)
