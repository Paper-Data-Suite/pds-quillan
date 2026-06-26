"""Tests for shared tag-bank loading and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from quillan.tag_banks import (
    TagBankError,
    load_tag_bank,
    tag_bank_path,
    validate_tag_bank,
)
from quillan.tag_bank_writing import (
    build_tag_bank,
    build_tag_category,
    build_tag_template,
    write_tag_bank,
)

TIMESTAMP = "2026-06-26T00:00:00+00:00"


def _bank(tag_bank_id: str = "general_written_response_tags") -> dict[str, Any]:
    category = build_tag_category(
        category_id="reasoning_explanation",
        label="Reasoning / Explanation",
        description="Teacher observations about reasoning.",
    )
    tag = build_tag_template(
        tag_template_id="explanation_needs_more_detail",
        label="Explanation needs more detail",
        category_id="reasoning_explanation",
        polarity="developing",
        optional_metadata={
            "standard_ids": ["synthetic-standard"],
            "criterion_ids": ["explanation"],
            "severity_default": 2,
            "teacher_note_prompt": "What needs more detail?",
            "student_facing_default": False,
            "writing_types": ["general"],
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
        },
    )
    return build_tag_bank(
        tag_bank_id=tag_bank_id,
        title="General Written Response Tags",
        description="Reusable synthetic observations.",
        writing_types=["general", "constructed_response"],
        categories=[category],
        tags=[tag],
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


def test_valid_tag_bank_writes_and_loads_from_shared_path(tmp_path: Path) -> None:
    path = write_tag_bank(tmp_path, _bank())

    assert path == (
        tmp_path
        / "shared"
        / "tag_banks"
        / "general_written_response_tags.json"
    )
    loaded = load_tag_bank(path)
    assert loaded["tag_bank_id"] == path.stem
    assert loaded["categories"][0]["category_id"] == "reasoning_explanation"
    assert loaded["tags"][0]["criterion_ids"] == ["explanation"]


def test_canonical_path_validates_identifier(tmp_path: Path) -> None:
    assert tag_bank_path(tmp_path, "general_tags") == (
        tmp_path / "shared" / "tag_banks" / "general_tags.json"
    )
    with pytest.raises(TagBankError, match="tag_bank_id"):
        tag_bank_path(tmp_path, "../unsafe")


def test_filename_tag_bank_id_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "different.json"
    path.write_text(json.dumps(_bank()), encoding="utf-8")
    with pytest.raises(TagBankError, match="filename"):
        load_tag_bank(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "2", "schema_version"),
        ("module", "other", "module"),
        ("record_type", "other", "record_type"),
        ("tag_bank_id", "../unsafe", "tag_bank_id"),
        ("title", " ", "title"),
        ("scope", "private", "scope"),
        ("writing_types", [], "non-empty"),
        ("categories", [], "non-empty"),
        ("tags", [], "non-empty"),
        ("created_at", "2026-06-26T00:00:00", "timezone-aware"),
    ],
)
def test_invalid_top_level_values_are_rejected(
    field: str,
    value: Any,
    message: str,
) -> None:
    bank = _bank()
    bank[field] = value
    with pytest.raises(TagBankError, match=message):
        validate_tag_bank(bank)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_category", "Duplicate category_id"),
        ("duplicate_tag", "Duplicate tag_template_id"),
        ("unknown_category", "unknown category"),
        ("invalid_polarity", "polarity"),
        ("invalid_severity", "severity_default"),
        ("invalid_student_facing", "student_facing_default"),
        ("outside_writing_type", "outside"),
        ("duplicate_standard", "duplicate"),
    ],
)
def test_nested_contract_failures_are_rejected(
    mutation: str,
    message: str,
) -> None:
    bank = copy.deepcopy(_bank())
    tag = bank["tags"][0]
    if mutation == "duplicate_category":
        bank["categories"].append(copy.deepcopy(bank["categories"][0]))
    elif mutation == "duplicate_tag":
        bank["tags"].append(copy.deepcopy(tag))
    elif mutation == "unknown_category":
        tag["category_id"] = "missing"
    elif mutation == "invalid_polarity":
        tag["polarity"] = "mixed"
    elif mutation == "invalid_severity":
        tag["severity_default"] = True
    elif mutation == "invalid_student_facing":
        tag["student_facing_default"] = "no"
    elif mutation == "outside_writing_type":
        tag["writing_types"] = ["lab_report"]
    else:
        tag["standard_ids"].append(tag["standard_ids"][0])

    with pytest.raises(TagBankError, match=message):
        validate_tag_bank(bank)


def test_write_refuses_overwrite_without_confirmation(tmp_path: Path) -> None:
    path = write_tag_bank(tmp_path, _bank())
    before = path.read_bytes()

    with pytest.raises(FileExistsError):
        write_tag_bank(tmp_path, _bank(), overwrite=False)

    assert path.read_bytes() == before


def test_write_validates_before_creating_directory(tmp_path: Path) -> None:
    bank = _bank()
    bank["tags"] = []

    with pytest.raises(TagBankError):
        write_tag_bank(tmp_path, bank)

    assert not (tmp_path / "shared" / "tag_banks").exists()
