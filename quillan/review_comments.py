"""Selection of reusable shared-bank comments into submission reviews.

Legacy v1 comment-bank review writes are retained only for compatibility and tests.
They are not exposed through active v0.8.6 menu or CLI routes.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.comment_banks import (
    CommentBankError,
    comment_bank_path,
    load_comment_bank,
)
from quillan.review_record import (
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
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)
from quillan.submission_guidance import missing_submission_guidance

_SEQUENTIAL_COMMENT_ID = re.compile(r"^comment_record_(\d{4})$")


class ReviewCommentError(Exception):
    """Raised when a reusable comment cannot be selected safely."""


@dataclass(frozen=True, slots=True)
class AddedReviewComment:
    """Information about one reusable comment appended to a review."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    comment_record_id: str
    bank_id: str
    comment_id: str
    label: str
    include_in_feedback: bool
    review_state: str
    created_at: str


def add_review_comment(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    bank_id: str,
    comment_id: str,
    standard_id: str | None = None,
    include_in_feedback: bool | None = None,
    page_number: int | None = None,
    evidence_id: str | None = None,
    location_type: str | None = None,
    location_value: int | list[int] | str | None = None,
    created_at: datetime | str | None = None,
) -> AddedReviewComment:
    """Append one snapshotted shared-bank comment to a review record."""
    normalized_bank_id = _normalize_identifier(bank_id, "bank_id")
    normalized_comment_id = _normalize_identifier(comment_id, "comment_id")
    normalized_standard = _normalize_optional_string(standard_id, "standard_id")
    normalized_evidence = _normalize_optional_string(evidence_id, "evidence_id")
    _validate_page_number(page_number)
    try:
        location = build_location(location_type, location_value, page_number)
    except ReviewTargetError as error:
        raise ReviewCommentError(str(error)) from error
    if include_in_feedback is not None and not isinstance(
        include_in_feedback, bool
    ):
        raise ReviewCommentError("include_in_feedback must be a boolean or None.")
    normalized_created_at = _normalize_timestamp(created_at)
    resolved_root = Path(workspace_root).resolve(strict=False)

    try:
        bank_path = comment_bank_path(resolved_root, normalized_bank_id)
        manifest_path = submission_manifest_path(
            resolved_root, class_id, assignment_id, student_id
        )
        record_path = review_record_path(
            resolved_root, class_id, assignment_id, student_id
        )
    except (
        OSError,
        RuntimeError,
        CommentBankError,
        SubmissionManifestPathError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewCommentError(str(error)) from error

    try:
        bank = load_comment_bank(bank_path)
    except (OSError, CommentBankError) as error:
        raise ReviewCommentError(f"Could not load comment bank: {error}") from error
    if bank["bank_id"] != normalized_bank_id:
        raise ReviewCommentError(
            f"Comment bank bank_id is {bank['bank_id']!r}, expected "
            f"{normalized_bank_id!r}."
        )
    matches = [
        item
        for item in bank["comments"]
        if item["comment_id"] == normalized_comment_id
    ]
    if not matches:
        raise ReviewCommentError(
            f"Comment bank '{normalized_bank_id}' has no comment "
            f"'{normalized_comment_id}'."
        )
    if len(matches) > 1:
        raise ReviewCommentError(
            f"Comment bank '{normalized_bank_id}' has multiple comments "
            f"named '{normalized_comment_id}'."
        )
    source_comment = matches[0]
    if not source_comment["student_facing"]:
        raise ReviewCommentError(
            f"Comment '{normalized_comment_id}' is not student-facing and "
            "cannot be selected into review comments."
        )
    selected_standard = _select_standard(source_comment, normalized_standard)
    selected_include = (
        source_comment["include_in_feedback_default"]
        if include_in_feedback is None
        else include_in_feedback
    )

    if not manifest_path.exists():
        raise ReviewCommentError(missing_submission_guidance())
    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise ReviewCommentError(
            f"Could not load submission manifest: {error}"
        ) from error
    _validate_identity(
        manifest, "Submission manifest", class_id, assignment_id, student_id
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

    if record_path.exists():
        try:
            review = load_review_record(record_path)
        except (OSError, ReviewRecordError) as error:
            raise ReviewCommentError(
                f"Could not load review record: {error}"
            ) from error
        _validate_identity(
            review, "Review record", class_id, assignment_id, student_id
        )
        updated_review = copy.deepcopy(review)
        if updated_review["review_state"] == "not_started":
            updated_review["review_state"] = "in_progress"
    else:
        updated_review = {
            "schema_version": "1",
            "module": "quillan",
            "record_type": "submission_review",
            "class_id": class_id,
            "assignment_id": assignment_id,
            "student_id": student_id,
            "submission_manifest_path": _workspace_relative_path(
                manifest_path, resolved_root, "submission manifest"
            ),
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

    comment_record_id = _next_comment_record_id(updated_review["comments"])
    selected_comment = {
        "comment_record_id": comment_record_id,
        "source": "comment_bank",
        "bank_id": normalized_bank_id,
        "comment_id": normalized_comment_id,
        "label": source_comment["label"],
        "text": source_comment["text"],
        "include_in_feedback": selected_include,
        "created_at": normalized_created_at,
        "module_details": {},
    }
    optional_target_fields = {
        "page_number": page_number,
        "evidence_id": normalized_evidence,
        "location": location,
    }
    selected_comment.update(
        {
            field: value
            for field, value in optional_target_fields.items()
            if value is not None
        }
    )
    if selected_standard is not None:
        selected_comment["standard_id"] = selected_standard
    updated_review["comments"].append(selected_comment)
    updated_review["updated_at"] = normalized_created_at

    try:
        validate_review_record(updated_review)
        write_review_record(
            record_path, updated_review, overwrite=record_path.exists()
        )
        relative_path = _workspace_relative_path(
            record_path, resolved_root, "review record"
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        ReviewRecordError,
        ReviewRecordPathError,
    ) as error:
        raise ReviewCommentError(
            f"Could not write review record: {error}"
        ) from error

    return AddedReviewComment(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=record_path,
        review_record_relative_path=relative_path,
        comment_record_id=comment_record_id,
        bank_id=normalized_bank_id,
        comment_id=normalized_comment_id,
        label=source_comment["label"],
        include_in_feedback=selected_include,
        review_state=updated_review["review_state"],
        created_at=normalized_created_at,
    )


def _select_standard(
    source_comment: dict[str, Any], requested: str | None
) -> str | None:
    standards = cast(list[str], source_comment.get("standard_ids", []))
    if requested is not None:
        if requested not in standards:
            raise ReviewCommentError(
                f"standard_id {requested!r} is not available on comment "
                f"{source_comment['comment_id']!r}."
            )
        return requested
    if len(standards) == 1:
        return standards[0]
    return None


def _normalize_identifier(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise ReviewCommentError(f"{field} must be a valid identifier.")
    normalized = value.strip()
    try:
        validate_identifier(normalized, field)
    except IdentifierValidationError as error:
        raise ReviewCommentError(str(error)) from error
    return normalized


def _normalize_optional_string(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ReviewCommentError(f"{field} must be a non-empty string.")
    return value.strip()


def _validate_page_number(value: int | None) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 1
    ):
        raise ReviewCommentError("page_number must be a positive integer.")


def _validate_manifest_references(
    manifest: dict[str, Any],
    *,
    page_number: int | None,
    evidence_id: str | None,
) -> None:
    pages = {page["page_number"]: page for page in manifest["pages"]}
    if page_number is not None and page_number not in pages:
        raise ReviewCommentError(
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
        raise ReviewCommentError(
            f"evidence_id {evidence_id!r} does not exist in the submission manifest."
        )
    if page_number is not None and evidence_pages[evidence_id] != page_number:
        raise ReviewCommentError(
            f"evidence_id {evidence_id!r} occurs on page "
            f"{evidence_pages[evidence_id]}, not page {page_number}."
        )


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewCommentError("created_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewCommentError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewCommentError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewCommentError(
            "created_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identity(
    record: dict[str, Any],
    record_name: str,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> None:
    for field, expected in {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }.items():
        if record[field] != expected:
            raise ReviewCommentError(
                f"{record_name} {field} is {record[field]!r}, "
                f"expected {expected!r}."
            )


def _next_comment_record_id(comments: list[dict[str, Any]]) -> str:
    existing_ids = {comment["comment_record_id"] for comment in comments}
    highest = max(
        (
            int(match.group(1))
            for comment_id in existing_ids
            if (match := _SEQUENTIAL_COMMENT_ID.fullmatch(comment_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"comment_record_{candidate_number:04d}"
        if candidate not in existing_ids:
            return candidate
        candidate_number += 1


def _workspace_relative_path(
    path: Path, workspace_root: Path, description: str
) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise ReviewCommentError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error
