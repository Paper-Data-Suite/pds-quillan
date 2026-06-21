"""Loading and validation for Quillan reviewable-evidence manifests."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

REQUIRED_MANIFEST_FIELDS: Final[tuple[str, ...]] = (
    "schema_version",
    "module",
    "record_type",
    "class_id",
    "assignment_id",
    "student_id",
    "expected_pages",
    "submission_state",
    "pages",
    "created_at",
    "updated_at",
    "module_details",
)
REQUIRED_PAGE_FIELDS: Final[tuple[str, ...]] = (
    "page_number",
    "page_state",
    "selected_evidence_id",
    "evidence",
)
REQUIRED_EVIDENCE_FIELDS: Final[tuple[str, ...]] = (
    "evidence_id",
    "routed_evidence_path",
    "evidence_role",
    "evidence_state",
    "duplicate_number",
    "created_at",
    "retained_source",
    "module_details",
)
REQUIRED_RETAINED_SOURCE_FIELDS: Final[tuple[str, ...]] = (
    "source_scan_id",
    "source_filename",
    "source_sha256",
    "retained_source_path",
    "source_page_number",
)

ALLOWED_SUBMISSION_STATES: Final[frozenset[str]] = frozenset(
    {"unreviewed", "in_progress", "needs_rescan", "reviewed"}
)
ALLOWED_PAGE_STATES: Final[frozenset[str]] = frozenset(
    {"present", "missing", "duplicate", "needs_rescan", "excluded"}
)
ALLOWED_EVIDENCE_ROLES: Final[frozenset[str]] = frozenset(
    {"candidate", "selected", "replacement", "excluded"}
)
ALLOWED_EVIDENCE_STATES: Final[frozenset[str]] = frozenset(
    {"active", "needs_rescan", "damaged", "excluded"}
)
_SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9A-Fa-f]{64}$")


class SubmissionManifestError(ValueError):
    """Raised when a v0.6 submission manifest is missing or invalid."""


def load_submission_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate a v0.6 submission manifest JSON file."""
    manifest_path = Path(path)

    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
    except FileNotFoundError as error:
        raise SubmissionManifestError(
            f"Submission manifest not found: {manifest_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise SubmissionManifestError(
            f"Submission manifest is not valid JSON: {manifest_path}"
        ) from error

    if not isinstance(manifest, dict):
        raise SubmissionManifestError(
            f"Submission manifest must be a JSON object: {manifest_path}"
        )

    manifest_dict = cast(dict[str, Any], manifest)
    validate_submission_manifest(manifest_dict)
    return manifest_dict


def validate_submission_manifest(manifest: dict[str, Any]) -> None:
    """Validate the structure of a v0.6 submission manifest."""
    _require_fields(manifest, REQUIRED_MANIFEST_FIELDS, "submission manifest")
    _validate_exact_value(manifest["schema_version"], "schema_version", "1")
    _validate_exact_value(manifest["module"], "module", "quillan")
    _validate_exact_value(
        manifest["record_type"], "record_type", "submission_manifest"
    )
    for field in ("class_id", "assignment_id", "student_id"):
        _validate_identifier(manifest[field], field)

    _validate_optional_positive_integer(manifest["expected_pages"], "expected_pages")
    _validate_allowed_value(
        manifest["submission_state"],
        "submission_state",
        ALLOWED_SUBMISSION_STATES,
    )
    _validate_timestamp(manifest["created_at"], "created_at")
    _validate_timestamp(manifest["updated_at"], "updated_at")
    _validate_json_object(manifest["module_details"], "module_details")

    pages = manifest["pages"]
    if not isinstance(pages, list):
        raise SubmissionManifestError("Field 'pages' must be a list.")

    seen_page_numbers: set[int] = set()
    seen_evidence_ids: set[str] = set()
    for index, page in enumerate(pages):
        context = f"pages[{index}]"
        if not isinstance(page, dict):
            raise SubmissionManifestError(f"{context} must be an object.")
        _validate_page(page, context, seen_page_numbers, seen_evidence_ids)


def _validate_page(
    page: dict[str, Any],
    context: str,
    seen_page_numbers: set[int],
    seen_evidence_ids: set[str],
) -> None:
    _require_fields(page, REQUIRED_PAGE_FIELDS, context)
    page_number = _validate_positive_integer(
        page["page_number"], f"{context}.page_number"
    )
    if page_number in seen_page_numbers:
        raise SubmissionManifestError(
            f"Duplicate page_number {page_number} in submission manifest."
        )
    seen_page_numbers.add(page_number)

    page_state = _validate_allowed_value(
        page["page_state"], f"{context}.page_state", ALLOWED_PAGE_STATES
    )
    selected_evidence_id = page["selected_evidence_id"]
    if selected_evidence_id is not None:
        _validate_non_empty_string(
            selected_evidence_id, f"{context}.selected_evidence_id"
        )

    evidence = page["evidence"]
    if not isinstance(evidence, list):
        raise SubmissionManifestError(f"Field '{context}.evidence' must be a list.")
    if page_state == "missing" and evidence:
        raise SubmissionManifestError(
            f"{context} has page_state 'missing' but contains evidence."
        )
    if page_state == "present" and not evidence:
        raise SubmissionManifestError(
            f"{context} has page_state 'present' but contains no evidence."
        )
    if page_state == "duplicate" and len(evidence) < 2:
        raise SubmissionManifestError(
            f"{context} has page_state 'duplicate' but has fewer than two "
            "evidence candidates."
        )

    page_evidence_ids: set[str] = set()
    selected_role_ids: list[str] = []
    for index, candidate in enumerate(evidence):
        evidence_context = f"{context}.evidence[{index}]"
        if not isinstance(candidate, dict):
            raise SubmissionManifestError(f"{evidence_context} must be an object.")
        evidence_id, evidence_role = _validate_evidence(
            candidate, evidence_context, seen_evidence_ids
        )
        page_evidence_ids.add(evidence_id)
        if evidence_role == "selected":
            selected_role_ids.append(evidence_id)

    if selected_evidence_id is None:
        if selected_role_ids:
            raise SubmissionManifestError(
                f"{context} has selected evidence role but "
                "selected_evidence_id is null."
            )
        return
    if selected_evidence_id not in page_evidence_ids:
        raise SubmissionManifestError(
            f"{context}.selected_evidence_id does not refer to evidence on "
            "the same page."
        )
    if selected_role_ids != [selected_evidence_id]:
        raise SubmissionManifestError(
            f"{context} must have exactly one candidate with evidence_role "
            "'selected', matching selected_evidence_id."
        )


