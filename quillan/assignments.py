"""Assignment config loading and validation for Quillan."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import (
    StandardsLibrary,
    StandardsValidationError,
    validate_profile_standard_selection,
)

ASSIGNMENT_SCHEMA_VERSION = "2"
ASSIGNMENT_MODULE = "quillan"
ASSIGNMENT_RECORD_TYPE = "assignment"
_SIMPLE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_LEGACY_ASSIGNMENT_FIELDS = frozenset({"tagging_mode", "focus_standards", "rubric_id"})


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
    """Validate the v2 structure of an assignment config."""
    _reject_legacy_assignment_config(assignment)

    required_fields = [
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
    ]

    for field in required_fields:
        _require_field(assignment, field, "assignment config")

    _validate_fixed_value(
        assignment["schema_version"], "schema_version", ASSIGNMENT_SCHEMA_VERSION
    )
    _validate_fixed_value(assignment["module"], "module", ASSIGNMENT_MODULE)
    _validate_fixed_value(
        assignment["record_type"], "record_type", ASSIGNMENT_RECORD_TYPE
    )
    _validate_identifier(assignment["assignment_id"], "assignment_id")
    _validate_non_empty_string(assignment["title"], "title")
    _validate_class_ids(assignment["class_ids"])
    _validate_non_empty_string(assignment["writing_type"], "writing_type")
    _validate_non_empty_string(assignment["student_prompt"], "student_prompt")
    _validate_non_empty_string(
        assignment["standards_profile_id"], "standards_profile_id"
    )
    _validate_focus_standard_ids(assignment["focus_standard_ids"])
    _validate_review_unit(assignment["review_unit"])
    _validate_rating_scale(assignment["rating_scale"])
    _validate_basic_requirements(assignment["basic_requirements"])
    _validate_minimum_requirement_policy(assignment["minimum_requirement_policy"])


def validate_assignment_standards_selection(
    assignment: dict[str, Any],
    standards_library: StandardsLibrary,
) -> tuple[str, ...]:
    """Validate assignment standards against a shared pds-core library.

    The returned values are normalized shared ``standard_id`` references.
    Structural assignment validation remains available separately through
    ``validate_assignment_config`` for callers that do not have a workspace
    standards library loaded.
    """
    validate_assignment_config(assignment)

    profile_id = cast(str, assignment["standards_profile_id"])
    focus_standard_ids = cast(list[str], assignment["focus_standard_ids"])

    try:
        return validate_profile_standard_selection(
            standards_library,
            profile_id=profile_id,
            selected_standard_ids=focus_standard_ids,
        )
    except StandardsValidationError as error:
        raise AssignmentConfigError(
            "Invalid assignment standards selection for "
            f"standards_profile_id {profile_id!r} and focus_standard_ids: {error}"
        ) from error


def _reject_legacy_assignment_config(assignment: dict[str, Any]) -> None:
    schema_version = assignment.get("schema_version")
    legacy_fields = sorted(_LEGACY_ASSIGNMENT_FIELDS.intersection(assignment))
    if schema_version == ASSIGNMENT_SCHEMA_VERSION and not legacy_fields:
        return

    if schema_version != ASSIGNMENT_SCHEMA_VERSION:
        detail = "missing" if schema_version is None else repr(schema_version)
        if legacy_fields:
            raise AssignmentConfigError(
                "Legacy assignment configs are not supported by the v2 "
                "standards-based assignment loader. Unsupported schema_version "
                f"is {detail}; legacy fields present: {', '.join(legacy_fields)}."
            )
        raise AssignmentConfigError(
            "Unsupported assignment schema_version "
            f"{detail}; expected {ASSIGNMENT_SCHEMA_VERSION!r}."
        )

    raise AssignmentConfigError(
        "Legacy assignment fields are not supported by the v2 standards-based "
        f"assignment loader: {', '.join(legacy_fields)}."
    )


def _validate_class_ids(class_ids: Any) -> None:
    """Validate assignment class IDs."""
    if not isinstance(class_ids, list):
        raise AssignmentConfigError("Field 'class_ids' must be a list.")

    if not class_ids:
        raise AssignmentConfigError("Field 'class_ids' must not be empty.")

    seen_class_ids: set[str] = set()
    for class_id in class_ids:
        _validate_identifier(class_id, "class_id")
        if class_id in seen_class_ids:
            raise AssignmentConfigError(f"Duplicate class_id: {class_id}.")
        seen_class_ids.add(class_id)


def _validate_focus_standard_ids(focus_standard_ids: Any) -> None:
    """Validate assignment focus standard IDs."""
    if not isinstance(focus_standard_ids, list):
        raise AssignmentConfigError("Field 'focus_standard_ids' must be a list.")

    if not focus_standard_ids:
        raise AssignmentConfigError("Field 'focus_standard_ids' must not be empty.")

    for standard_id in focus_standard_ids:
        if not isinstance(standard_id, str) or not standard_id.strip():
            raise AssignmentConfigError(
                "Each value in 'focus_standard_ids' must be a non-empty string."
            )


def _validate_review_unit(review_unit: Any) -> None:
    if not isinstance(review_unit, dict):
        raise AssignmentConfigError("Field 'review_unit' must be an object.")

    for field in ("type", "singular_label", "plural_label"):
        _require_field(review_unit, field, "review_unit")
        _validate_non_empty_string(review_unit[field], f"review_unit.{field}")

    unit_type = cast(str, review_unit["type"])
    if _SIMPLE_IDENTIFIER_PATTERN.fullmatch(unit_type.strip()) is None:
        raise AssignmentConfigError(
            "Field 'review_unit.type' must be a simple identifier-like string."
        )


def _validate_rating_scale(rating_scale: Any) -> None:
    if not isinstance(rating_scale, dict):
        raise AssignmentConfigError("Field 'rating_scale' must be an object.")

    for field in ("scale_id", "levels"):
        _require_field(rating_scale, field, "rating_scale")
    _validate_non_empty_string(rating_scale["scale_id"], "rating_scale.scale_id")

    levels = rating_scale["levels"]
    if not isinstance(levels, list):
        raise AssignmentConfigError("Field 'rating_scale.levels' must be a list.")
    if not levels:
        raise AssignmentConfigError("Field 'rating_scale.levels' must not be empty.")

    seen_values: set[int] = set()
    for index, level in enumerate(levels):
        if not isinstance(level, dict):
            raise AssignmentConfigError(
                f"Each value in 'rating_scale.levels' must be an object; "
                f"level {index + 1} is invalid."
            )
        for field in ("value", "label", "description"):
            _require_field(level, field, f"rating_scale.levels[{index}]")

        value = level["value"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise AssignmentConfigError(
                "Each 'value' in 'rating_scale.levels' must be an integer."
            )
        if value in seen_values:
            raise AssignmentConfigError(
                f"Duplicate rating_scale level value: {value}."
            )
        seen_values.add(value)
        _validate_non_empty_string(level["label"], "rating_scale.levels.label")
        _validate_non_empty_string(
            level["description"], "rating_scale.levels.description"
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
            if not isinstance(element, str) or not element.strip():
                raise AssignmentConfigError(
                    "Each value in 'required_elements' must be a non-empty string."
                )

    _validate_min_max_requirement(
        basic_requirements,
        minimum_key="paragraphs_min",
        maximum_key="paragraphs_max",
    )
    _validate_min_max_requirement(
        basic_requirements,
        minimum_key="word_count_min",
        maximum_key="word_count_max",
    )


def _validate_min_max_requirement(
    requirements: dict[str, Any],
    *,
    minimum_key: str,
    maximum_key: str,
) -> None:
    minimum = requirements.get(minimum_key)
    maximum = requirements.get(maximum_key)
    if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
        raise AssignmentConfigError(
            f"Field '{minimum_key}' in 'basic_requirements' must not exceed "
            f"'{maximum_key}'."
        )


def _validate_minimum_requirement_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise AssignmentConfigError(
            "Field 'minimum_requirement_policy' must be an object."
        )
    _require_field(
        policy,
        "allow_return_without_full_review",
        "minimum_requirement_policy",
    )
    value = policy["allow_return_without_full_review"]
    if not isinstance(value, bool):
        raise AssignmentConfigError(
            "Field 'allow_return_without_full_review' in "
            "'minimum_requirement_policy' must be a boolean."
        )


def _validate_non_negative_integer_requirement(key: str, value: Any) -> None:
    """Validate a non-negative integer requirement value."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AssignmentConfigError(
            f"Field '{key}' in 'basic_requirements' must be a non-negative integer."
        )


def _validate_identifier(value: Any, field: str) -> None:
    """Validate a shared Paper Data Suite identifier."""
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise AssignmentConfigError(str(error)) from error


def _validate_non_empty_string(value: Any, field: str) -> None:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise AssignmentConfigError(f"Field '{field}' must be a non-empty string.")


def _validate_fixed_value(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise AssignmentConfigError(
            f"Field '{field}' must be {expected!r}; got {value!r}."
        )


def _require_field(data: dict[str, Any], field: str, context: str) -> None:
    """Require a field to exist and contain a non-empty value."""
    if field not in data:
        raise AssignmentConfigError(f"Missing required field '{field}' in {context}.")

    if data[field] in ("", None):
        raise AssignmentConfigError(f"Field '{field}' in {context} must not be empty.")
