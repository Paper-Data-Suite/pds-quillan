"""Teacher-entered assignment requirement checks for review records."""

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
    build_empty_review_record,
    load_review_record,
    validate_review_record,
)
from quillan.review_record_paths import (
    ReviewRecordPathError,
    review_record_path,
    write_review_record,
)
from quillan.submission_guidance import missing_submission_guidance
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)
from quillan.submission_manifest_paths import (
    SubmissionManifestPathError,
    submission_manifest_path,
)

_SEQUENTIAL_REQUIREMENT_CHECK_ID = re.compile(r"^requirement_check_(\d{4})$")


class ReviewRequirementError(Exception):
    """Raised when a requirement check cannot be set safely."""


@dataclass(frozen=True, slots=True)
class UpdatedRequirementCheck:
    """Information about a requirement check set in a review record."""

    class_id: str
    assignment_id: str
    student_id: str
    review_record_path: Path
    review_record_relative_path: str
    requirement_check_id: str
    requirement_key: str
    met: bool
    review_state: str
    updated_at: str
    was_created: bool


def set_requirement_check(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
    *,
    requirement_key: str,
    label: str,
    expected: str | int | float,
    met: bool,
    teacher_note: str | None = None,
    updated_at: datetime | str | None = None,
) -> UpdatedRequirementCheck:
    """Set or update one teacher-entered assignment requirement check."""
    normalized_key = _normalize_required_string(
        requirement_key, "requirement_key"
    )
    normalized_label = _normalize_required_string(label, "label")
    normalized_expected = _normalize_expected(expected)
    if not isinstance(met, bool):
        raise ReviewRequirementError("met must be a boolean.")
    normalized_note = _normalize_optional_string(teacher_note, "teacher_note")
    normalized_updated_at = _normalize_timestamp(updated_at)

    try:
        resolved_root = Path(workspace_root).resolve(strict=False)
        manifest_path = submission_manifest_path(
            resolved_root,
            class_id,
            assignment_id,
            student_id,
        )
        record_path = review_record_path(
            resolved_root,
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
        raise ReviewRequirementError(str(error)) from error

    if not manifest_path.exists():
        raise ReviewRequirementError(missing_submission_guidance())

    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        raise ReviewRequirementError(
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
            raise ReviewRequirementError(
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
            updated_review["review_state"] = "requirements_checked"
    else:
        updated_review = build_empty_review_record(
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
            submission_manifest_path=_workspace_relative_path(
                manifest_path, resolved_root, "submission manifest"
            ),
            assignment_path=(
                f"classes/{class_id}/assignments/{assignment_id}/assignment.json"
            ),
            created_at=normalized_updated_at,
        )
        updated_review["review_state"] = "requirements_checked"

    checks = updated_review["minimum_requirement_checks"]
    existing_check = next(
        (
            candidate
            for candidate in checks
            if candidate["requirement_key"] == normalized_key
        ),
        None,
    )
    was_created = existing_check is None
    if existing_check is None:
        check_id = _next_requirement_check_id(checks)
        existing_check = {"requirement_check_id": check_id}
        checks.append(existing_check)
    else:
        check_id = existing_check["requirement_check_id"]

    existing_check.clear()
    existing_check.update(
        {
            "requirement_check_id": check_id,
            "requirement_key": normalized_key,
            "label": normalized_label,
            "expected": normalized_expected,
            "met": met,
            "updated_at": normalized_updated_at,
            "module_details": {},
        }
    )
    if normalized_note is not None:
        existing_check["teacher_note"] = normalized_note
    updated_review["updated_at"] = normalized_updated_at

    try:
        validate_review_record(updated_review)
        write_review_record(
            record_path,
            updated_review,
            overwrite=record_path.exists(),
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
        raise ReviewRequirementError(
            f"Could not write review record: {error}"
        ) from error

    return UpdatedRequirementCheck(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        review_record_path=record_path,
        review_record_relative_path=relative_path,
        requirement_check_id=check_id,
        requirement_key=normalized_key,
        met=met,
        review_state=updated_review["review_state"],
        updated_at=normalized_updated_at,
        was_created=was_created,
    )


def _normalize_required_string(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewRequirementError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_optional_string(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return _normalize_required_string(value, field)


def _normalize_expected(value: str | int | float) -> str | int | float:
    if isinstance(value, str):
        if not value.strip():
            raise ReviewRequirementError(
                "expected must be a non-empty string or finite number."
            )
        return value.strip()
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ReviewRequirementError(
            "expected must be a non-empty string or finite number."
        )
    return value


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReviewRequirementError(
                "updated_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise ReviewRequirementError(
            "updated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReviewRequirementError(
            "updated_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewRequirementError(
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
    for field, expected in {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }.items():
        actual = record[field]
        if actual != expected:
            raise ReviewRequirementError(
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )


def _next_requirement_check_id(checks: list[dict[str, Any]]) -> str:
    existing_ids = {check["requirement_check_id"] for check in checks}
    highest = max(
        (
            int(match.group(1))
            for check_id in existing_ids
            if (match := _SEQUENTIAL_REQUIREMENT_CHECK_ID.fullmatch(check_id))
        ),
        default=0,
    )
    candidate_number = highest + 1
    while True:
        candidate = f"requirement_check_{candidate_number:04d}"
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
        raise ReviewRequirementError(
            f"Could not resolve workspace-relative {description} path: {error}"
        ) from error
