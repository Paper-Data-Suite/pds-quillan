"""Loading, canonical paths, and validation for shared comment banks."""

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
        "bank_id",
        "title",
        "description",
        "scope",
        "writing_types",
        "categories",
        "comments",
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
REQUIRED_COMMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "comment_id",
        "label",
        "text",
        "category_id",
        "polarity",
        "include_in_feedback_default",
        "student_facing",
        "module_details",
    }
)
OPTIONAL_COMMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "short_text",
        "subcategory",
        "writing_types",
        "standard_codes",
        "criterion_ids",
        "severity_default",
        "tags",
        "hotwords",
        "teacher_note",
        "follow_up_prompt",
        "revision_action",
        "sort_order",
        "created_at",
        "updated_at",
    }
)
ALLOWED_SCOPES: Final[frozenset[str]] = frozenset(
    {"shared", "assignment_local", "district", "system"}
)
ALLOWED_POLARITIES: Final[frozenset[str]] = frozenset(
    {"positive", "developing", "negative", "neutral"}
)


class CommentBankError(ValueError):
    """Raised when a shared comment bank is missing or invalid."""


def comment_bank_path(workspace_root: str | Path, bank_id: str) -> Path:
    """Return the canonical path for one shared comment bank."""
    _validate_identifier(bank_id, "bank_id")
    return Path(workspace_root) / "shared" / "comment_banks" / f"{bank_id}.json"


def load_comment_bank(path: str | Path) -> dict[str, Any]:
    """Load and validate a version 1 shared comment bank."""
    bank_path = Path(path)
    try:
        with bank_path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as error:
        raise CommentBankError(f"Comment bank not found: {bank_path}") from error
    except json.JSONDecodeError as error:
        raise CommentBankError(
            f"Comment bank is not valid JSON: {bank_path}"
        ) from error
    except OSError as error:
        raise CommentBankError(
            f"Could not read comment bank {bank_path}: {error}"
        ) from error

    if not isinstance(value, dict):
        raise CommentBankError(f"Comment bank must be a JSON object: {bank_path}")
    bank = cast(dict[str, Any], value)
    validate_comment_bank(bank)
    if bank["bank_id"] != bank_path.stem:
        raise CommentBankError(
            f"Comment bank bank_id is {bank['bank_id']!r}, expected "
            f"{bank_path.stem!r} from its filename."
        )
    return bank


def validate_comment_bank(bank: dict[str, Any]) -> None:
    """Validate the intrinsic version 1 shared comment-bank contract."""
    if not isinstance(bank, dict):
        raise CommentBankError("Comment bank must be an object.")
    _validate_fields(bank, REQUIRED_BANK_FIELDS, frozenset(), "comment bank")
    _validate_exact(bank["schema_version"], "schema_version", "1")
    _validate_exact(bank["module"], "module", "quillan")
    _validate_exact(bank["record_type"], "record_type", "comment_bank")
    _validate_identifier(bank["bank_id"], "bank_id")
    _validate_non_empty_string(bank["title"], "title")
    _validate_string(bank["description"], "description")
    _validate_allowed(bank["scope"], "scope", ALLOWED_SCOPES)
    writing_types = _validate_unique_strings(
        bank["writing_types"], "writing_types", require_non_empty=True
    )
    category_ids = _validate_categories(bank["categories"])
    _validate_comments(bank["comments"], category_ids, set(writing_types))
    created_at = _validate_timestamp(bank["created_at"], "created_at")
    updated_at = _validate_timestamp(bank["updated_at"], "updated_at")
    if updated_at < created_at:
        raise CommentBankError(
            "Field 'updated_at' must not precede field 'created_at'."
        )
    _validate_object(bank["module_details"], "module_details")


def _validate_categories(value: Any) -> set[str]:
    categories = _validate_list(value, "categories")
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
            raise CommentBankError(f"Duplicate category_id '{category_id}'.")
        seen.add(category_id)
        _validate_non_empty_string(item["label"], f"{context}.label")
        if "description" in item:
            _validate_string(item["description"], f"{context}.description")
        if "sort_order" in item:
            _validate_integer(item["sort_order"], f"{context}.sort_order")
        if "module_details" in item:
            _validate_object(item["module_details"], f"{context}.module_details")
    return seen


