"""Teacher-entered quick notes for submission review records."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quillan.review_record import (
    ReviewRecordError,
    build_empty_review_record,
    load_review_record,
    validate_review_record,
)
from quillan.review_record_paths import (
    ReviewRecordPathError,
    review_record_path,
    write_review_record,
)
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)
from quillan.submission_guidance import missing_submission_guidance
from quillan.work_paths import relative_assignment_path

_SEQUENTIAL_NOTE_ID = re.compile(r"^note_(\d{4})$")


class ReviewNoteError(Exception):
    """Raised when a teacher note cannot be added safely."""


@dataclass(frozen=True, slots=True)
class AddedReviewNote:
    """Information about a teacher note added to a review record."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    note_id: str
    review_state: str
    created_at: str


def add_review_note(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    text: str,
    *,
    created_at: datetime | str | None = None,
) -> AddedReviewNote:
    """Append one teacher-entered note to a canonical review record."""
    normalized_text = _normalize_text(text)
    normalized_created_at = _normalize_timestamp(created_at)

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
        raise ReviewNoteError(str(error)) from error

    if not manifest_path.exists():
        raise ReviewNoteError(missing_submission_guidance())

    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise ReviewNoteError(
            f"Could not load submission manifest: {error}"
        ) from error
    _validate_identity(
        manifest,
        record_name="Submission manifest",
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
    )

    if record_path.exists():
        try:
            review = load_review_record(record_path)
        except (OSError, ReviewRecordError) as error:
            raise ReviewNoteError(
                f"Could not load review record: {error}"
            ) from error
        _validate_identity(
            review,
            record_name="Review record",
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
        )
        updated_review = copy.deepcopy(review)
    else:
        manifest_relative_path = _workspace_relative_path(
            manifest_path, resolved_workspace_root, "submission manifest"
        )
        updated_review = build_empty_review_record(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            submission_manifest_path=manifest_relative_path,
            assignment_path=relative_assignment_path(class_id, assignment_id),
            created_at=normalized_created_at,
        )

    note_id = _next_note_id(updated_review["private_notes"])
    updated_review["private_notes"].append(
        {
            "private_note_id": note_id,
            "text": normalized_text,
            "created_at": normalized_created_at,
            "updated_at": normalized_created_at,
            "module_details": {},
        }
    )
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
        raise ReviewNoteError(f"Could not write review record: {error}") from error

    return AddedReviewNote(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=record_path,
        review_record_relative_path=record_relative_path,
        note_id=note_id,
        review_state=updated_review["review_state"],
        created_at=normalized_created_at,
    )


def _normalize_text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewNoteError("Teacher note text must be a non-empty string.")
    return value.strip()


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewNoteError("created_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewNoteError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewNoteError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewNoteError(
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
            raise ReviewNoteError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _next_note_id(notes: list[dict[str, Any]]) -> str:
    existing_ids = {note["private_note_id"] for note in notes}
    highest = max(
        (
            int(match.group(1))
            for note_id in existing_ids
            if (match := _SEQUENTIAL_NOTE_ID.fullmatch(note_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"note_{candidate_number:04d}"
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
        raise ReviewNoteError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error
