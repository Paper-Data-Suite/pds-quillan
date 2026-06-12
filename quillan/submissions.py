"""Submission metadata loading and validation for Quillan."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

ALLOWED_SOURCE_TYPES = {
    "manual_entry",
    "typed_text",
    "pasted_text",
    "file_import",
    "paper_scan",
    "ocr_scan",
    "google_doc_export",
}

ALLOWED_SUBMISSION_STATUSES = {
    "captured",
    "needs_review",
    "reviewed",
    "superseded",
    "invalid",
}

REQUIRED_SUBMISSION_FIELDS = [
    "submission_id",
    "assignment_id",
    "class_id",
    "student_id",
    "source_type",
    "text_file",
    "captured_at",
    "status",
    "version",
]


class SubmissionMetadataError(ValueError):
    """Raised when submission metadata is missing or invalid."""


def load_submission_metadata(path: str | Path) -> dict[str, Any]:
    """Load and validate submission metadata from a JSON file."""
    metadata_path = Path(path)

    try:
        with metadata_path.open("r", encoding="utf-8") as file:
            submission = json.load(file)
    except FileNotFoundError as error:
        raise SubmissionMetadataError(
            f"Submission metadata not found: {metadata_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise SubmissionMetadataError(
            f"Submission metadata is not valid JSON: {metadata_path}"
        ) from error

    if not isinstance(submission, dict):
        raise SubmissionMetadataError(
            f"Submission metadata must be a JSON object: {metadata_path}"
        )

    submission_dict = cast(dict[str, Any], submission)
    validate_submission_metadata(submission_dict)
    return submission_dict


def validate_submission_metadata(submission: dict[str, Any]) -> None:
    """Validate the structure of a submission metadata record."""
    for field in REQUIRED_SUBMISSION_FIELDS:
        if field not in submission:
            raise SubmissionMetadataError(f"Missing required field '{field}'.")

    for field in (
        "submission_id",
        "assignment_id",
        "class_id",
        "student_id",
        "source_type",
        "text_file",
        "captured_at",
        "status",
    ):
        _validate_non_empty_string(submission[field], field)

    for field in ("submission_id", "assignment_id", "class_id", "student_id"):
        _validate_identifier(submission[field], field)

    _validate_allowed_value(
        submission["source_type"], "source_type", ALLOWED_SOURCE_TYPES
    )
    _validate_text_file(submission["text_file"])
    _validate_allowed_value(submission["status"], "status", ALLOWED_SUBMISSION_STATUSES)
    _validate_version(submission["version"])


def _validate_non_empty_string(value: Any, field: str) -> None:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise SubmissionMetadataError(f"Field '{field}' must be a non-empty string.")


def _validate_identifier(value: Any, field: str) -> None:
    """Validate a shared Paper Data Suite identifier."""
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise SubmissionMetadataError(str(error)) from error


def _validate_allowed_value(value: str, field: str, allowed_values: set[str]) -> None:
    """Validate a string against an explicit set of allowed values."""
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise SubmissionMetadataError(
            f"Invalid {field} '{value}'. Allowed values: {allowed}."
        )


def _validate_text_file(text_file: str) -> None:
    """Validate that the text artifact path is relative and contained."""
    path_variants = (PurePosixPath(text_file), PureWindowsPath(text_file))

    if any(path.anchor for path in path_variants):
        raise SubmissionMetadataError("Field 'text_file' must be a relative path.")

    if any(".." in path.parts for path in path_variants):
        raise SubmissionMetadataError(
            "Field 'text_file' must not contain parent-directory traversal."
        )


def _validate_version(version: Any) -> None:
    """Validate the positive integer submission version."""
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise SubmissionMetadataError("Field 'version' must be a positive integer.")
