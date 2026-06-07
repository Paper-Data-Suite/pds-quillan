"""Standards profile loading and validation for Quillan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ALLOWED_POLARITIES = {"positive", "developing", "negative"}


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
    required_top_level_fields = ["profile_id", "subject", "course", "standards"]

    for field in required_top_level_fields:
        _require_field(profile, field, "standards profile")

    if not isinstance(profile["standards"], list):
        raise StandardsProfileError("Field 'standards' must be a list.")

    if not profile["standards"]:
        raise StandardsProfileError("Field 'standards' must not be empty.")

    for standard in profile["standards"]:
        _validate_standard(standard)


def _validate_standard(standard: Any) -> None:
    """Validate one standard record."""
    if not isinstance(standard, dict):
        raise StandardsProfileError("Each standard must be an object.")

    required_standard_fields = ["code", "short_name", "description", "comments"]

    for field in required_standard_fields:
        _require_field(standard, field, "standard")

    if not isinstance(standard["comments"], list):
        raise StandardsProfileError(
            f"Comments for standard '{standard['code']}' must be a list."
        )

    if not standard["comments"]:
        raise StandardsProfileError(
            f"Comments for standard '{standard['code']}' must not be empty."
        )

    for comment in standard["comments"]:
        _validate_comment(comment, standard["code"])


def _validate_comment(comment: Any, standard_code: str) -> None:
    """Validate one comment record."""
    if not isinstance(comment, dict):
        raise StandardsProfileError(
            f"Each comment for standard '{standard_code}' must be an object."
        )

    required_comment_fields = ["comment_id", "label", "polarity"]

    for field in required_comment_fields:
        _require_field(comment, field, f"comment for standard '{standard_code}'")

    if comment["polarity"] not in ALLOWED_POLARITIES:
        allowed = ", ".join(sorted(ALLOWED_POLARITIES))
        raise StandardsProfileError(
            f"Invalid polarity '{comment['polarity']}' for comment "
            f"'{comment['comment_id']}'. Allowed values: {allowed}."
        )


def _require_field(data: dict[str, Any], field: str, context: str) -> None:
    """Require a field to exist and contain a non-empty value."""
    if field not in data:
        raise StandardsProfileError(f"Missing required field '{field}' in {context}.")

    if data[field] in ("", None):
        raise StandardsProfileError(f"Field '{field}' in {context} must not be empty.")