def _validate_comments(
    value: Any, category_ids: set[str], bank_writing_types: set[str]
) -> None:
    comments = _validate_list(value, "comments")
    if not comments:
        raise CommentBankError("Field 'comments' must be a non-empty list.")
    seen: set[str] = set()
    for index, value_item in enumerate(comments):
        context = f"comments[{index}]"
        item = _validate_record(value_item, context)
        _validate_fields(
            item, REQUIRED_COMMENT_FIELDS, OPTIONAL_COMMENT_FIELDS, context
        )
        comment_id = _validate_identifier(
            item["comment_id"], f"{context}.comment_id"
        )
        if comment_id in seen:
            raise CommentBankError(f"Duplicate comment_id '{comment_id}'.")
        seen.add(comment_id)
        for field in ("label", "text"):
            _validate_non_empty_string(item[field], f"{context}.{field}")
        category_id = _validate_identifier(
            item["category_id"], f"{context}.category_id"
        )
        if category_id not in category_ids:
            raise CommentBankError(
                f"Field '{context}.category_id' references unknown category "
                f"'{category_id}'."
            )
        _validate_allowed(
            item["polarity"], f"{context}.polarity", ALLOWED_POLARITIES
        )
        for field in ("include_in_feedback_default", "student_facing"):
            if not isinstance(item[field], bool):
                raise CommentBankError(
                    f"Field '{context}.{field}' must be a boolean."
                )
        _validate_object(item["module_details"], f"{context}.module_details")

        for field in (
            "short_text",
            "subcategory",
            "teacher_note",
            "follow_up_prompt",
            "revision_action",
        ):
            if field in item:
                _validate_non_empty_string(item[field], f"{context}.{field}")
        if "writing_types" in item:
            values = _validate_unique_strings(
                item["writing_types"],
                f"{context}.writing_types",
                require_non_empty=True,
            )
            outside = set(values) - bank_writing_types
            if outside:
                raise CommentBankError(
                    f"Field '{context}.writing_types' contains value outside "
                    f"bank writing_types: {sorted(outside)[0]!r}."
                )
        for field in ("standard_codes", "criterion_ids", "tags", "hotwords"):
            if field in item:
                _validate_unique_strings(item[field], f"{context}.{field}")
        if "severity_default" in item:
            value_severity = item["severity_default"]
            if (
                isinstance(value_severity, bool)
                or not isinstance(value_severity, int)
                or value_severity < 0
            ):
                raise CommentBankError(
                    f"Field '{context}.severity_default' must be a "
                    "non-negative integer."
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
        if (
            created_at is not None
            and updated_at is not None
            and updated_at < created_at
        ):
            raise CommentBankError(
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
        raise CommentBankError(
            f"Missing required field '{sorted(missing)[0]}' in {context}."
        )
    unknown = data.keys() - required - optional
    if unknown:
        raise CommentBankError(
            f"Unknown field '{sorted(unknown)[0]}' in {context}."
        )


def _validate_record(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CommentBankError(f"{context} must be an object.")
    return cast(dict[str, Any], value)


def _validate_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CommentBankError(f"Field '{field}' must be a list.")
    return value


def _validate_unique_strings(
    value: Any, field: str, *, require_non_empty: bool = False
) -> list[str]:
    values = _validate_list(value, field)
    if require_non_empty and not values:
        raise CommentBankError(f"Field '{field}' must be a non-empty list.")
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = _validate_non_empty_string(item, field)
        if text in seen:
            raise CommentBankError(f"Field '{field}' contains duplicate {text!r}.")
        seen.add(text)
        result.append(text)
    return result


def _validate_identifier(value: Any, field: str) -> str:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise CommentBankError(str(error)) from error
    return cast(str, value)


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommentBankError(f"Field '{field}' must be a non-empty string.")
    return value


def _validate_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise CommentBankError(f"Field '{field}' must be a string.")
    return value


def _validate_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CommentBankError(f"Field '{field}' must be an integer.")
    return value


def _validate_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise CommentBankError(f"Field '{field}' must be an object.")


def _validate_exact(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise CommentBankError(
            f"Field '{field}' must be the string '{expected}'."
        )


def _validate_allowed(
    value: Any, field: str, allowed_values: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise CommentBankError(
            f"Invalid {field} {value!r}. Allowed values: {allowed}."
        )
    return value


def _validate_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CommentBankError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CommentBankError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CommentBankError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    return parsed
