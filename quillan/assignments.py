"""Assignment config loading and validation for Quillan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ALLOWED_TAGGING_MODES = {"focus", "focus_plus_past", "benchmark", "custom"}


class AssignmentConfigError(ValueError):
    """Raised when an assignment config is missing or invalid."""


def load_assignment_config(path: str | Path) -> dict[str, Any]:
    """Load and validate an assignment config from a JSON file."""
    assignment_path = Path(path)

    try:
        with assignment_path.open("r", encoding="utf-8") as file:
            assignment = json.load(file)
    except FileNotFoundError as error:
        raise AssignmentConfigError(
            f"Assignment config not found: {assignment_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise AssignmentConfigError(
            f"Assignment config is not valid JSON: {assignment_path}"
        ) from error

    if not isinstance(assignment, dict):
        raise AssignmentConfigError(
            f"Assignment config must be a JSON object: {assignment_path}"
        )

    assignment_dict = cast(dict[str, Any], assignment)
    validate_assignment_config(assignment_dict)
    return assignment_dict


def validate_assignment_config(assignment: dict[str, Any]) -> None:
    """Validate the structure of an assignment config."""
    required_fields = [
        "assignment_id",
        "title",
        "class_ids",
        "writing_type",
        "standards_profile_id",
        "tagging_mode",
        "focus_standards",
        "basic_requirements",
        "rubric_id",
    ]

    for field in required_fields:
        _require_field(assignment, field, "assignment config")

    _validate_class_ids(assignment["class_ids"])
    _validate_tagging_mode(assignment["tagging_mode"])
    _validate_focus_standards(assignment["focus_standards"])
    _validate_basic_requirements(assignment["basic_requirements"])


def _validate_class_ids(class_ids: Any) -> None:
    """Validate assignment class IDs."""
    if not isinstance(class_ids, list):
        raise AssignmentConfigError("Field 'class_ids' must be a list.")

    if not class_ids:
        raise AssignmentConfigError("Field 'class_ids' must not be empty.")

    for class_id in class_ids:
        if not isinstance(class_id, str) or not class_id:
            raise AssignmentConfigError(
                "Each value in 'class_ids' must be a non-empty string."
            )


def _validate_tagging_mode(tagging_mode: Any) -> None:
    """Validate assignment tagging mode."""
    if tagging_mode not in ALLOWED_TAGGING_MODES:
        allowed = ", ".join(sorted(ALLOWED_TAGGING_MODES))
        raise AssignmentConfigError(
            f"Invalid tagging mode '{tagging_mode}'. Allowed values: {allowed}."
        )


def _validate_focus_standards(focus_standards: Any) -> None:
    """Validate assignment focus standards."""
    if not isinstance(focus_standards, list):
        raise AssignmentConfigError("Field 'focus_standards' must be a list.")

    for standard_code in focus_standards:
        if not isinstance(standard_code, str) or not standard_code:
            raise AssignmentConfigError(
                "Each value in 'focus_standards' must be a non-empty string."
            )


def _validate_basic_requirements(basic_requirements: Any) -> None:
    """Validate assignment basic requirements."""
    if not isinstance(basic_requirements, dict):
        raise AssignmentConfigError("Field 'basic_requirements' must be an object.")

    for key, value in basic_requirements.items():
        if key in {
            "paragraphs_min",
            "paragraphs_max",
            "word_count_min",
            "word_count_max",
        }:
            _validate_non_negative_integer_requirement(key, value)

    if "required_elements" in basic_requirements:
        required_elements = basic_requirements["required_elements"]

        if not isinstance(required_elements, list):
            raise AssignmentConfigError(
                "Field 'required_elements' in 'basic_requirements' must be a list."
            )

        for element in required_elements:
            if not isinstance(element, str) or not element:
                raise AssignmentConfigError(
                    "Each value in 'required_elements' must be a non-empty string."
                )


def _validate_non_negative_integer_requirement(key: str, value: Any) -> None:
    """Validate a non-negative integer requirement value."""
    if not isinstance(value, int) or value < 0:
        raise AssignmentConfigError(
            f"Field '{key}' in 'basic_requirements' must be a non-negative integer."
        )


def _require_field(data: dict[str, Any], field: str, context: str) -> None:
    """Require a field to exist and contain a non-empty value."""
    if field not in data:
        raise AssignmentConfigError(f"Missing required field '{field}' in {context}.")

    if data[field] in ("", None):
        raise AssignmentConfigError(f"Field '{field}' in {context} must not be empty.")
