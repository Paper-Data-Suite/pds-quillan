"""Tests for shared rubric loading, validation, and writing."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.rubrics import RubricError, load_rubric, rubric_path, validate_rubric
from quillan.rubric_writing import (
    build_rubric,
    build_rubric_criterion,
    build_rubric_level,
    write_rubric,
)

TIMESTAMP = "2026-06-26T00:00:00+00:00"


def _rubric(rubric_id: str = "general_response_4pt") -> dict[str, Any]:
    level = build_rubric_level(
        score=3,
        label="Clear explanation",
        description="The response explains its reasoning clearly.",
        student_facing_feedback="Your explanation is clear.",
        teacher_note="Use when reasoning is clear.",
        sort_order=30,
    )
    criterion = build_rubric_criterion(
        criterion_id="reasoning_explanation",
        label="Reasoning / Explanation",
        max_score=4,
        scale="4_point",
        standard_ids=["synthetic-standard"],
        sort_order=20,
        levels=[level],
    )
    return build_rubric(
        rubric_id=rubric_id,
        title="General Response 4-Point Rubric",
        description="Reusable synthetic scoring profile.",
        writing_types=["general", "constructed_response"],
        criteria=[criterion],
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


def test_valid_rubric_writes_and_loads_from_shared_path(tmp_path: Path) -> None:
    path = write_rubric(tmp_path, _rubric())

    assert path == tmp_path / "shared" / "rubrics" / "general_response_4pt.json"
    loaded = load_rubric(path)
    assert loaded["rubric_id"] == path.stem
    assert loaded["criteria"][0]["criterion_id"] == "reasoning_explanation"
    assert loaded["criteria"][0]["levels"][0]["score"] == 3


def test_canonical_path_validates_identifier(tmp_path: Path) -> None:
    assert rubric_path(tmp_path, "general_rubric") == (
        tmp_path / "shared" / "rubrics" / "general_rubric.json"
    )
    with pytest.raises(RubricError, match="rubric_id"):
        rubric_path(tmp_path, "../unsafe")


def test_filename_rubric_id_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "different.json"
    path.write_text(json.dumps(_rubric()), encoding="utf-8")
    with pytest.raises(RubricError, match="filename"):
        load_rubric(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "2", "schema_version"),
        ("module", "other", "module"),
        ("record_type", "other", "record_type"),
        ("rubric_id", "../unsafe", "rubric_id"),
        ("title", " ", "title"),
        ("scope", "private", "scope"),
        ("writing_types", [], "non-empty"),
        ("criteria", [], "non-empty"),
        ("created_at", "2026-06-26T00:00:00", "timezone-aware"),
    ],
)
def test_invalid_top_level_values_are_rejected(
    field: str,
    value: Any,
    message: str,
) -> None:
    rubric = _rubric()
    rubric[field] = value
    with pytest.raises(RubricError, match=message):
        validate_rubric(rubric)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_criterion", "Duplicate criterion_id"),
        ("criterion_missing_levels", "non-empty"),
        ("invalid_max_score", "max_score"),
        ("invalid_scale", "scale"),
        ("invalid_standard_ids", "standard_ids"),
        ("duplicate_level_score", "Duplicate level score"),
        ("negative_level_score", "greater than or equal"),
        ("level_above_max", "must not exceed"),
    ],
)
def test_nested_contract_failures_are_rejected(
    mutation: str,
    message: str,
) -> None:
    rubric = copy.deepcopy(_rubric())
    criterion = rubric["criteria"][0]
    level = criterion["levels"][0]
    if mutation == "duplicate_criterion":
        rubric["criteria"].append(copy.deepcopy(criterion))
    elif mutation == "criterion_missing_levels":
        criterion["levels"] = []
    elif mutation == "invalid_max_score":
        criterion["max_score"] = 0
    elif mutation == "invalid_scale":
        criterion["scale"] = ""
    elif mutation == "invalid_standard_ids":
        criterion["standard_ids"] = "synthetic-standard"
    elif mutation == "duplicate_level_score":
        criterion["levels"].append(copy.deepcopy(level))
    elif mutation == "negative_level_score":
        level["score"] = -1
    else:
        level["score"] = 5

    with pytest.raises(RubricError, match=message):
        validate_rubric(rubric)


def test_write_refuses_overwrite_without_confirmation(tmp_path: Path) -> None:
    path = write_rubric(tmp_path, _rubric())
    before = path.read_bytes()

    with pytest.raises(FileExistsError):
        write_rubric(tmp_path, _rubric(), overwrite=False)

    assert path.read_bytes() == before


def test_write_validates_before_creating_directory(tmp_path: Path) -> None:
    rubric = _rubric()
    rubric["criteria"] = []

    with pytest.raises(RubricError):
        write_rubric(tmp_path, rubric)

    assert not (tmp_path / "shared" / "rubrics").exists()
