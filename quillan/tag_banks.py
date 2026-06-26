"""Loading, canonical paths, and validation for shared tag banks."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

REQUIRED_BANK_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "module",
        "record_type",
        "tag_bank_id",
        "title",
        "description",
        "scope",
        "writing_types",
        "categories",
        "tags",
        "created_at",
        "updated_at",
        "module_details",
    }
)
REQUIRED_CATEGORY_FIELDS: Final[frozenset[str]] = frozenset(
    {"category_id", "label"}
)
OPTIONAL_CATEGORY_FIELDS: Final[frozenset[str]] = frozenset(
    {"description", "sort_order", "module_details"}
)
REQUIRED_TAG_FIELDS: Final[frozenset[str]] = frozenset(
    {"tag_template_id", "label", "category_id", "polarity", "module_details"}
)
OPTIONAL_TAG_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "description",
        "writing_types",
        "standard_ids",
        "criterion_ids",
        "severity_default",
        "teacher_note_prompt",
        "student_facing_default",
        "sort_order",
        "created_at",
        "updated_at",
    }
)
ALLOWED_SCOPES: Final[frozenset[str]] = frozenset({"shared"})
ALLOWED_POLARITIES: Final[frozenset[str]] = frozenset(
    {"positive", "developing", "negative", "neutral"}
)


class TagBankError(ValueError):
    """Raised when a shared tag bank is missing or invalid."""


def tag_bank_path(workspace_root: str | Path, tag_bank_id: str) -> Path:
    """Return the canonical path for one shared tag bank."""
    _validate_identifier(tag_bank_id, "tag_bank_id")
    return Path(workspace_root) / "shared" / "tag_banks" / f"{tag_bank_id}.json"


def load_tag_bank(path: str | Path) -> dict[str, Any]:
    """Load and validate a version 1 shared tag bank."""
    bank_path = Path(path)
    try:
        with bank_path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as error:
        raise TagBankError(f"Tag bank not found: {bank_path}") from error
    except json.JSONDecodeError as error:
        raise TagBankError(f"Tag bank is not valid JSON: {bank_path}") from error
    except OSError as error:
        raise TagBankError(f"Could not read tag bank {bank_path}: {error}") from error

    if not isinstance(value, dict):
        raise TagBankError(f"Tag bank must be a JSON object: {bank_path}")
    bank = cast(dict[str, Any], value)
    validate_tag_bank(bank)
    if bank["tag_bank_id"] != bank_path.stem:
        raise TagBankError(
            f"Tag bank tag_bank_id is {bank['tag_bank_id']!r}, expected "
            f"{bank_path.stem!r} from its filename."
        )
    return bank


def validate_tag_bank(bank: dict[str, Any]) -> None:
    """Validate the intrinsic version 1 shared tag-bank contract."""
    if not isinstance(bank, dict):
        raise TagBankError("Tag bank must be an object.")
    _validate_fields(bank, REQUIRED_BANK_FIELDS, frozenset(), "tag bank")
    _validate_exact(bank["schema_version"], "schema_version", "1")
    _validate_exact(bank["module"], "module", "quillan")
    _validate_exact(bank["record_type"], "record_type", "tag_bank")
    _validate_identifier(bank["tag_bank_id"], "tag_bank_id")
    _validate_non_empty_string(bank["title"], "title")
    _validate_string(bank["description"], "description")
    _validate_allowed(bank["scope"], "scope", ALLOWED_SCOPES)
    writing_types = _validate_unique_strings(
        bank["writing_types"], "writing_types", require_non_empty=True
    )
    category_ids = _validate_categories(bank["categories"])
    _validate_tags(bank["tags"], category_ids, set(writing_types))
    created_at = _validate_timestamp(bank["created_at"], "created_at")
    updated_at = _validate_timestamp(bank["updated_at"], "updated_at")
    if updated_at < created_at:
        raise TagBankError("Field 'updated_at' must not precede field 'created_at'.")
    _validate_object(bank["module_details"], "module_details")


def _validate_categories(value: Any) -> set[str]:
    categories = _validate_list(value, "categories")
    if not categories:
        raise TagBankError("Field 'categories' must be a non-empty list.")
    seen: set[str] = set()
    for index, value_item in enumerate(categories):
        context = f"categories[{index}]"
        item = _validate_record(value_item, context)
        _validate_fields(
            item, REQUIRED_CATEGORY_FIELDS, OPTIONAL_CATEGORY_FIELDS, context
        )
        category_id = _validate_identifier(
            item["category_id"], f"{context}.category_id"
        )
        if category_id in seen:
            raise TagBankError(f"Duplicate category_id '{category_id}'.")
        seen.add(category_id)
        _validate_non_empty_string(item["label"], f"{context}.label")
        if "description" in item:
            _validate_string(item["description"], f"{context}.description")
        if "sort_order" in item:
            _validate_integer(item["sort_order"], f"{context}.sort_order")
        if "module_details" in item:
            _validate_object(item["module_details"], f"{context}.module_details")
    return seen


def _validate_tags(
    value: Any, category_ids: set[str], bank_writing_types: set[str]
) -> None:
    tags = _validate_list(value, "tags")
    if not tags:
        raise TagBankError("Field 'tags' must be a non-empty list.")
    seen: set[str] = set()
    for index, value_item in enumerate(tags):
        context = f"tags[{index}]"
        item = _validate_record(value_item, context)
        _validate_fields(item, REQUIRED_TAG_FIELDS, OPTIONAL_TAG_FIELDS, context)
        tag_template_id = _validate_identifier(
            item["tag_template_id"], f"{context}.tag_template_id"
        )
        if tag_template_id in seen:
            raise TagBankError(f"Duplicate tag_template_id '{tag_template_id}'.")
        seen.add(tag_template_id)
        _validate_non_empty_string(item["label"], f"{context}.label")
        category_id = _validate_identifier(
            item["category_id"], f"{context}.category_id"
        )
        if category_id not in category_ids:
            raise TagBankError(
                f"Field '{context}.category_id' references unknown category "
                f"'{category_id}'."
            )
        _validate_allowed(item["polarity"], f"{context}.polarity", ALLOWED_POLARITIES)
        _validate_object(item["module_details"], f"{context}.module_details")
        if "description" in item:
            _validate_string(item["description"], f"{context}.description")
        if "teacher_note_prompt" in item:
            _validate_non_empty_string(
                item["teacher_note_prompt"], f"{context}.teacher_note_prompt"
            )
        if "writing_types" in item:
            values = _validate_unique_strings(
                item["writing_types"],
                f"{context}.writing_types",
                require_non_empty=True,
            )
            outside = set(values) - bank_writing_types
            if outside:
                raise TagBankError(
                    f"Field '{context}.writing_types' contains value outside "
                    f"bank writing_types: {sorted(outside)[0]!r}."
                )
        for field in ("standard_ids", "criterion_ids"):
            if field in item:
                _validate_unique_strings(item[field], f"{context}.{field}")
        if "severity_default" in item:
            value_severity = item["severity_default"]
            if (
                isinstance(value_severity, bool)
                or not isinstance(value_severity, int)
                or value_severity < 0
            ):
                raise TagBankError(
                    f"Field '{context}.severity_default' must be a "
                    "non-negative integer."
                )
        if "student_facing_default" in item and not isinstance(
            item["student_facing_default"], bool
        ):
            raise TagBankError(
                f"Field '{context}.student_facing_default' must be a boolean."
            )
        if "sort_order" in item:
            _validate_integer(item["sort_order"], f"{context}.sort_order")
        created_at = (
            _validate_timestamp(item["created_at"], f"{context}.created_at")
            if "created_at" in item
            else None
        )
        updated_at = (
            _validate_timestamp(item["updated_at"], f"{context}.updated_at")
            if "updated_at" in item
            else None
        )
        if created_at is not None and updated_at is not None and updated_at < created_at:
            raise TagBankError(
                f"Field '{context}.updated_at' must not precede "
                f"field '{context}.created_at'."
            )


def _validate_fields(
    data: dict[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
    context: str,
) -> None:
    missing = required - data.keys()
    if missing:
        raise TagBankError(
            f"Missing required field '{sorted(missing)[0]}' in {context}."
        )
    unknown = data.keys() - required - optional
    if unknown:
        raise TagBankError(f"Unknown field '{sorted(unknown)[0]}' in {context}.")


def _validate_record(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TagBankError(f"{context} must be an object.")
    return cast(dict[str, Any], value)


def _validate_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise TagBankError(f"Field '{field}' must be a list.")
    return value


def _validate_unique_strings(
    value: Any, field: str, *, require_non_empty: bool = False
) -> list[str]:
    values = _validate_list(value, field)
    if require_non_empty and not values:
        raise TagBankError(f"Field '{field}' must be a non-empty list.")
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = _validate_non_empty_string(item, field)
        if text in seen:
            raise TagBankError(f"Field '{field}' contains duplicate {text!r}.")
        seen.add(text)
        result.append(text)
    return result


def _validate_identifier(value: Any, field: str) -> str:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise TagBankError(str(error)) from error
    return cast(str, value)


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TagBankError(f"Field '{field}' must be a non-empty string.")
    return value


def _validate_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise TagBankError(f"Field '{field}' must be a string.")
    return value


def _validate_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TagBankError(f"Field '{field}' must be an integer.")
    return value


def _validate_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise TagBankError(f"Field '{field}' must be an object.")


def _validate_exact(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise TagBankError(f"Field '{field}' must be the string '{expected}'.")


def _validate_allowed(
    value: Any, field: str, allowed_values: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise TagBankError(f"Invalid {field} {value!r}. Allowed values: {allowed}.")
    return value


def _validate_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise TagBankError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise TagBankError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TagBankError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    return parsed
