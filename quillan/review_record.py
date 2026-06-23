"""Loading and validation for Quillan submission review records."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

REQUIRED_REVIEW_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "module",
        "record_type",
        "class_id",
        "assignment_id",
        "student_id",
        "submission_manifest_path",
        "review_state",
        "notes",
        "tags",
        "scores",
        "comments",
        "created_at",
        "updated_at",
        "module_details",
    }
)
REQUIRED_NOTE_FIELDS: Final[frozenset[str]] = frozenset(
    {"note_id", "text", "created_at", "updated_at", "module_details"}
)
REQUIRED_TAG_FIELDS: Final[frozenset[str]] = frozenset(
    {"tag_id", "label", "polarity", "created_at", "module_details"}
)
OPTIONAL_TAG_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "standard_code",
        "comment_id",
        "severity",
        "teacher_note",
        "page_number",
        "evidence_id",
        "location",
    }
)
REQUIRED_SCORE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "score_id",
        "criterion_id",
        "label",
        "score",
        "max_score",
        "updated_at",
        "module_details",
    }
)
OPTIONAL_SCORE_FIELDS: Final[frozenset[str]] = frozenset(
    {"scale", "teacher_note"}
)
REQUIRED_COMMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "comment_record_id",
        "label",
        "text",
        "source",
        "include_in_feedback",
        "created_at",
        "module_details",
    }
)
OPTIONAL_COMMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {"bank_id", "comment_id", "standard_code"}
)

ALLOWED_REVIEW_STATES: Final[frozenset[str]] = frozenset(
    {"not_started", "in_progress", "ready_for_export", "exported"}
)
ALLOWED_TAG_POLARITIES: Final[frozenset[str]] = frozenset(
    {"positive", "developing", "negative", "neutral"}
)
ALLOWED_COMMENT_SOURCES: Final[frozenset[str]] = frozenset(
    {"standards_profile", "comment_bank", "custom"}
)
ALLOWED_LOCATION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "whole_submission",
        "page",
        "paragraph",
        "sentence",
        "line",
        "section",
        "scene",
        "stanza",
        "custom",
    }
)
INTEGER_LOCATION_TYPES: Final[frozenset[str]] = frozenset(
    {"page", "paragraph", "sentence", "line"}
)
FLEXIBLE_LOCATION_TYPES: Final[frozenset[str]] = frozenset(
    {"section", "scene", "stanza", "custom"}
)


class ReviewRecordError(ValueError):
    """Raised when a Quillan submission review record is missing or invalid."""


def load_review_record(path: str | Path) -> dict[str, Any]:
    """Load and validate a version 1 submission review record."""
    review_path = Path(path)
    try:
        with review_path.open("r", encoding="utf-8") as file:
            record = json.load(file)
    except FileNotFoundError as error:
        raise ReviewRecordError(f"Review record not found: {review_path}") from error
    except json.JSONDecodeError as error:
        raise ReviewRecordError(
            f"Review record is not valid JSON: {review_path}"
        ) from error
    except OSError as error:
        raise ReviewRecordError(
            f"Could not read review record {review_path}: {error}"
        ) from error

    if not isinstance(record, dict):
        raise ReviewRecordError(
            f"Review record must be a JSON object: {review_path}"
        )
    record_dict = cast(dict[str, Any], record)
    validate_review_record(record_dict)
    return record_dict


def validate_review_record(record: dict[str, Any]) -> None:
    """Validate the intrinsic version 1 submission review record contract."""
    if not isinstance(record, dict):
        raise ReviewRecordError("Review record must be an object.")
    _validate_fields(record, REQUIRED_REVIEW_FIELDS, frozenset(), "review record")
    _validate_exact_value(record["schema_version"], "schema_version", "1")
    _validate_exact_value(record["module"], "module", "quillan")
    _validate_exact_value(
        record["record_type"], "record_type", "submission_review"
    )
    for field in ("class_id", "assignment_id", "student_id"):
        _validate_identifier(record[field], field)

    _validate_submission_manifest_path(record)
    _validate_allowed_value(
        record["review_state"], "review_state", ALLOWED_REVIEW_STATES
    )
    created_at = _validate_timestamp(record["created_at"], "created_at")
    updated_at = _validate_timestamp(record["updated_at"], "updated_at")
    if updated_at < created_at:
        raise ReviewRecordError(
            "Field 'updated_at' must not precede field 'created_at'."
        )
    _validate_json_object(record["module_details"], "module_details")

    _validate_notes(record["notes"])
    _validate_tags(record["tags"])
    _validate_scores(record["scores"])
    _validate_comments(record["comments"])


def _validate_submission_manifest_path(record: dict[str, Any]) -> None:
    value = record["submission_manifest_path"]
    _validate_workspace_relative_path(value, "submission_manifest_path")
    expected = (
        f"classes/{record['class_id']}/assignments/{record['assignment_id']}"
        f"/submissions/{record['student_id']}/submission.json"
    )
    if value != expected:
        raise ReviewRecordError(
            "Field 'submission_manifest_path' must be the canonical path "
            f"'{expected}'."
        )


def _validate_notes(value: Any) -> None:
    notes = _validate_array(value, "notes")
    seen_ids: set[str] = set()
    for index, note in enumerate(notes):
        context = f"notes[{index}]"
        item = _validate_record(note, context)
        _validate_fields(item, REQUIRED_NOTE_FIELDS, frozenset(), context)
        _validate_unique_local_id(item["note_id"], f"{context}.note_id", seen_ids)
        _validate_non_empty_string(item["text"], f"{context}.text")
        created_at = _validate_timestamp(
            item["created_at"], f"{context}.created_at"
        )
        updated_at = _validate_timestamp(
            item["updated_at"], f"{context}.updated_at"
        )
        if updated_at < created_at:
            raise ReviewRecordError(
                f"Field '{context}.updated_at' must not precede "
                f"field '{context}.created_at'."
            )
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_tags(value: Any) -> None:
    tags = _validate_array(value, "tags")
    seen_ids: set[str] = set()
    for index, tag in enumerate(tags):
        context = f"tags[{index}]"
        item = _validate_record(tag, context)
        _validate_fields(item, REQUIRED_TAG_FIELDS, OPTIONAL_TAG_FIELDS, context)
        _validate_unique_local_id(item["tag_id"], f"{context}.tag_id", seen_ids)
        _validate_non_empty_string(item["label"], f"{context}.label")
        _validate_allowed_value(
            item["polarity"], f"{context}.polarity", ALLOWED_TAG_POLARITIES
        )
        for field in (
            "standard_code",
            "comment_id",
            "teacher_note",
            "evidence_id",
        ):
            if field in item:
                _validate_non_empty_string(item[field], f"{context}.{field}")
        if "severity" in item:
            _validate_non_negative_integer(
                item["severity"], f"{context}.severity"
            )
        if "page_number" in item:
            _validate_positive_integer(
                item["page_number"], f"{context}.page_number"
            )
        if "location" in item:
            _validate_location(
                item["location"], f"{context}.location", item.get("page_number")
            )
        _validate_timestamp(item["created_at"], f"{context}.created_at")
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_location(
    value: Any, context: str, page_number: Any
) -> None:
    location = _validate_record(value, context)
    _validate_fields(
        location, frozenset({"type", "value"}), frozenset(), context
    )
    location_type = _validate_allowed_value(
        location["type"], f"{context}.type", ALLOWED_LOCATION_TYPES
    )
    location_value = location["value"]
    if location_type == "whole_submission":
        if location_value is not None:
            raise ReviewRecordError(
                f"Field '{context}.value' must be null for whole_submission."
            )
    elif location_type in INTEGER_LOCATION_TYPES:
        location_value = _validate_positive_integer(
            location_value, f"{context}.value"
        )
    elif location_type in FLEXIBLE_LOCATION_TYPES:
        if isinstance(location_value, bool) or not (
            (
                isinstance(location_value, int)
                and location_value >= 1
            )
            or (
                isinstance(location_value, str)
                and bool(location_value.strip())
            )
        ):
            raise ReviewRecordError(
                f"Field '{context}.value' must be a positive integer or "
                "non-empty string."
            )
    if (
        location_type == "page"
        and page_number is not None
        and location_value != page_number
    ):
        raise ReviewRecordError(
            f"Field '{context}.value' must agree with the tag's page_number."
        )


def _validate_scores(value: Any) -> None:
    scores = _validate_array(value, "scores")
    seen_score_ids: set[str] = set()
    seen_criterion_ids: set[str] = set()
    for index, score_record in enumerate(scores):
        context = f"scores[{index}]"
        item = _validate_record(score_record, context)
        _validate_fields(
            item, REQUIRED_SCORE_FIELDS, OPTIONAL_SCORE_FIELDS, context
        )
        _validate_unique_local_id(
            item["score_id"], f"{context}.score_id", seen_score_ids
        )
        _validate_unique_local_id(
            item["criterion_id"],
            f"{context}.criterion_id",
            seen_criterion_ids,
        )
        _validate_non_empty_string(item["label"], f"{context}.label")
        score = _validate_finite_number(item["score"], f"{context}.score")
        max_score = _validate_finite_number(
            item["max_score"], f"{context}.max_score"
        )
        if score < 0:
            raise ReviewRecordError(
                f"Field '{context}.score' must be greater than or equal to zero."
            )
        if max_score <= 0:
            raise ReviewRecordError(
                f"Field '{context}.max_score' must be greater than zero."
            )
        if score > max_score:
            raise ReviewRecordError(
                f"Field '{context}.score' must not exceed max_score."
            )
        for field in ("scale", "teacher_note"):
            if field in item:
                _validate_non_empty_string(item[field], f"{context}.{field}")
        _validate_timestamp(item["updated_at"], f"{context}.updated_at")
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_comments(value: Any) -> None:
    comments = _validate_array(value, "comments")
    seen_ids: set[str] = set()
    for index, comment in enumerate(comments):
        context = f"comments[{index}]"
        item = _validate_record(comment, context)
        _validate_fields(
            item, REQUIRED_COMMENT_FIELDS, OPTIONAL_COMMENT_FIELDS, context
        )
        _validate_unique_local_id(
            item["comment_record_id"],
            f"{context}.comment_record_id",
            seen_ids,
        )
        for field in ("label", "text"):
            _validate_non_empty_string(item[field], f"{context}.{field}")
        for field in ("comment_id", "standard_code"):
            if field in item:
                _validate_non_empty_string(item[field], f"{context}.{field}")
        if "bank_id" in item:
            _validate_identifier(item["bank_id"], f"{context}.bank_id")
        source = _validate_allowed_value(
            item["source"], f"{context}.source", ALLOWED_COMMENT_SOURCES
        )
        _validate_comment_provenance(item, source, context)
        if not isinstance(item["include_in_feedback"], bool):
            raise ReviewRecordError(
                f"Field '{context}.include_in_feedback' must be a boolean."
            )
        _validate_timestamp(item["created_at"], f"{context}.created_at")
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_comment_provenance(
    item: dict[str, Any], source: str, context: str
) -> None:
    if source == "comment_bank":
        for field in ("bank_id", "comment_id"):
            if field not in item:
                raise ReviewRecordError(
                    f"Field '{context}.{field}' is required when "
                    f"'{context}.source' is 'comment_bank'."
                )
        return

    if source == "standards_profile":
        if "bank_id" in item:
            raise ReviewRecordError(
                f"Field '{context}.bank_id' must be absent when "
                f"'{context}.source' is 'standards_profile'."
            )
        for field in ("comment_id", "standard_code"):
            if field not in item:
                raise ReviewRecordError(
                    f"Field '{context}.{field}' is required when "
                    f"'{context}.source' is 'standards_profile'."
                )
        return

    for field in ("bank_id", "comment_id", "standard_code"):
        if field in item:
            raise ReviewRecordError(
                f"Field '{context}.{field}' must be absent when "
                f"'{context}.source' is 'custom'."
            )


def _validate_workspace_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ReviewRecordError(
            f"Field '{field}' must be a non-empty workspace-relative path string."
        )
    if "\0" in value:
        raise ReviewRecordError(f"Field '{field}' must not contain null bytes.")
    path_variants = (PurePosixPath(value), PureWindowsPath(value))
    if any(path.anchor or path.drive for path in path_variants):
        raise ReviewRecordError(
            f"Field '{field}' must be a workspace-relative path."
        )
    components = re.split(r"[\\/]", value)
    if "." in components or ".." in components:
        raise ReviewRecordError(
            f"Field '{field}' must not contain '.' or '..' path components."
        )


def _validate_fields(
    data: dict[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
    context: str,
) -> None:
    missing = required - data.keys()
    if missing:
        field = sorted(missing)[0]
        raise ReviewRecordError(
            f"Missing required field '{field}' in {context}."
        )
    unknown = data.keys() - required - optional
    if unknown:
        field = sorted(unknown)[0]
        raise ReviewRecordError(f"Unknown field '{field}' in {context}.")


def _validate_record(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewRecordError(f"{context} must be an object.")
    return cast(dict[str, Any], value)


def _validate_array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewRecordError(f"Field '{field}' must be a list.")
    return value


def _validate_exact_value(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise ReviewRecordError(
            f"Field '{field}' must be the string '{expected}'."
        )


def _validate_identifier(value: Any, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise ReviewRecordError(str(error)) from error


def _validate_unique_local_id(
    value: Any, field: str, seen_ids: set[str]
) -> str:
    local_id = _validate_non_empty_string(value, field)
    if local_id in seen_ids:
        raise ReviewRecordError(f"Duplicate {field.rsplit('.', 1)[-1]} '{local_id}'.")
    seen_ids.add(local_id)
    return local_id


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewRecordError(f"Field '{field}' must be a non-empty string.")
    return value


def _validate_positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReviewRecordError(f"Field '{field}' must be a positive integer.")
    return value


def _validate_non_negative_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReviewRecordError(
            f"Field '{field}' must be a non-negative integer."
        )
    return value


def _validate_finite_number(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ReviewRecordError(f"Field '{field}' must be a finite number.")
    return float(value)


def _validate_allowed_value(
    value: Any, field: str, allowed_values: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise ReviewRecordError(
            f"Invalid {field} {value!r}. Allowed values: {allowed}."
        )
    return value


def _validate_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ReviewRecordError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewRecordError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewRecordError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    return parsed


def _validate_json_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise ReviewRecordError(f"Field '{field}' must be an object.")
