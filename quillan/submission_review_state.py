"""Teacher-controlled lightweight submission-state updates."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.submission_manifest import (
    ALLOWED_SUBMISSION_STATES,
    SubmissionManifestError,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    update_quillan_submission_manifest,
)
from quillan.submission_guidance import missing_submission_guidance
from quillan.record_context import (
    MissingSubmissionError,
    QuillanRecordContextError,
    ReviewLoadingPolicy,
    load_quillan_student_review_context,
    mutable_json_copy,
)
from quillan.work_paths import quillan_work_ref


class SubmissionReviewStateError(Exception):
    """Raised when a lightweight submission state cannot be updated safely."""


@dataclass(frozen=True, slots=True)
class UpdatedSubmissionReviewState:
    """Information about a lightweight submission-state update."""

    class_id: str
    assignment_id: str
    student_id: str
    manifest_path: Path
    manifest_relative_path: str
    previous_state: str
    new_state: str
    updated_at: str


def update_submission_review_state(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    state: str,
    *,
    updated_at: datetime | str | None = None,
) -> UpdatedSubmissionReviewState:
    """Update only the lightweight state for one student submission."""
    if state not in ALLOWED_SUBMISSION_STATES:
        allowed = ", ".join(sorted(ALLOWED_SUBMISSION_STATES))
        raise SubmissionReviewStateError(
            f"Invalid lightweight submission state {state!r}. Allowed states: {allowed}."
        )

    work_ref = quillan_work_ref(class_id, assignment_id)
    try:
        context = load_quillan_student_review_context(
            workspace_root,
            work_ref,
            student_id,
            review_policy=ReviewLoadingPolicy.REVIEW_OPTIONAL,
        )
    except MissingSubmissionError as error:
        raise SubmissionReviewStateError(missing_submission_guidance()) from error
    except (OSError, RuntimeError, QuillanRecordContextError) as error:
        raise SubmissionReviewStateError(str(error)) from error
    manifest_path = context.paths.submission_manifest_path
    relative_path = context.paths.submission_relative_path
    manifest = mutable_json_copy(context.submission)
    normalized_updated_at = _normalize_timestamp(updated_at)
    previous_state = manifest["submission_state"]
    updated_manifest = copy.deepcopy(manifest)
    updated_manifest["submission_state"] = state
    updated_manifest["updated_at"] = normalized_updated_at

    try:
        validate_submission_manifest(updated_manifest)
        update_quillan_submission_manifest(context, updated_manifest)
    except (
        OSError,
        RuntimeError,
        ValueError,
        SubmissionManifestError,
        SubmissionManifestPathError,
    ) as error:
        raise SubmissionReviewStateError(
            f"Could not write submission manifest: {error}"
        ) from error

    return UpdatedSubmissionReviewState(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        manifest_path=manifest_path,
        manifest_relative_path=relative_path,
        previous_state=previous_state,
        new_state=state,
        updated_at=normalized_updated_at,
    )


def _validate_manifest_identity(
    manifest: dict[str, Any],
    *,
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
        actual = manifest[field]
        if actual != expected:
            raise SubmissionReviewStateError(
                f"Submission manifest {field} is {actual!r}, expected {expected!r}."
            )


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise SubmissionReviewStateError(
                "updated_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise SubmissionReviewStateError(
            "updated_at must be a timezone-aware datetime or ISO 8601 string."
        )

    try:
        validate_submission_manifest(
            {
                "schema_version": "1",
                "module": "quillan",
                "record_type": "submission_manifest",
                "class_id": "timestamp_validation",
                "assignment_id": "timestamp_validation",
                "student_id": "timestamp_validation",
                "expected_pages": None,
                "submission_state": "unreviewed",
                "pages": [],
                "created_at": value,
                "updated_at": value,
                "module_details": {},
            }
        )
    except SubmissionManifestError as error:
        raise SubmissionReviewStateError(
            f"Invalid updated_at timestamp: {error}"
        ) from error
    return value