def _validate_evidence(
    evidence: dict[str, Any],
    context: str,
    seen_evidence_ids: set[str],
) -> tuple[str, str]:
    _require_fields(evidence, REQUIRED_EVIDENCE_FIELDS, context)
    evidence_id = _validate_non_empty_string(
        evidence["evidence_id"], f"{context}.evidence_id"
    )
    if evidence_id in seen_evidence_ids:
        raise SubmissionManifestError(
            f"Duplicate evidence_id '{evidence_id}' in submission manifest."
        )
    seen_evidence_ids.add(evidence_id)

    _validate_workspace_relative_path(
        evidence["routed_evidence_path"], f"{context}.routed_evidence_path"
    )
    evidence_role = _validate_allowed_value(
        evidence["evidence_role"],
        f"{context}.evidence_role",
        ALLOWED_EVIDENCE_ROLES,
    )
    _validate_allowed_value(
        evidence["evidence_state"],
        f"{context}.evidence_state",
        ALLOWED_EVIDENCE_STATES,
    )
    _validate_optional_positive_integer(
        evidence["duplicate_number"], f"{context}.duplicate_number"
    )
    _validate_timestamp(evidence["created_at"], f"{context}.created_at")
    _validate_retained_source(
        evidence["retained_source"], f"{context}.retained_source"
    )
    _validate_json_object(
        evidence["module_details"], f"{context}.module_details"
    )
    return evidence_id, evidence_role


def _validate_retained_source(value: Any, context: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise SubmissionManifestError(f"{context} must be an object or null.")

    _require_fields(value, REQUIRED_RETAINED_SOURCE_FIELDS, context)
    _validate_non_empty_string(value["source_scan_id"], f"{context}.source_scan_id")
    _validate_filename(value["source_filename"], f"{context}.source_filename")
    source_sha256 = value["source_sha256"]
    if not isinstance(source_sha256, str) or not _SHA256_PATTERN.fullmatch(
        source_sha256
    ):
        raise SubmissionManifestError(
            f"Field '{context}.source_sha256' must be a 64-character "
            "hexadecimal SHA-256 digest."
        )
    _validate_workspace_relative_path(
        value["retained_source_path"], f"{context}.retained_source_path"
    )
    # This is the page inside the retained source, not the logical response page.
    _validate_optional_positive_integer(
        value["source_page_number"], f"{context}.source_page_number"
    )


def _validate_workspace_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or value == "":
        raise SubmissionManifestError(
            f"Field '{field}' must be a non-empty workspace-relative path string."
        )
    if "\0" in value:
        raise SubmissionManifestError(f"Field '{field}' must not contain null bytes.")

    path_variants = (PurePosixPath(value), PureWindowsPath(value))
    if any(path.anchor or path.drive for path in path_variants):
        raise SubmissionManifestError(
            f"Field '{field}' must be a workspace-relative path."
        )
    components = re.split(r"[\\/]", value)
    if "." in components or ".." in components:
        raise SubmissionManifestError(
            f"Field '{field}' must not contain '.' or '..' path components."
        )


def _validate_filename(value: Any, field: str) -> None:
    filename = _validate_non_empty_string(value, field)
    if "/" in filename or "\\" in filename or "\0" in filename:
        raise SubmissionManifestError(f"Field '{field}' must be a filename only.")
    if filename in {".", ".."}:
        raise SubmissionManifestError(f"Field '{field}' must be a valid filename.")


def _validate_timestamp(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise SubmissionManifestError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise SubmissionManifestError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SubmissionManifestError(
            f"Field '{field}' must be a timezone-aware ISO 8601 string."
        )


def _validate_exact_value(value: Any, field: str, expected: str) -> None:
    if value != expected:
        raise SubmissionManifestError(
            f"Field '{field}' must be the string '{expected}'."
        )


def _validate_identifier(value: Any, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise SubmissionManifestError(str(error)) from error


def _validate_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SubmissionManifestError(
            f"Field '{field}' must be a non-empty string."
        )
    return value


def _validate_positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SubmissionManifestError(
            f"Field '{field}' must be a positive integer."
        )
    return value


def _validate_optional_positive_integer(value: Any, field: str) -> None:
    if value is not None:
        _validate_positive_integer(value, field)


def _validate_allowed_value(
    value: Any, field: str, allowed_values: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise SubmissionManifestError(
            f"Invalid {field} {value!r}. Allowed values: {allowed}."
        )
    return value


def _validate_json_object(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise SubmissionManifestError(f"Field '{field}' must be an object.")


def _require_fields(
    data: dict[str, Any], fields: tuple[str, ...], context: str
) -> None:
    for field in fields:
        if field not in data:
            raise SubmissionManifestError(
                f"Missing required field '{field}' in {context}."
            )
