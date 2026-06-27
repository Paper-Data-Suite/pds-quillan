"""Loading, canonical paths, and validation for shared rubrics."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

REQUIRED_RUBRIC_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "module",
        "record_type",
        "rubric_id",
        "title",
        "description",
        "scope",
        "writing_types",
        "criteria",
        "created_at",
        "updated_at",
        "module_details",
    }
)
REQUIRED_CRITERION_FIELDS: Final[frozenset[str]] = frozenset(
    {"criterion_id", "label", "max_score", "scale", "levels", "module_details"}
)
OPTIONAL_CRITERION_FIELDS: Final[frozenset[str]] = frozenset(
    {"description", "standard_ids", "sort_order"}
)
REQUIRED_LEVEL_FIELDS: Final[frozenset[str]] = frozenset(
    {"score", "label", "module_details"}
)
OPTIONAL_LEVEL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "description",
        "student_facing_feedback",
        "teacher_note",
        "sort_order",
    }
)
ALLOWED_SCOPES: Final[frozenset[str]] = frozenset({"shared"})


class RubricError(ValueError):
    """Raised when a shared rubric is missing or invalid."""


@dataclass(frozen=True)
class RubricFile:
    """One discovered rubric file and its validation state."""

    path: Path
    rubric: dict[str, Any] | None
    error: str | None

    @property
    def is_valid(self) -> bool:
        return self.rubric is not None and self.error is None


def rubric_path(workspace_root: str | Path, rubric_id: str) -> Path:
    """Return the canonical path for one shared rubric."""
    _validate_identifier(rubric_id, "rubric_id")
    return Path(workspace_root) / "shared" / "rubrics" / f"{rubric_id}.json"


def load_rubric(path: str | Path) -> dict[str, Any]:
    """Load and validate a version 1 shared rubric."""
    path_obj = Path(path)
    try:
        with path_obj.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as error:
        raise RubricError(f"Rubric not found: {path_obj}") from error
    except json.JSONDecodeError as error:
        raise RubricError(f"Rubric is not valid JSON: {path_obj}") from error
    except OSError as error:
        raise RubricError(f"Could not read rubric {path_obj}: {error}") from error

    if not isinstance(value, dict):
        raise RubricError(f"Rubric must be a JSON object: {path_obj}")
    rubric = cast(dict[str, Any], value)
    validate_rubric(rubric)
    if rubric["rubric_id"] != path_obj.stem:
        raise RubricError(
            f"Rubric rubric_id is {rubric['rubric_id']!r}, expected "
            f"{path_obj.stem!r} from its filename."
        )
    return rubric


def list_rubric_files(workspace_root: str | Path) -> tuple[RubricFile, ...]:
    """List shared rubric files without raising on invalid files."""
    directory = Path(workspace_root) / "shared" / "rubrics"
    if not directory.is_dir():
        return ()
    files: list[RubricFile] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            files.append(RubricFile(path, load_rubric(path), None))
        except (OSError, RubricError) as error:
            files.append(RubricFile(path, None, str(error)))
    return tuple(files)


def list_valid_rubrics(workspace_root: str | Path) -> tuple[RubricFile, ...]:
    """Return valid shared rubric files only."""
    return tuple(item for item in list_rubric_files(workspace_root) if item.is_valid)


def validate_rubric(rubric: dict[str, Any]) -> None:
    """Validate the intrinsic version 1 shared-rubric contract."""
    if not isinstance(rubric, dict):
        raise RubricError("Rubric must be an object.")
    _validate_fields(rubric, REQUIRED_RUBRIC_FIELDS, frozenset(), "rubric")
    _validate_exact(rubric["schema_version"], "schema_version", "1")
    _validate_exact(rubric["module"], "module", "quillan")
    _validate_exact(rubric["record_type"], "record_type", "rubric")
    _validate_identifier(rubric["rubric_id"], "rubric_id")
    _validate_non_empty_string(rubric["title"], "title")
    _validate_string(rubric["description"], "description")
    _validate_allowed(rubric["scope"], "scope", ALLOWED_SCOPES)
    _validate_unique_strings(
        rubric["writing_types"], "writing_types", require_non_empty=True
    )
    _validate_criteria(rubric["criteria"])
    created_at = _validate_timestamp(rubric["created_at"], "created_at")
    updated_at = _validate_timestamp(rubric["updated_at"], "updated_at")
    if updated_at < created_at:
        raise RubricError("Field 'updated_at' must not precede field 'created_at'.")
    _validate_object(rubric["module_details"], "module_details")


def _validate_criteria(value: Any) -> None:
    criteria = _validate_list(value, "criteria")
    if not criteria:
        raise RubricError("Field 'criteria' must be a non-empty list.")
    seen: set[str] = set()
    for index, value_item in enumerate(criteria):
        context = f"criteria[{index}]"
        item = _validate_record(value_item, context)
        _validate_fields(
            item,
            REQUIRED_CRITERION_FIELDS,
            OPTIONAL_CRITERION_FIELDS,
            context,
        )
        criterion_id = _validate_identifier(
            item["criterion_id"], f"{context}.criterion_id"
        )
        if criterion_id in seen:
            raise RubricError(f"Duplicate criterion_id '{criterion_id}'.")
        seen.add(criterion_id)
        _validate_non_empty_string(item["label"], f"{context}.label")
        max_score = _validate_number(
            item["max_score"],
            f"{context}.max_score",
            minimum=0,
            exclusive_minimum=True,
        )
        _validate_non_empty_string(item["scale"], f"{context}.scale")
        _validate_levels(item["levels"], max_score, context)
        _validate_object(item["module_details"], f"{context}.module_details")
        if "description" in item:
            _validate_string(item["description"], f"{context}.description")
        if "standard_ids" in item:
            _validate_unique_strings(item["standard_ids"], f"{context}.standard_ids")
        if "sort_order" in item:
            _validate_integer(item["sort_order"], f"{context}.sort_order")


def _validate_levels(value: Any, max_score: int | float, context: str) -> None:
    levels = _validate_list(value, f"{context}.levels")
    if not levels:
        raise RubricError(f"Field '{context}.levels' must be a non-empty list.")
    seen_scores: set[int | float] = set()
    for index, value_item in enumerate(levels):
        level_context = f"{context}.levels[{index}]"
        item = _validate_record(value_item, level_context)
        _validate_fields(
            item,
            REQUIRED_LEVEL_FIELDS,
            OPTIONAL_LEVEL_FIELDS,
            level_context,
        )
        score = _validate_number(item["score"], f"{level_context}.score", minimum=0)
        if score > max_score:
            raise RubricError(
                f"Field '{level_context}.score' must not exceed criterion max_score."
            )
        if score in seen_scores:
            raise RubricError(f"Duplicate level score '{score}' in {context}.")
        seen_scores.add(score)
        _validate_non_empty_string(item["label"], f"{level_context}.label")
        _validate_object(item["module_details"], f"{level_context}.module_details")
        for field in ("description", "student_facing_feedback", "teacher_note"):
            if field in item:
                _validate_string(item[field], f"{level_context}.{field}")
        if "sort_order" in item:
            _validate_integer(item["sort_order"], f"{level_context}.sort_order")


def _validate_fields(
    data: dict[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
    context: str,
) -> None:
    missing = required - data.keys()
    if missing:
        raise RubricError(
            f"Missing required field '{sorted(missing)[0]}' in {context}."
        )
    unknown = data.keys() - required - optional
    if unknown:
        raise RubricError(f"Unknown field '{sorted(unknown)[0]}' in {context}.")


def _validate_record(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RubricError(f"{context} must be an object.")
    return cast(dict[str, Any], value)


def _validate_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise RubricError(f"Field '{field}' must be a list.")
    return value


def _validate_unique_strings(
    value: Any, field: str, *, require_non_empty: bool = False
) -> list[str]:
    values = _validate_list(value, field)
    if require_non_empty and not values:
        raise RubricError(f"Field '{field}' must be a non-empty list.")
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = _validate_non_empty_string(item, field)
        if text in seen:
            raise RubricError(f"Field '{field}' contains duplicate {text!r}.")
        seen.add(text)
        result.append(text)
    return result


def _validate_identifier(value: Any, field: str) -> str:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise RubricError(str(error)) from error
    return cast(str, value)


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RubricError(f"Field '{field}' must be a non-empty string.")
    return value


def _validate_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise RubricError(f"Field '{field}' must be a string.")
    return value


def _validate_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RubricError(f"Field '{field}' must be an integer.")
    return value


def _validate_number(
    value: Any,
    field: str,
    *,
    minimum: int,
    exclusive_minimum: bool = False,
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RubricError(f"Field '{field}' must be a finite number.")
    if not math.isfinite(value):
        raise RubricError(f"Field '{field}' must be a finite number.")
    if exclusive_minimum and value <= minimum:
        raise RubricError(f"Field '{field}' must be greater than {minimum}.")
    if not exclusive_minimum and value < minimum:
        raise RubricError(
            f"Field '{field}' must be greater than or equal to {minimum}."
        )
    return value


def _validate_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise RubricError(f"Field '{field}' must be an object.")


def _validate_exact(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise RubricError(f"Field '{field}' must be the string '{expected}'.")


def _validate_allowed(
    value: Any, field: str, allowed_values: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise RubricError(f"Invalid {field} {value!r}. Allowed values: {allowed}.")
    return value


def _validate_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RubricError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise RubricError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RubricError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    return parsed
