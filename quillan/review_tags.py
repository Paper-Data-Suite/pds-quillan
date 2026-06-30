"""Teacher-entered structured tags for submission review records."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pds_core.standards import (
    StandardsValidationError,
    load_workspace_standards_library,
    validate_profile_standard_selection,
)

from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.review_record import (
    ALLOWED_TAG_POLARITIES,
    ReviewRecordError,
    load_review_record,
    validate_review_record,
)
from quillan.review_record_paths import (
    ReviewRecordPathError,
    review_record_path,
    write_review_record,
)
from quillan.review_targets import ReviewTargetError, build_location
from quillan.storage import assignment_config_path
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)
from quillan.submission_guidance import missing_submission_guidance

_SEQUENTIAL_TAG_ID = re.compile(r"^tag_(\d{4})$")


class ReviewTagError(Exception):
    """Raised when a teacher tag cannot be added safely."""


@dataclass(frozen=True, slots=True)
class AddedReviewTag:
    """Information about a teacher tag added to a review record."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    tag_id: str
    polarity: str
    review_state: str
    created_at: str


def add_review_tag(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    label: str,
    polarity: str,
    standard_id: str | None = None,
    comment_id: str | None = None,
    criterion_id: str | None = None,
    source: str | None = None,
    tag_bank_id: str | None = None,
    tag_template_id: str | None = None,
    severity: int | None = None,
    teacher_note: str | None = None,
    page_number: int | None = None,
    evidence_id: str | None = None,
    location_type: str | None = None,
    location_value: int | list[int] | str | None = None,
    created_at: datetime | str | None = None,
) -> AddedReviewTag:
    """Append one teacher-entered structured tag to a review record."""
    normalized_label = _normalize_required_string(label, "label")
    normalized_polarity = _normalize_polarity(polarity)
    normalized_standard = _normalize_optional_string(standard_id, "standard_id")
    normalized_comment = _normalize_optional_string(comment_id, "comment_id")
    normalized_criterion = _normalize_optional_string(criterion_id, "criterion_id")
    normalized_source = _normalize_optional_source(source)
    normalized_tag_bank = _normalize_optional_identifier(tag_bank_id, "tag_bank_id")
    normalized_tag_template = _normalize_optional_identifier(
        tag_template_id, "tag_template_id"
    )
    normalized_note = _normalize_optional_string(teacher_note, "teacher_note")
    normalized_evidence = _normalize_optional_string(evidence_id, "evidence_id")
    _validate_severity(severity)
    _validate_page_number(page_number)
    try:
        location = build_location(location_type, location_value, page_number)
    except ReviewTargetError as error:
        raise ReviewTagError(str(error)) from error
    normalized_created_at = _normalize_timestamp(created_at)

    if normalized_comment is not None and normalized_standard is None:
        raise ReviewTagError("comment_id requires standard_id.")
    if normalized_source == "tag_bank" and (
        normalized_tag_bank is None or normalized_tag_template is None
    ):
        raise ReviewTagError("tag_bank source requires tag_bank_id and tag_template_id.")
    if normalized_source == "custom" and (
        normalized_tag_bank is not None or normalized_tag_template is not None
    ):
        raise ReviewTagError(
            "tag_bank_id and tag_template_id must be omitted for custom tags."
        )
    if normalized_source is None and (
        normalized_tag_bank is not None or normalized_tag_template is not None
    ):
        raise ReviewTagError(
            "source is required when tag_bank_id or tag_template_id is supplied."
        )

    try:
        resolved_workspace_root = Path(workspace_root).resolve(strict=False)
        manifest_path = submission_manifest_path(
            resolved_workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
        record_path = review_record_path(
            resolved_workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
    except (
        OSError,
        RuntimeError,
        SubmissionManifestPathError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewTagError(str(error)) from error

    if not manifest_path.exists():
        raise ReviewTagError(missing_submission_guidance())

    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise ReviewTagError(
            f"Could not load submission manifest: {error}"
        ) from error
    _validate_identity(
        manifest,
        record_name="Submission manifest",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    _validate_manifest_references(
        manifest,
        page_number=(
            page_number
            if page_number is not None
            else (
                location["value"]
                if location is not None and location["type"] == "page"
                else None
            )
        ),
        evidence_id=normalized_evidence,
    )

    if normalized_standard is not None:
        severity = _validate_profile_references(
            resolved_workspace_root,
            class_id=class_id,
            assignment_id=assignment_id,
            standard_id=normalized_standard,
            comment_id=normalized_comment,
            label=normalized_label,
            polarity=normalized_polarity,
            severity=severity,
        )

    if record_path.exists():
        try:
            review = load_review_record(record_path)
        except (OSError, ReviewRecordError) as error:
            raise ReviewTagError(f"Could not load review record: {error}") from error
        _validate_identity(
            review,
            record_name="Review record",
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
        )
        updated_review = copy.deepcopy(review)
        if updated_review["review_state"] == "not_started":
            updated_review["review_state"] = "in_progress"
    else:
        manifest_relative_path = _workspace_relative_path(
            manifest_path, resolved_workspace_root, "submission manifest"
        )
        updated_review = {
            "schema_version": "1",
            "module": "quillan",
            "record_type": "submission_review",
            "class_id": class_id,
            "assignment_id": assignment_id,
            "student_id": student_id,
            "submission_manifest_path": manifest_relative_path,
            "review_state": "in_progress",
            "notes": [],
            "tags": [],
            "scores": [],
            "comments": [],
            "requirement_checks": [],
            "created_at": normalized_created_at,
            "updated_at": normalized_created_at,
            "module_details": {},
        }

    tag_id = _next_tag_id(updated_review["tags"])
    tag: dict[str, Any] = {
        "tag_id": tag_id,
        "label": normalized_label,
        "polarity": normalized_polarity,
        "created_at": normalized_created_at,
        "module_details": {},
    }
    optional_fields = {
        "source": normalized_source,
        "tag_bank_id": normalized_tag_bank,
        "tag_template_id": normalized_tag_template,
        "standard_id": normalized_standard,
        "comment_id": normalized_comment,
        "criterion_id": normalized_criterion,
        "severity": severity,
        "teacher_note": normalized_note,
        "page_number": page_number,
        "evidence_id": normalized_evidence,
        "location": location,
    }
    tag.update(
        {field: value for field, value in optional_fields.items() if value is not None}
    )
    updated_review["tags"].append(tag)
    updated_review["updated_at"] = normalized_created_at

    try:
        validate_review_record(updated_review)
        write_review_record(
            record_path,
            updated_review,
            overwrite=record_path.exists(),
        )
        record_relative_path = _workspace_relative_path(
            record_path, resolved_workspace_root, "review record"
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        ReviewRecordError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewTagError(f"Could not write review record: {error}") from error

    return AddedReviewTag(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=record_path,
        review_record_relative_path=record_relative_path,
        tag_id=tag_id,
        polarity=normalized_polarity,
        review_state=updated_review["review_state"],
        created_at=normalized_created_at,
    )


def _normalize_required_string(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewTagError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_optional_string(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return _normalize_required_string(value, field)


def _normalize_polarity(value: str) -> str:
    if not isinstance(value, str) or value not in ALLOWED_TAG_POLARITIES:
        allowed = ", ".join(sorted(ALLOWED_TAG_POLARITIES))
        raise ReviewTagError(
            f"Invalid polarity {value!r}. Allowed values: {allowed}."
        )
    return value


def _normalize_optional_source(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_required_string(value, "source")
    if normalized not in {"tag_bank", "custom"}:
        raise ReviewTagError(
            "Invalid source "
            f"{normalized!r}. Allowed values: custom, tag_bank."
        )
    return normalized


def _normalize_optional_identifier(value: str | None, field: str) -> str | None:
    normalized = _normalize_optional_string(value, field)
    if normalized is None:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", normalized):
        raise ReviewTagError(f"{field} must be a valid identifier.")
    return normalized


def _validate_severity(value: int | None) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
    ):
        raise ReviewTagError("severity must be a non-negative integer.")


def _validate_page_number(value: int | None) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 1
    ):
        raise ReviewTagError("page_number must be a positive integer.")


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewTagError("created_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewTagError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewTagError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewTagError(
            "created_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identity(
    record: dict[str, Any],
    *,
    record_name: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    requested = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }
    for field, expected in requested.items():
        actual = record[field]
        if actual != expected:
            raise ReviewTagError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _validate_manifest_references(
    manifest: dict[str, Any],
    *,
    page_number: int | None,
    evidence_id: str | None,
) -> None:
    pages = {page["page_number"]: page for page in manifest["pages"]}
    if page_number is not None and page_number not in pages:
        raise ReviewTagError(
            f"page_number {page_number} does not exist in the submission manifest."
        )
    if evidence_id is None:
        return
    evidence_pages = {
        candidate["evidence_id"]: page["page_number"]
        for page in manifest["pages"]
        for candidate in page["evidence"]
    }
    if evidence_id not in evidence_pages:
        raise ReviewTagError(
            f"evidence_id {evidence_id!r} does not exist in the submission manifest."
        )
    if page_number is not None and evidence_pages[evidence_id] != page_number:
        raise ReviewTagError(
            f"evidence_id {evidence_id!r} occurs on page "
            f"{evidence_pages[evidence_id]}, not page {page_number}."
        )


def _validate_profile_references(
    workspace_root: Path,
    *,
    class_id: str,
    assignment_id: str,
    standard_id: str,
    comment_id: str | None,
    label: str,
    polarity: str,
    severity: int | None,
) -> int | None:
    config_path = assignment_config_path(
        workspace_root, class_id, assignment_id
    )
    try:
        assignment = load_assignment_config(config_path)
    except (OSError, AssignmentConfigError) as error:
        raise ReviewTagError(f"Could not load assignment config: {error}") from error
    if assignment["assignment_id"] != assignment_id:
        raise ReviewTagError(
            "Assignment config assignment_id is "
            f"{assignment['assignment_id']!r}, expected {assignment_id!r}."
        )
    if class_id not in assignment["class_ids"]:
        raise ReviewTagError(
            f"Assignment config does not include class_id {class_id!r}."
        )

    profile_id = cast(str, assignment["standards_profile_id"])
    try:
        library = load_workspace_standards_library(workspace_root)
        validate_profile_standard_selection(
            library,
            profile_id=profile_id,
            selected_standard_ids=(standard_id,),
        )
    except (OSError, StandardsValidationError) as error:
        raise ReviewTagError(
            "Could not validate standard_id against pds-core standards "
            f"profile {profile_id!r}: {error}"
        ) from error
    return severity


def _next_tag_id(tags: list[dict[str, Any]]) -> str:
    existing_ids = {tag["tag_id"] for tag in tags}
    highest = max(
        (
            int(match.group(1))
            for tag_id in existing_ids
            if (match := _SEQUENTIAL_TAG_ID.fullmatch(tag_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"tag_{candidate_number:04d}"
        if candidate not in existing_ids:
            return candidate
        candidate_number += 1


def _workspace_relative_path(
    path: Path,
    workspace_root: Path,
    description: str,
) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise ReviewTagError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error
