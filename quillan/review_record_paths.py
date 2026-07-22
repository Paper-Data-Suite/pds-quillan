"""Domain-aware canonical persistence for Quillan review records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Literal

from quillan.atomic_record_io import (
    AtomicRecordConcurrencyError,
    AtomicRecordDurabilityError,
    AtomicRecordError,
    create_exclusive_record,
    revision_guarded_update,
)
from quillan.record_context import (
    QuillanStudentReviewContext,
    student_record_paths,
)
from quillan.review_record import ReviewRecordError, validate_review_record
from quillan.work_paths import (
    QuillanWorkPathError,
    _preflight_arbitrary_file_destination,
    quillan_work_ref,
    review_record_path as work_review_record_path,
    student_submission_dir,
)


class ReviewRecordPathError(ValueError):
    """Raised when a contextual review write is invalid or uncertain."""

    def __init__(
        self,
        message: str,
        *,
        possibly_durable_path: Path | None = None,
        possible_lock_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.possibly_durable_path = possibly_durable_path
        self.possible_lock_path = possible_lock_path


class ReviewRecordConcurrencyError(ReviewRecordPathError):
    """The canonical review changed after its context snapshot was loaded."""


@dataclass(frozen=True, slots=True)
class PersistedReviewRecord:
    """Exact location and outcome of one contextual review write."""

    path: Path
    relative_path: str
    status: Literal["created", "updated", "unchanged"]

    def __post_init__(self) -> None:
        if type(self.path) is not type(Path()) or not self.path.is_absolute():
            raise ReviewRecordPathError("Persisted review path must be absolute.")
        if type(self.relative_path) is not str or not self.relative_path:
            raise ReviewRecordPathError("Persisted review relative path is required.")
        if self.status not in {"created", "updated", "unchanged"}:
            raise ReviewRecordPathError("Persisted review status is invalid.")


def create_quillan_review_record(
    context: QuillanStudentReviewContext,
    record: Mapping[str, object],
) -> PersistedReviewRecord:
    """Create a review only for a validated assignment and submission context."""
    _require_context(context)
    if context.review_record is not None:
        raise ReviewRecordPathError("Review creation context already has a review.")
    record_data = dict(record)
    _validate_review_for_context(record_data, context)
    data = _canonical_review_bytes(record_data)
    path = context.paths.review_record_path
    try:
        result = create_exclusive_record(
            path,
            data,
            preflight=lambda: _preflight_context_target(context),
            verify_bytes=lambda loaded: _verify_review_bytes(loaded, record_data),
        )
    except AtomicRecordConcurrencyError as error:
        raise ReviewRecordConcurrencyError(str(error)) from error
    except AtomicRecordDurabilityError as error:
        raise ReviewRecordPathError(
            str(error),
            possibly_durable_path=error.possibly_durable_path,
            possible_lock_path=error.possible_lock_path,
        ) from error
    except (AtomicRecordError, OSError) as error:
        raise ReviewRecordPathError(str(error)) from error
    return PersistedReviewRecord(
        path,
        context.paths.review_relative_path,
        result.status,
    )


def update_quillan_review_record(
    context: QuillanStudentReviewContext,
    record: Mapping[str, object],
) -> PersistedReviewRecord:
    """Update only the exact review revision carried by ``context``."""
    _require_context(context)
    if context.review_record is None:
        raise ReviewRecordPathError("Review update requires a loaded review snapshot.")
    record_data = dict(record)
    _validate_review_for_context(record_data, context)
    data = _canonical_review_bytes(record_data)
    path = context.paths.review_record_path
    try:
        result = revision_guarded_update(
            path,
            context.review_record.original_bytes,
            data,
            preflight=lambda: _preflight_context_target(context),
            verify_bytes=lambda loaded: _verify_review_bytes(loaded, record_data),
            lock_purpose="review-update",
        )
    except AtomicRecordConcurrencyError as error:
        raise ReviewRecordConcurrencyError(str(error)) from error
    except AtomicRecordDurabilityError as error:
        raise ReviewRecordPathError(
            str(error),
            possibly_durable_path=error.possibly_durable_path,
            possible_lock_path=error.possible_lock_path,
        ) from error
    except (AtomicRecordError, OSError) as error:
        raise ReviewRecordPathError(str(error)) from error
    return PersistedReviewRecord(
        path,
        context.paths.review_relative_path,
        result.status,
    )


def persist_quillan_review_record(
    context: QuillanStudentReviewContext,
    record: Mapping[str, object],
) -> PersistedReviewRecord:
    """Persist through a validated context; raw path creation is not supported."""
    if context.review_record is None:
        return create_quillan_review_record(context, record)
    return update_quillan_review_record(context, record)


def review_record_dir(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical directory for one student's review record."""
    try:
        return student_submission_dir(
            workspace_root, quillan_work_ref(class_id, assignment_id), student_id
        )
    except ValueError as error:
        raise ReviewRecordPathError(str(error)) from error


