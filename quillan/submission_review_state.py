"""Teacher-controlled lightweight submission review-state updates."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.submission_manifest import (
    ALLOWED_SUBMISSION_STATES,
    SubmissionManifestError,
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
    write_submission_manifest,
)


class SubmissionReviewStateError(Exception):
    """Raised when a submission review state cannot be updated safely."""


@dataclass(frozen=True, slots=True)
class UpdatedSubmissionReviewState:
    """Information about a submission review-state update."""

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
    """Update only the lightweight review state for one student submission."""
    if state not in ALLOWED_SUBMISSION_STATES:
        allowed = ", ".join(sorted(ALLOWED_SUBMISSION_STATES))
        raise SubmissionReviewStateError(
            f"Invalid submission review state {state!r}. Allowed states: {allowed}."
        )

    try:
        resolved_workspace_root = Path(workspace_root).resolve(strict=False)
        manifest_path = submission_manifest_path(
            resolved_workspace_root,
            class_id,
            assignment_id,
            student_id,
        )
    except (OSError, RuntimeError, SubmissionManifestPathError) as error:
        raise SubmissionReviewStateError(str(error)) from error

    if not manifest_path.exists():
        raise SubmissionReviewStateError(
            "Submission manifest does not exist for "
            f"class={class_id}, assignment={assignment_id}, student={student_id}."
        )

    try:
        relative_path = manifest_path.resolve(strict=False).relative_to(
            resolved_workspace_root
        ).as_posix()
        manifest = load_submission_manifest(manifest_path)
    except (
        OSError,
        RuntimeError,
        ValueError,
        SubmissionManifestError,
    ) as error:
        raise SubmissionReviewStateError(
            f"Could not load submission manifest: {error}"
        ) from error

    _validate_manifest_identity(
        manifest,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )
    normalized_updated_at = _normalize_timestamp(updated_at)
    previous_state = manifest["submission_state"]
    updated_manifest = copy.deepcopy(manifest)
    updated_manifest["submission_state"] = state
    updated_manifest["updated_at"] = normalized_updated_at

    try:
        validate_submission_manifest(updated_manifest)
        write_submission_manifest(
            manifest_path,
            updated_manifest,
            overwrite=True,
        )
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
