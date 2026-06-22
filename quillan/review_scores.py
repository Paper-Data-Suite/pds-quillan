"""Teacher-entered criterion scores for submission review records."""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)

_SEQUENTIAL_SCORE_ID = re.compile(r"^score_(\d{4})$")


class ReviewScoreError(Exception):
    """Raised when a teacher score cannot be set safely."""


@dataclass(frozen=True, slots=True)
class UpdatedReviewScore:
    """Information about a criterion score set in a review record."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    score_id: str
    criterion_id: str
    score: int | float
    max_score: int | float
    review_state: str
    updated_at: str
    was_created: bool


def set_review_score(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    criterion_id: str,
    label: str,
    score: int | float,
    max_score: int | float,
    scale: str | None = None,
    teacher_note: str | None = None,
    updated_at: datetime | str | None = None,
) -> UpdatedReviewScore:
    """Set or update one teacher-entered criterion score."""
    normalized_criterion_id = _normalize_required_string(
        criterion_id, "criterion_id"
    )
    normalized_label = _normalize_required_string(label, "label")
    normalized_score = _normalize_number(score, "score", minimum=0)
    normalized_max_score = _normalize_number(
        max_score, "max_score", minimum=0, exclusive_minimum=True
    )
    if normalized_score > normalized_max_score:
        raise ReviewScoreError("score must be less than or equal to max_score.")
    normalized_scale = _normalize_optional_string(scale, "scale")
    normalized_teacher_note = _normalize_optional_string(
        teacher_note, "teacher_note"
    )
    normalized_updated_at = _normalize_timestamp(updated_at)

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
        raise ReviewScoreError(str(error)) from error

    if not manifest_path.exists():
        raise ReviewScoreError(
            "Submission manifest does not exist for "
            f"class={class_id}, assignment={assignment_id}, student={student_id}."
        )

    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise ReviewScoreError(
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
            raise ReviewScoreError(
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
            "created_at": normalized_updated_at,
            "updated_at": normalized_updated_at,
            "module_details": {},
        }

    existing_score = next(
        (
            candidate
            for candidate in updated_review["scores"]
            if candidate["criterion_id"] == normalized_criterion_id
        ),
        None,
    )
    was_created = existing_score is None
    if existing_score is None:
        score_id = _next_score_id(updated_review["scores"])
        existing_score = {"score_id": score_id}
        updated_review["scores"].append(existing_score)
    else:
        score_id = existing_score["score_id"]

    existing_score.clear()
    existing_score.update(
        {
            "score_id": score_id,
            "criterion_id": normalized_criterion_id,
            "label": normalized_label,
            "score": normalized_score,
            "max_score": normalized_max_score,
            "updated_at": normalized_updated_at,
            "module_details": {},
        }
    )
    if normalized_scale is not None:
        existing_score["scale"] = normalized_scale
    if normalized_teacher_note is not None:
        existing_score["teacher_note"] = normalized_teacher_note
    updated_review["updated_at"] = normalized_updated_at

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
        raise ReviewScoreError(f"Could not write review record: {error}") from error

    return UpdatedReviewScore(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=record_path,
        review_record_relative_path=record_relative_path,
        score_id=score_id,
        criterion_id=normalized_criterion_id,
        score=normalized_score,
        max_score=normalized_max_score,
        review_state=updated_review["review_state"],
        updated_at=normalized_updated_at,
        was_created=was_created,
    )


def _normalize_required_string(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewScoreError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_optional_string(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return _normalize_required_string(value, field)


def _normalize_number(
    value: int | float,
    field: str,
    *,
    minimum: int,
    exclusive_minimum: bool = False,
) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ReviewScoreError(f"{field} must be a finite number.")
    if exclusive_minimum and value <= minimum:
        raise ReviewScoreError(f"{field} must be greater than {minimum}.")
    if not exclusive_minimum and value < minimum:
        raise ReviewScoreError(
            f"{field} must be greater than or equal to {minimum}."
        )
    return value


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewScoreError("updated_at datetime must be timezone-aware.")
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewScoreError(
            "updated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewScoreError(
            "updated_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewScoreError(
            "updated_at must be a timezone-aware ISO 8601 string."
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
            raise ReviewScoreError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _next_score_id(scores: list[dict[str, Any]]) -> str:
    existing_ids = {score["score_id"] for score in scores}
    highest = max(
        (
            int(match.group(1))
            for score_id in existing_ids
            if (match := _SEQUENTIAL_SCORE_ID.fullmatch(score_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"score_{candidate_number:04d}"
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
        raise ReviewScoreError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error
