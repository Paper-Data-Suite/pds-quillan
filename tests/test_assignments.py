"""Tests for assignment config loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quillan.assignments import (
    AssignmentConfigError,
    load_assignment_config,
    validate_assignment_config,
)


def _valid_assignment_config() -> dict[str, Any]:
    """Return a valid synthetic v2 assignment config."""
    return {
        "schema_version": "2",
        "module": "quillan",
        "record_type": "assignment",
        "assignment_id": "villainy_final_essay_synthetic",
        "title": "Villainy Final Essay",
        "class_ids": ["english12_period3_synthetic"],
        "writing_type": "literary_argument",
        "student_prompt": "Rank villains using evidence from the texts.",
        "standards_profile_id": "english_12_njsls_synthetic",
        "focus_standard_ids": [
            "njsls-ela:W.AW.11-12.1",
            "njsls-ela:W.WP.11-12.4",
        ],
        "review_unit": {
            "type": "paragraph",
            "singular_label": "paragraph",
            "plural_label": "paragraphs",
        },
        "rating_scale": {
            "scale_id": "standards_4_level",
            "levels": [
                {
                    "value": 1,
                    "label": "Developing",
                    "description": "Limited evidence of the standard.",
                },
                {
                    "value": 2,
                    "label": "Approaching",
                    "description": "Partial evidence of the standard.",
                },
            ],
        },
        "basic_requirements": {
            "paragraphs_min": 4,
            "paragraphs_max": 6,
            "word_count_min": 500,
            "word_count_max": 1200,
            "required_elements": [
                "thesis",
                "textual evidence",
                "comparative reasoning",
            ],
        },
        "minimum_requirement_policy": {
            "allow_return_without_full_review": True,
        },
    }


def _write_assignment(tmp_path: Path, assignment: dict[str, Any]) -> Path:
    assignment_path = tmp_path / "assignment.json"
    assignment_path.write_text(json.dumps(assignment), encoding="utf-8")
    return assignment_path


def test_load_valid_assignment_config(tmp_path: Path) -> None:
    assignment_data = _valid_assignment_config()

    loaded_assignment = load_assignment_config(
        _write_assignment(tmp_path, assignment_data)
    )

    assert loaded_assignment == assignment_data


def test_validate_assignment_config_accepts_example_assignment() -> None:
    path = (
        Path(__file__).parent.parent
        / "examples"
        / "assignments"
        / "villainy_final_essay_synthetic.json"
    )

    validate_assignment_config(json.loads(path.read_text(encoding="utf-8")))


def test_optional_metadata_fields_do_not_break_validation(tmp_path: Path) -> None:
    assignment = _valid_assignment_config()
    assignment["created_at"] = "2026-07-02T00:00:00+00:00"
    assignment["updated_at"] = "2026-07-02T00:00:00+00:00"
    assignment["module_details"] = {}

    assert load_assignment_config(_write_assignment(tmp_path, assignment)) == assignment


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "module",
        "record_type",
        "assignment_id",
        "title",
        "class_ids",
        "writing_type",
        "student_prompt",
        "standards_profile_id",
        "focus_standard_ids",
        "review_unit",
        "rating_scale",
        "basic_requirements",
        "minimum_requirement_policy",
    ],
)
def test_missing_required_field_raises_error(tmp_path: Path, field: str) -> None:
    assignment = _valid_assignment_config()
    del assignment[field]

    with pytest.raises(AssignmentConfigError, match=field):
        load_assignment_config(_write_assignment(tmp_path, assignment))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "1"),
        ("module", "other"),
        ("record_type", "other"),
        ("assignment_id", "../unsafe"),
        ("title", ""),
        ("class_ids", []),
        ("writing_type", ""),
        ("student_prompt", ""),
        ("standards_profile_id", ""),
        ("focus_standard_ids", []),
        ("review_unit", []),
        ("rating_scale", []),
        ("basic_requirements", []),
        ("minimum_requirement_policy", []),
    ],
)
def test_invalid_required_field_raises_error(
    tmp_path: Path, field: str, value: object
) -> None:
    assignment = _valid_assignment_config()
    assignment[field] = value

    with pytest.raises(AssignmentConfigError, match=field):
        load_assignment_config(_write_assignment(tmp_path, assignment))


def test_legacy_assignment_config_is_rejected_clearly(tmp_path: Path) -> None:
    assignment = {
        "assignment_id": "legacy_assignment",
        "title": "Legacy Assignment",
        "class_ids": ["english12"],
        "writing_type": "argument",
        "standards_profile_id": "synthetic",
        "tagging_mode": "focus",
        "focus_standards": ["synthetic:W.1"],
        "basic_requirements": {},
        "rubric_id": "legacy_rubric",
    }

    with pytest.raises(AssignmentConfigError, match="Legacy assignment configs"):
        load_assignment_config(_write_assignment(tmp_path, assignment))


@pytest.mark.parametrize("field", ["type", "singular_label", "plural_label"])
def test_review_unit_requires_fields(tmp_path: Path, field: str) -> None:
    assignment = _valid_assignment_config()
    del assignment["review_unit"][field]

    with pytest.raises(AssignmentConfigError, match=field):
        load_assignment_config(_write_assignment(tmp_path, assignment))


@pytest.mark.parametrize(
    "review_unit",
    [
        {"type": "", "singular_label": "paragraph", "plural_label": "paragraphs"},
        {"type": "two words", "singular_label": "paragraph", "plural_label": "paragraphs"},
        {"type": "paragraph", "singular_label": "", "plural_label": "paragraphs"},
        {"type": "paragraph", "singular_label": "paragraph", "plural_label": ""},
    ],
)
def test_review_unit_rejects_invalid_values(
    tmp_path: Path, review_unit: dict[str, str]
) -> None:
    assignment = _valid_assignment_config()
    assignment["review_unit"] = review_unit

    with pytest.raises(AssignmentConfigError, match="review_unit"):
        load_assignment_config(_write_assignment(tmp_path, assignment))


@pytest.mark.parametrize(
    "rating_scale",
    [
        {"levels": [{"value": 1, "label": "Developing", "description": "Some."}]},
        {"scale_id": "scale"},
        {"scale_id": "scale", "levels": []},
        {"scale_id": "scale", "levels": "bad"},
        {"scale_id": "scale", "levels": [{"label": "Developing", "description": "Some."}]},
        {"scale_id": "scale", "levels": [{"value": True, "label": "Developing", "description": "Some."}]},
        {"scale_id": "scale", "levels": [{"value": 1, "label": "A", "description": "A."}, {"value": 1, "label": "B", "description": "B."}]},
        {"scale_id": "scale", "levels": [{"value": 1, "label": "", "description": "Some."}]},
        {"scale_id": "scale", "levels": [{"value": 1, "label": "Developing", "description": ""}]},
    ],
)
def test_rating_scale_rejects_invalid_values(
    tmp_path: Path, rating_scale: dict[str, object]
) -> None:
    assignment = _valid_assignment_config()
    assignment["rating_scale"] = rating_scale

    with pytest.raises(AssignmentConfigError, match="rating_scale|Duplicate"):
        load_assignment_config(_write_assignment(tmp_path, assignment))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("paragraphs_min", -1),
        ("paragraphs_max", True),
        ("word_count_min", 1.5),
        ("word_count_max", "500"),
    ],
)
def test_known_requirement_numbers_must_be_non_negative_integers(
    tmp_path: Path, key: str, value: object
) -> None:
    assignment = _valid_assignment_config()
    assignment["basic_requirements"] = {key: value}

    with pytest.raises(AssignmentConfigError, match=key):
        load_assignment_config(_write_assignment(tmp_path, assignment))


@pytest.mark.parametrize(
    "requirements",
    [
        {"paragraphs_min": 7, "paragraphs_max": 6},
        {"word_count_min": 1201, "word_count_max": 1200},
        {"required_elements": "thesis"},
        {"required_elements": ["thesis", " "]},
    ],
)
def test_basic_requirements_reject_invalid_values(
    tmp_path: Path, requirements: dict[str, object]
) -> None:
    assignment = _valid_assignment_config()
    assignment["basic_requirements"] = requirements

    with pytest.raises(AssignmentConfigError, match="basic_requirements|required_elements"):
        load_assignment_config(_write_assignment(tmp_path, assignment))


def test_minimum_requirement_policy_requires_boolean(tmp_path: Path) -> None:
    assignment = _valid_assignment_config()
    assignment["minimum_requirement_policy"] = {
        "allow_return_without_full_review": "yes"
    }

    with pytest.raises(
        AssignmentConfigError, match="allow_return_without_full_review"
    ):
        load_assignment_config(_write_assignment(tmp_path, assignment))


def test_missing_file_raises_clear_error() -> None:
    with pytest.raises(AssignmentConfigError, match="Assignment config not found"):
        load_assignment_config("missing_assignment_file.json")


def test_invalid_json_raises_clear_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="not valid JSON"):
        load_assignment_config(assignment_path)


def test_valid_json_that_is_not_object_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_path.write_text("[]", encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="must be a JSON object"):
        load_assignment_config(assignment_path)
