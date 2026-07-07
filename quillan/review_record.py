"""Loading, building, and validation for Quillan submission review records."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

REVIEW_SCHEMA_VERSION: Final = "2"
REVIEW_MODULE: Final = "quillan"
REVIEW_RECORD_TYPE: Final = "submission_review"

REQUIRED_REVIEW_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "module",
        "record_type",
        "class_id",
        "assignment_id",
        "student_id",
        "submission_manifest_path",
        "assignment_path",
        "review_state",
        "minimum_requirement_checks",
        "minimum_requirement_outcome",
        "review_units",
        "overall_standard_ratings",
        "feedback",
        "exports",
        "private_notes",
        "created_at",
        "updated_at",
        "module_details",
    }
)
LEGACY_V1_FIELDS: Final[frozenset[str]] = frozenset(
    {"notes", "tags", "scores", "comments", "requirement_checks"}
)
REQUIRED_REQUIREMENT_CHECK_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "requirement_check_id",
        "requirement_key",
        "label",
        "expected",
        "met",
        "updated_at",
        "module_details",
    }
)
OPTIONAL_REQUIREMENT_CHECK_FIELDS: Final[frozenset[str]] = frozenset(
    {"teacher_note"}
)
REQUIRED_MINIMUM_REQUIREMENT_OUTCOME_FIELDS: Final[frozenset[str]] = frozenset(
    {"status", "returned_without_full_review", "teacher_note", "updated_at"}
)
REQUIRED_REVIEW_UNIT_FIELDS: Final[frozenset[str]] = frozenset(
    {"unit_id", "sequence", "label", "unit_type", "standard_observations", "module_details"}
)
OPTIONAL_REVIEW_UNIT_FIELDS: Final[frozenset[str]] = frozenset(
    {"page_number", "evidence_id"}
)
REQUIRED_STANDARD_OBSERVATION_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "observation_id",
        "standard_id",
        "applicable",
        "evidence_present",
        "rating",
        "rationale",
        "include_in_feedback",
        "updated_at",
        "module_details",
    }
)
REQUIRED_OVERALL_STANDARD_RATING_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "standard_id",
        "rating",
        "rationale",
        "include_in_feedback",
        "updated_at",
        "module_details",
    }
)
REQUIRED_FEEDBACK_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "include_review_unit_observations",
        "include_overall_standard_ratings",
        "standard_feedback",
    }
)
REQUIRED_STANDARD_FEEDBACK_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "standard_id",
        "include_overall_rating",
        "include_overall_rationale",
        "included_observation_ids",
        "comments",
        "module_details",
    }
)
REQUIRED_FEEDBACK_COMMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "feedback_comment_id",
        "source",
        "text",
        "reusable_comment_id",
        "save_for_reuse",
        "include_in_feedback",
        "created_at",
        "module_details",
    }
)
REQUIRED_EXPORTS_FIELDS: Final[frozenset[str]] = frozenset(
    {"feedback_pdf", "feedback_markdown"}
)
REQUIRED_EXPORT_METADATA_FIELDS: Final[frozenset[str]] = frozenset(
    {"path", "generated_at", "source_review_updated_at", "module_details"}
)
REQUIRED_PRIVATE_NOTE_FIELDS: Final[frozenset[str]] = frozenset(
    {"private_note_id", "text", "created_at", "updated_at", "module_details"}
)

ALLOWED_REVIEW_STATES: Final[frozenset[str]] = frozenset(
    {
        "not_started",
        "requirements_checked",
        "returned_without_full_review",
        "observations_in_progress",
        "observations_complete",
        "ratings_complete",
        "feedback_composed",
        "ready_for_export",
        "exported",
    }
)
ALLOWED_MINIMUM_REQUIREMENT_OUTCOME_STATUSES: Final[frozenset[str]] = frozenset(
    {"not_checked", "met", "unmet_continue_review", "returned_without_full_review"}
)
ALLOWED_FEEDBACK_COMMENT_SOURCES: Final[frozenset[str]] = frozenset(
    {"custom", "reusable_focus_standard_comment"}
)

# Retained for legacy modules that now fail closed before writing v1 tags.
ALLOWED_TAG_POLARITIES: Final[frozenset[str]] = frozenset(
    {"positive", "developing", "negative", "neutral"}
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
    """Load and validate a schema version 2 submission review record."""
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


def build_empty_review_record(
    *,
    class_id: str,
    assignment_id: str,
    student_id: str,
    submission_manifest_path: str | None = None,
    assignment_path: str | None = None,
    created_at: str,
) -> dict[str, Any]:
    """Build a minimal valid schema version 2 submission review record."""
    record: dict[str, Any] = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "module": REVIEW_MODULE,
        "record_type": REVIEW_RECORD_TYPE,
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "submission_manifest_path": submission_manifest_path
        or _canonical_submission_manifest_path(class_id, assignment_id, student_id),
        "assignment_path": assignment_path
        or _canonical_assignment_path(class_id, assignment_id),
        "review_state": "not_started",
        "minimum_requirement_checks": [],
        "minimum_requirement_outcome": {
            "status": "not_checked",
            "returned_without_full_review": False,
            "teacher_note": None,
            "updated_at": None,
        },
        "review_units": [],
        "overall_standard_ratings": [],
        "feedback": {
            "include_review_unit_observations": False,
            "include_overall_standard_ratings": True,
            "standard_feedback": [],
        },
        "exports": {"feedback_pdf": None, "feedback_markdown": None},
        "private_notes": [],
        "created_at": created_at,
        "updated_at": created_at,
        "module_details": {},
    }
    validate_review_record(record)
    return record


def validate_review_record(record: dict[str, Any]) -> None:
    """Validate the intrinsic schema version 2 submission review record contract."""
    if not isinstance(record, dict):
        raise ReviewRecordError("Review record must be an object.")
    _reject_legacy_schema(record)
    _validate_fields(record, REQUIRED_REVIEW_FIELDS, frozenset(), "review record")
    _validate_exact_value(record["schema_version"], "schema_version", REVIEW_SCHEMA_VERSION)
    _validate_exact_value(record["module"], "module", REVIEW_MODULE)
    _validate_exact_value(record["record_type"], "record_type", REVIEW_RECORD_TYPE)
    for field in ("class_id", "assignment_id", "student_id"):
        _validate_identifier(record[field], field)

    _validate_submission_manifest_path(record)
    _validate_assignment_path(record)
    _validate_allowed_value(record["review_state"], "review_state", ALLOWED_REVIEW_STATES)
    created_at = _validate_timestamp(record["created_at"], "created_at")
    updated_at = _validate_timestamp(record["updated_at"], "updated_at")
    if updated_at < created_at:
        raise ReviewRecordError("Field 'updated_at' must not precede field 'created_at'.")
    _validate_json_object(record["module_details"], "module_details")

    observation_ids = _validate_review_units(record["review_units"])
    _validate_minimum_requirement_checks(record["minimum_requirement_checks"])
    _validate_minimum_requirement_outcome(
        record["minimum_requirement_outcome"], record["review_state"]
    )
    _validate_overall_standard_ratings(record["overall_standard_ratings"])
    _validate_feedback(record["feedback"], observation_ids)
    _validate_exports(record["exports"])
    _validate_private_notes(record["private_notes"])


def _reject_legacy_schema(record: dict[str, Any]) -> None:
    if record.get("schema_version") == "1":
        raise ReviewRecordError(
            "Schema version '1' review records are legacy and are not supported "
            "by the schema version 2 standards-based runtime."
        )
    legacy = LEGACY_V1_FIELDS & record.keys()
    if legacy:
        field = sorted(legacy)[0]
        raise ReviewRecordError(
            f"Legacy v1 top-level field '{field}' is not supported by schema version 2."
        )


def _validate_submission_manifest_path(record: dict[str, Any]) -> None:
    value = record["submission_manifest_path"]
    _validate_workspace_relative_path(value, "submission_manifest_path")
    expected = _canonical_submission_manifest_path(
        record["class_id"], record["assignment_id"], record["student_id"]
    )
    if value != expected:
        raise ReviewRecordError(
            "Field 'submission_manifest_path' must be the canonical path "
            f"'{expected}'."
        )


def _validate_assignment_path(record: dict[str, Any]) -> None:
    value = record["assignment_path"]
    _validate_workspace_relative_path(value, "assignment_path")
    expected = _canonical_assignment_path(record["class_id"], record["assignment_id"])
    if value != expected:
        raise ReviewRecordError(
            "Field 'assignment_path' must be the canonical path "
            f"'{expected}'."
        )


def _canonical_submission_manifest_path(
    class_id: str, assignment_id: str, student_id: str
) -> str:
    return (
        f"classes/{class_id}/assignments/{assignment_id}/submissions/"
        f"{student_id}/submission.json"
    )


def _canonical_assignment_path(class_id: str, assignment_id: str) -> str:
    return f"classes/{class_id}/assignments/{assignment_id}/assignment.json"


def _validate_minimum_requirement_checks(value: Any) -> None:
    checks = _validate_array(value, "minimum_requirement_checks")
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for index, check in enumerate(checks):
        context = f"minimum_requirement_checks[{index}]"
        item = _validate_record(check, context)
        _validate_fields(
            item,
            REQUIRED_REQUIREMENT_CHECK_FIELDS,
            OPTIONAL_REQUIREMENT_CHECK_FIELDS,
            context,
        )
        _validate_unique_local_id(
            item["requirement_check_id"], f"{context}.requirement_check_id", seen_ids
        )
        _validate_unique_local_id(
            item["requirement_key"], f"{context}.requirement_key", seen_keys
        )
        _validate_non_empty_string(item["label"], f"{context}.label")
        _validate_requirement_expected(item["expected"], f"{context}.expected")
        _validate_boolean(item["met"], f"{context}.met")
        if "teacher_note" in item and item["teacher_note"] is not None:
            _validate_non_empty_string(item["teacher_note"], f"{context}.teacher_note")
        _validate_timestamp(item["updated_at"], f"{context}.updated_at")
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_minimum_requirement_outcome(value: Any, review_state: str) -> None:
    outcome = _validate_record(value, "minimum_requirement_outcome")
    _validate_fields(
        outcome,
        REQUIRED_MINIMUM_REQUIREMENT_OUTCOME_FIELDS,
        frozenset(),
        "minimum_requirement_outcome",
    )
    status = _validate_allowed_value(
        outcome["status"],
        "minimum_requirement_outcome.status",
        ALLOWED_MINIMUM_REQUIREMENT_OUTCOME_STATUSES,
    )
    returned = _validate_boolean(
        outcome["returned_without_full_review"],
        "minimum_requirement_outcome.returned_without_full_review",
    )
    if outcome["teacher_note"] is not None:
        _validate_non_empty_string(
            outcome["teacher_note"], "minimum_requirement_outcome.teacher_note"
        )
    if status == "not_checked":
        if outcome["updated_at"] is not None:
            raise ReviewRecordError(
                "Field 'minimum_requirement_outcome.updated_at' must be null "
                "when status is 'not_checked'."
            )
    elif outcome["updated_at"] is None:
        raise ReviewRecordError(
            "Field 'minimum_requirement_outcome.updated_at' must be a "
            "timezone-aware ISO 8601 string unless status is 'not_checked'."
        )
    else:
        _validate_timestamp(
            outcome["updated_at"], "minimum_requirement_outcome.updated_at"
        )
    if status == "returned_without_full_review" and not returned:
        raise ReviewRecordError(
            "Field 'minimum_requirement_outcome.returned_without_full_review' "
            "must be true when status is 'returned_without_full_review'."
        )
    if returned and review_state != "returned_without_full_review":
        raise ReviewRecordError(
            "Field 'review_state' must be 'returned_without_full_review' when "
            "minimum_requirement_outcome.returned_without_full_review is true."
        )


def _validate_review_units(value: Any) -> set[str]:
    units = _validate_array(value, "review_units")
    seen_unit_ids: set[str] = set()
    seen_sequences: set[int] = set()
    seen_observation_ids: set[str] = set()
    for index, unit in enumerate(units):
        context = f"review_units[{index}]"
        item = _validate_record(unit, context)
        _validate_fields(item, REQUIRED_REVIEW_UNIT_FIELDS, OPTIONAL_REVIEW_UNIT_FIELDS, context)
        _validate_unique_local_id(item["unit_id"], f"{context}.unit_id", seen_unit_ids)
        sequence = _validate_positive_integer(item["sequence"], f"{context}.sequence")
        if sequence in seen_sequences:
            raise ReviewRecordError(f"Duplicate sequence '{sequence}' in review_units.")
        seen_sequences.add(sequence)
        _validate_non_empty_string(item["label"], f"{context}.label")
        _validate_non_empty_string(item["unit_type"], f"{context}.unit_type")
        if "page_number" in item:
            _validate_positive_integer(item["page_number"], f"{context}.page_number")
        if "evidence_id" in item:
            _validate_non_empty_string(item["evidence_id"], f"{context}.evidence_id")
        _validate_standard_observations(
            item["standard_observations"], f"{context}.standard_observations", seen_observation_ids
        )
        _validate_json_object(item["module_details"], f"{context}.module_details")
    return seen_observation_ids


def _validate_standard_observations(
    value: Any, context: str, seen_observation_ids: set[str]
) -> None:
    observations = _validate_array(value, context)
    seen_standard_ids: set[str] = set()
    for index, observation in enumerate(observations):
        item_context = f"{context}[{index}]"
        item = _validate_record(observation, item_context)
        _validate_fields(
            item, REQUIRED_STANDARD_OBSERVATION_FIELDS, frozenset(), item_context
        )
        _validate_unique_local_id(
            item["observation_id"], f"{item_context}.observation_id", seen_observation_ids
        )
        _validate_unique_local_id(
            item["standard_id"], f"{item_context}.standard_id", seen_standard_ids
        )
        applicable = _validate_boolean(item["applicable"], f"{item_context}.applicable")
        if applicable:
            _validate_boolean(item["evidence_present"], f"{item_context}.evidence_present")
            if item["rating"] is not None:
                _validate_integer(item["rating"], f"{item_context}.rating")
        else:
            if item["evidence_present"] is not None:
                raise ReviewRecordError(
                    f"Field '{item_context}.evidence_present' must be null when applicable is false."
                )
            if item["rating"] is not None:
                raise ReviewRecordError(
                    f"Field '{item_context}.rating' must be null when applicable is false."
                )
        if item["rationale"] is not None:
            _validate_non_empty_string(item["rationale"], f"{item_context}.rationale")
        _validate_boolean(item["include_in_feedback"], f"{item_context}.include_in_feedback")
        _validate_timestamp(item["updated_at"], f"{item_context}.updated_at")
        _validate_json_object(item["module_details"], f"{item_context}.module_details")


def _validate_overall_standard_ratings(value: Any) -> None:
    ratings = _validate_array(value, "overall_standard_ratings")
    seen_standard_ids: set[str] = set()
    for index, rating in enumerate(ratings):
        context = f"overall_standard_ratings[{index}]"
        item = _validate_record(rating, context)
        _validate_fields(
            item, REQUIRED_OVERALL_STANDARD_RATING_FIELDS, frozenset(), context
        )
        _validate_unique_local_id(item["standard_id"], f"{context}.standard_id", seen_standard_ids)
        _validate_integer(item["rating"], f"{context}.rating")
        if item["rationale"] is not None:
            _validate_non_empty_string(item["rationale"], f"{context}.rationale")
        _validate_boolean(item["include_in_feedback"], f"{context}.include_in_feedback")
        _validate_timestamp(item["updated_at"], f"{context}.updated_at")
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_feedback(value: Any, observation_ids: set[str]) -> None:
    feedback = _validate_record(value, "feedback")
    _validate_fields(feedback, REQUIRED_FEEDBACK_FIELDS, frozenset(), "feedback")
    _validate_boolean(
        feedback["include_review_unit_observations"],
        "feedback.include_review_unit_observations",
    )
    _validate_boolean(
        feedback["include_overall_standard_ratings"],
        "feedback.include_overall_standard_ratings",
    )
    standard_feedback = _validate_array(
        feedback["standard_feedback"], "feedback.standard_feedback"
    )
    seen_standard_ids: set[str] = set()
    seen_comment_ids: set[str] = set()
    for index, item_value in enumerate(standard_feedback):
        context = f"feedback.standard_feedback[{index}]"
        item = _validate_record(item_value, context)
        _validate_fields(item, REQUIRED_STANDARD_FEEDBACK_FIELDS, frozenset(), context)
        _validate_unique_local_id(item["standard_id"], f"{context}.standard_id", seen_standard_ids)
        _validate_boolean(item["include_overall_rating"], f"{context}.include_overall_rating")
        _validate_boolean(item["include_overall_rationale"], f"{context}.include_overall_rationale")
        included = _validate_array(item["included_observation_ids"], f"{context}.included_observation_ids")
        for observation_id in included:
            value_id = _validate_non_empty_string(observation_id, f"{context}.included_observation_ids")
            if value_id not in observation_ids:
                raise ReviewRecordError(
                    f"Field '{context}.included_observation_ids' references unknown observation_id '{value_id}'."
                )
        comments = _validate_array(item["comments"], f"{context}.comments")
        for comment_index, comment_value in enumerate(comments):
            _validate_feedback_comment(
                comment_value, f"{context}.comments[{comment_index}]", seen_comment_ids
            )
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_feedback_comment(
    value: Any, context: str, seen_comment_ids: set[str]
) -> None:
    item = _validate_record(value, context)
    _validate_fields(item, REQUIRED_FEEDBACK_COMMENT_FIELDS, frozenset(), context)
    _validate_unique_local_id(
        item["feedback_comment_id"], f"{context}.feedback_comment_id", seen_comment_ids
    )
    source = _validate_allowed_value(
        item["source"], f"{context}.source", ALLOWED_FEEDBACK_COMMENT_SOURCES
    )
    _validate_non_empty_string(item["text"], f"{context}.text")
    if source == "custom":
        if item["reusable_comment_id"] is not None:
            raise ReviewRecordError(
                f"Field '{context}.reusable_comment_id' must be null for custom comments."
            )
    else:
        _validate_non_empty_string(
            item["reusable_comment_id"], f"{context}.reusable_comment_id"
        )
    _validate_boolean(item["save_for_reuse"], f"{context}.save_for_reuse")
    _validate_boolean(item["include_in_feedback"], f"{context}.include_in_feedback")
    _validate_timestamp(item["created_at"], f"{context}.created_at")
    _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_exports(value: Any) -> None:
    exports = _validate_record(value, "exports")
    _validate_fields(exports, REQUIRED_EXPORTS_FIELDS, frozenset(), "exports")
    for field in ("feedback_pdf", "feedback_markdown"):
        metadata = exports[field]
        if metadata is None:
            continue
        context = f"exports.{field}"
        item = _validate_record(metadata, context)
        _validate_fields(item, REQUIRED_EXPORT_METADATA_FIELDS, frozenset(), context)
        _validate_workspace_relative_path(item["path"], f"{context}.path")
        _validate_timestamp(item["generated_at"], f"{context}.generated_at")
        _validate_timestamp(
            item["source_review_updated_at"], f"{context}.source_review_updated_at"
        )
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_private_notes(value: Any) -> None:
    notes = _validate_array(value, "private_notes")
    seen_ids: set[str] = set()
    for index, note in enumerate(notes):
        context = f"private_notes[{index}]"
        item = _validate_record(note, context)
        _validate_fields(item, REQUIRED_PRIVATE_NOTE_FIELDS, frozenset(), context)
        _validate_unique_local_id(
            item["private_note_id"], f"{context}.private_note_id", seen_ids
        )
        _validate_non_empty_string(item["text"], f"{context}.text")
        created_at = _validate_timestamp(item["created_at"], f"{context}.created_at")
        updated_at = _validate_timestamp(item["updated_at"], f"{context}.updated_at")
        if updated_at < created_at:
            raise ReviewRecordError(
                f"Field '{context}.updated_at' must not precede field '{context}.created_at'."
            )
        _validate_json_object(item["module_details"], f"{context}.module_details")


def _validate_workspace_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ReviewRecordError(
            f"Field '{field}' must be a non-empty workspace-relative path string."
        )
    if "\0" in value:
        raise ReviewRecordError(f"Field '{field}' must not contain null bytes.")
    path_variants = (PurePosixPath(value), PureWindowsPath(value))
    if any(path.anchor or path.drive for path in path_variants):
        raise ReviewRecordError(f"Field '{field}' must be a workspace-relative path.")
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
        raise ReviewRecordError(f"Missing required field '{field}' in {context}.")
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
        raise ReviewRecordError(f"Field '{field}' must be the string '{expected}'.")


def _validate_identifier(value: Any, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise ReviewRecordError(str(error)) from error


def _validate_unique_local_id(value: Any, field: str, seen_ids: set[str]) -> str:
    local_id = _validate_non_empty_string(value, field)
    if local_id in seen_ids:
        raise ReviewRecordError(f"Duplicate {field.rsplit('.', 1)[-1]} '{local_id}'.")
    seen_ids.add(local_id)
    return local_id


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewRecordError(f"Field '{field}' must be a non-empty string.")
    return value


def _validate_boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ReviewRecordError(f"Field '{field}' must be a boolean.")
    return value


def _validate_positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReviewRecordError(f"Field '{field}' must be a positive integer.")
    return value


def _validate_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReviewRecordError(f"Field '{field}' must be an integer.")
    return value


def _validate_requirement_expected(value: Any, field: str) -> None:
    if isinstance(value, str) and value.strip():
        return
    if (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    ):
        return
    raise ReviewRecordError(
        f"Field '{field}' must be a non-empty string or finite number."
    )


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