def review_record_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical review.json path for one student."""
    try:
        return work_review_record_path(
            workspace_root, quillan_work_ref(class_id, assignment_id), student_id
        )
    except ValueError as error:
        raise ReviewRecordPathError(str(error)) from error


def write_review_record(
    path: str | Path,
    record: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Low-level compatibility writer for fixtures and record initialization.

    Canonical runtime services must use the context-aware create/update APIs.
    """
    validate_review_record(record)
    target = Path(os.path.abspath(Path(path)))
    try:
        _preflight_arbitrary_file_destination(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        def preflight() -> None:
            _preflight_arbitrary_file_destination(target)

        data = _canonical_review_bytes(record)
        if overwrite:
            if not os.path.lexists(target):
                raise ReviewRecordPathError(
                    f"Review record does not exist for overwrite: {target}"
                )
            expected = target.read_bytes()
            revision_guarded_update(
                target,
                expected,
                data,
                preflight=preflight,
                verify_bytes=lambda loaded: _verify_review_bytes(loaded, record),
                lock_purpose="low-level-review-update",
            )
        else:
            create_exclusive_record(
                target,
                data,
                preflight=preflight,
                verify_bytes=lambda loaded: _verify_review_bytes(loaded, record),
            )
    except AtomicRecordConcurrencyError as error:
        raise ReviewRecordConcurrencyError(str(error)) from error
    except AtomicRecordDurabilityError as error:
        raise ReviewRecordPathError(
            str(error),
            possibly_durable_path=error.possibly_durable_path,
            possible_lock_path=error.possible_lock_path,
        ) from error
    except (AtomicRecordError, QuillanWorkPathError, OSError) as error:
        raise ReviewRecordPathError(str(error)) from error
    return target


def _require_context(context: QuillanStudentReviewContext) -> None:
    if type(context) is not QuillanStudentReviewContext:
        raise ReviewRecordPathError(
            "context must be an exact QuillanStudentReviewContext."
        )


def _validate_review_for_context(
    record: dict[str, Any], context: QuillanStudentReviewContext
) -> None:
    validate_review_record(record)
    expected = {
        "class_id": context.paths.work_ref.class_id,
        "assignment_id": context.paths.work_ref.work_id,
        "student_id": context.paths.student_id,
        "assignment_path": context.paths.assignment_relative_path,
        "submission_manifest_path": context.paths.submission_relative_path,
    }
    for field, value in expected.items():
        if record[field] != value:
            raise ReviewRecordPathError(
                f"Review record {field} does not match its validated context."
            )


def _preflight_context_target(context: QuillanStudentReviewContext) -> None:
    paths = student_record_paths(
        context.paths.workspace_root,
        context.paths.work_ref,
        context.paths.student_id,
    )
    if paths.review_record_path != context.paths.review_record_path:
        raise ReviewRecordPathError("Review context destination changed.")


def _canonical_review_bytes(record: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ReviewRecordPathError(f"Could not serialize review record: {error}") from error


def _verify_review_bytes(data: bytes, expected: dict[str, Any]) -> None:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ReviewRecordError(f"Duplicate review JSON key: {key}")
            value[key] = item
        return value

    try:
        loaded = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ReviewRecordError(f"Invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReviewRecordPathError(f"Persisted review is not strict JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise ReviewRecordPathError("Persisted review is not a JSON object.")
    validate_review_record(loaded)
    if loaded != expected:
        raise ReviewRecordPathError(
            "Reloaded review record differs from the committed model."
        )


__all__ = [
    "PersistedReviewRecord",
    "ReviewRecordConcurrencyError",
    "ReviewRecordPathError",
    "create_quillan_review_record",
    "persist_quillan_review_record",
    "review_record_dir",
    "review_record_path",
    "update_quillan_review_record",
]
