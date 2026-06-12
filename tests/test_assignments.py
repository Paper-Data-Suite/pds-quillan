"""Tests for assignment config loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quillan.assignments import AssignmentConfigError, load_assignment_config


def _valid_assignment_config() -> dict[str, object]:
    """Return a valid synthetic assignment config."""
    return {
        "assignment_id": "villainy_final_essay_synthetic",
        "title": "Villainy Final Essay",
        "class_ids": ["english12_period3_synthetic"],
        "writing_type": "literary argument essay",
        "standards_profile_id": "english_12_njsls_synthetic",
        "tagging_mode": "focus",
        "focus_standards": [
            "W.AW.11-12.1",
            "W.WP.11-12.4",
        ],
        "basic_requirements": {
            "paragraphs_min": 4,
            "paragraphs_max": 6,
            "word_count_min": 500,
            "required_elements": [
                "thesis",
                "textual evidence",
                "comparative reasoning",
            ],
        },
        "rubric_id": "argument_essay_4pt_synthetic",
    }


def test_load_valid_assignment_config(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    loaded_assignment = load_assignment_config(assignment_path)

    assert loaded_assignment == assignment_data


def test_missing_required_field_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    del assignment_data["rubric_id"]
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(
        AssignmentConfigError, match="Missing required field 'rubric_id'"
    ):
        load_assignment_config(assignment_path)


def test_invalid_tagging_mode_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["tagging_mode"] = "everything"
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="Invalid tagging mode"):
        load_assignment_config(assignment_path)


def test_invalid_assignment_identifier_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["assignment_id"] = "../unsafe"
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="assignment_id"):
        load_assignment_config(assignment_path)


def test_invalid_class_identifier_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["class_ids"] = ["English 12"]
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="class_id"):
        load_assignment_config(assignment_path)


@pytest.mark.parametrize(
    "field",
    ["title", "writing_type", "standards_profile_id", "rubric_id"],
)
def test_required_string_field_must_be_string(tmp_path: Path, field: str) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data[field] = 123
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match=field):
        load_assignment_config(assignment_path)


def test_empty_class_ids_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["class_ids"] = []
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="class_ids.*must not be empty"):
        load_assignment_config(assignment_path)


def test_focus_standards_must_be_list(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["focus_standards"] = "W.AW.11-12.1"
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="focus_standards.*must be a list"):
        load_assignment_config(assignment_path)


def test_focus_standards_reject_whitespace_only_value(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["focus_standards"] = ["   "]
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="focus_standards"):
        load_assignment_config(assignment_path)


def test_basic_requirements_must_be_object(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["basic_requirements"] = []
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="basic_requirements.*object"):
        load_assignment_config(assignment_path)


def test_negative_requirement_value_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["basic_requirements"] = {
        "paragraphs_min": -1,
    }
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="paragraphs_min"):
        load_assignment_config(assignment_path)


def test_boolean_requirement_value_raises_error(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["basic_requirements"] = {
        "paragraphs_min": True,
    }
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="paragraphs_min"):
        load_assignment_config(assignment_path)


def test_required_elements_must_be_list(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["basic_requirements"] = {
        "required_elements": "thesis",
    }
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(
        AssignmentConfigError, match="required_elements.*must be a list"
    ):
        load_assignment_config(assignment_path)


def test_required_elements_reject_whitespace_only_value(tmp_path: Path) -> None:
    assignment_path = tmp_path / "assignment.json"
    assignment_data = _valid_assignment_config()
    assignment_data["basic_requirements"] = {
        "required_elements": ["   "],
    }
    assignment_path.write_text(json.dumps(assignment_data), encoding="utf-8")

    with pytest.raises(AssignmentConfigError, match="required_elements"):
        load_assignment_config(assignment_path)


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
