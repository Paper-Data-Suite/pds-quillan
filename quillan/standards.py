"""Legacy Quillan standards-profile loading and validation.

Shared standards definitions and reusable standards profiles are owned by
``pds-core``. This module remains for transitional Quillan-specific profile
data such as comment-bank scaffolding, hotwords, feedback templates, and
severity defaults that are not part of the shared ``StandardDefinition``
contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

ALLOWED_POLARITIES = {"positive", "developing", "negative"}
REQUIRED_PROFILE_FIELDS = ("profile_id", "subject", "course", "standards")
REQUIRED_STANDARD_FIELDS = ("code", "short_name", "description", "comments")
REQUIRED_COMMENT_FIELDS = ("comment_id", "label", "polarity")


class StandardsProfileError(ValueError):
    """Raised when a standards profile is missing or invalid."""


def load_standards_profile(path: str | Path) -> dict[str, Any]:
    """Load and validate a standards profile from a JSON file."""
    profile_path = Path(path)

    try:
        with profile_path.open("r", encoding="utf-8") as file:
            profile = json.load(file)
    except FileNotFoundError as error:
        raise StandardsProfileError(
            f"Standards profile not found: {profile_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise StandardsProfileError(
            f"Standards profile is not valid JSON: {profile_path}"
        ) from error

    if not isinstance(profile, dict):
        raise StandardsProfileError(
            f"Standards profile must be a JSON object: {profile_path}"
        )

    profile_dict = cast(dict[str, Any], profile)
    validate_standards_profile(profile_dict)
    return profile_dict


def validate_standards_profile(profile: dict[str, Any]) -> None:
    """Validate the structure of a standards profile."""
    for field in REQUIRED_PROFILE_FIELDS:
        _require_field(profile, field, "standards profile")

    _validate_identifier(profile["profile_id"], "profile_id")
    _validate_non_empty_string(profile["subject"], "subject")
    _validate_non_empty_string(profile["course"], "course")

    if not isinstance(profile["standards"], list):
        raise StandardsProfileError("Field 'standards' must be a list.")

    if not profile["standards"]:
        raise StandardsProfileError("Field 'standards' must not be empty.")

    standard_codes: set[str] = set()
    for standard in profile["standards"]:
        _validate_standard(standard)
        standard_code = standard["code"]
        if standard_code in standard_codes:
            raise StandardsProfileError(
                f"Duplicate standard code '{standard_code}' in standards profile."
            )
        standard_codes.add(standard_code)


def _validate_standard(standard: Any) -> None:
    """Validate one standard record."""
    if not isinstance(standard, dict):
        raise StandardsProfileError("Each standard must be an object.")

    for field in REQUIRED_STANDARD_FIELDS:
        _require_field(standard, field, "standard")

    for field in ("code", "short_name", "description"):
        _validate_non_empty_string(standard[field], field)

    if not isinstance(standard["comments"], list):
        raise StandardsProfileError(
            f"Comments for standard '{standard['code']}' must be a list."
        )

    comment_ids: set[str] = set()
    for comment in standard["comments"]:
        _validate_comment(comment, standard["code"])
        comment_id = comment["comment_id"]
        if comment_id in comment_ids:
            raise StandardsProfileError(
                f"Duplicate comment_id '{comment_id}' for standard "
                f"'{standard['code']}'."
            )
        comment_ids.add(comment_id)


def _validate_comment(comment: Any, standard_code: str) -> None:
    """Validate one comment record."""
    if not isinstance(comment, dict):
        raise StandardsProfileError(
            f"Each comment for standard '{standard_code}' must be an object."
        )

    for field in REQUIRED_COMMENT_FIELDS:
        _require_field(comment, field, f"comment for standard '{standard_code}'")

    _validate_identifier(comment["comment_id"], "comment_id")
    _validate_non_empty_string(comment["label"], "label")

    if not isinstance(comment["polarity"], str):
        raise StandardsProfileError("Field 'polarity' must be a string.")

    if comment["polarity"] not in ALLOWED_POLARITIES:
        allowed = ", ".join(sorted(ALLOWED_POLARITIES))
        raise StandardsProfileError(
            f"Invalid polarity '{comment['polarity']}' for comment "
            f"'{comment['comment_id']}'. Allowed values: {allowed}."
        )

    if "severity_default" in comment:
        severity = comment["severity_default"]
        if isinstance(severity, bool) or not isinstance(severity, int) or severity < 0:
            raise StandardsProfileError(
                "Field 'severity_default' must be a non-negative integer."
            )

    if "feedback_template" in comment:
        _validate_non_empty_string(comment["feedback_template"], "feedback_template")

    for field in ("subskills", "hotwords"):
        if field in comment:
            _validate_string_list(comment[field], field)


def _validate_identifier(value: Any, field: str) -> None:
    """Validate a shared Paper Data Suite identifier."""
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise StandardsProfileError(str(error)) from error


def _validate_non_empty_string(value: Any, field: str) -> None:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise StandardsProfileError(f"Field '{field}' must be a non-empty string.")


def _validate_string_list(value: Any, field: str) -> None:
    """Validate an optional list of non-empty teacher-defined strings."""
    if not isinstance(value, list):
        raise StandardsProfileError(f"Field '{field}' must be a list.")

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise StandardsProfileError(
                f"Each value in '{field}' must be a non-empty string."
            )


def _require_field(data: dict[str, Any], field: str, context: str) -> None:
    """Require a field to exist."""
    if field not in data:
        raise StandardsProfileError(f"Missing required field '{field}' in {context}.")
