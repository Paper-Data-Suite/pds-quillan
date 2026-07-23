"""Canonical paths and safe writing for Quillan submission manifests."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal

from pds_core.routing_models import ModuleWorkRef

from quillan._path_safety import is_link_like as _shared_is_link_like
from quillan.atomic_record_io import (
    AtomicRecordConcurrencyError,
    AtomicRecordDurabilityError,
    AtomicRecordError,
    create_exclusive_record,
    revision_guarded_update,
)
from quillan.record_context import (
    QuillanAssignmentRecordContext,
    QuillanStudentReviewContext,
    student_record_paths,
)

from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    _preflight_arbitrary_file_destination,
    quillan_work_ref,
    initialize_student_submission_dir,
    student_submission_dir,
    submission_manifest_path as work_submission_manifest_path,
)


class SubmissionManifestPathError(ValueError):
    """Raised when a submission manifest path or write operation is invalid."""

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


class SubmissionManifestConcurrencyError(SubmissionManifestPathError):
    """The manifest changed after assembly loaded its original revision."""


@dataclass(frozen=True, slots=True)
class PersistedSubmissionManifest:
    path: Path
    status: Literal["created", "updated", "unchanged"]


def create_quillan_submission_manifest(
    assignment_context: QuillanAssignmentRecordContext,
    student_id: str,
    manifest: Mapping[str, object],
) -> PersistedSubmissionManifest:
    """Create only beneath a validated canonical assignment context."""
    if type(assignment_context) is not QuillanAssignmentRecordContext:
        raise SubmissionManifestPathError(
            "assignment_context must be an exact QuillanAssignmentRecordContext."
        )
    work_ref = assignment_context.paths.work_ref
    manifest_data = dict(manifest)
    _validate_manifest_identity(manifest_data, work_ref, student_id)
    initialize_student_submission_dir(
        assignment_context.paths.workspace_root, work_ref, student_id
    )
    paths = student_record_paths(
        assignment_context.paths.workspace_root, work_ref, student_id
    )
    return _persist_submission_manifest(
        paths.submission_manifest_path,
        manifest_data,
        preflight=lambda: student_record_paths(
            assignment_context.paths.workspace_root, work_ref, student_id
        ),
    )


def update_quillan_submission_manifest(
    context: QuillanStudentReviewContext,
    manifest: Mapping[str, object],
) -> PersistedSubmissionManifest:
    """Revision-guard an update using the manifest snapshot in ``context``."""
    if type(context) is not QuillanStudentReviewContext:
        raise SubmissionManifestPathError(
            "context must be an exact QuillanStudentReviewContext."
        )
    manifest_data = dict(manifest)
    _validate_manifest_identity(
        manifest_data, context.paths.work_ref, context.paths.student_id
    )
    return _persist_submission_manifest(
        context.paths.submission_manifest_path,
        manifest_data,
        expected_original_bytes=context.submission_record.original_bytes,
        preflight=lambda: student_record_paths(
            context.paths.workspace_root,
            context.paths.work_ref,
            context.paths.student_id,
        ),
    )


def submission_dir(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical directory for one student's Quillan submission."""
    try:
        work_ref = quillan_work_ref(class_id, assignment_id)
        return student_submission_dir(workspace_root, work_ref, student_id)
    except ValueError as error:
        raise SubmissionManifestPathError(str(error)) from error


def submission_manifest_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical submission.json path for one student."""
    try:
        work_ref = quillan_work_ref(class_id, assignment_id)
        return work_submission_manifest_path(workspace_root, work_ref, student_id)
    except ValueError as error:
        raise SubmissionManifestPathError(str(error)) from error


def write_submission_manifest(
    path: str | Path,
    manifest: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and safely write a submission manifest as UTF-8 JSON."""
    validate_submission_manifest(manifest)
    manifest_path = Path(path)

    try:
        _preflight_arbitrary_file_destination(manifest_path)
    except QuillanWorkPathError as error:
        raise SubmissionManifestPathError(str(error)) from error

    target_exists = os.path.lexists(manifest_path)
    if not overwrite and target_exists:
        raise SubmissionManifestPathError(
            f"Submission manifest already exists: {manifest_path}"
        )
    if overwrite and not target_exists:
        raise SubmissionManifestPathError(
            f"Submission manifest does not exist for overwrite: {manifest_path}"
        )

    parent = manifest_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SubmissionManifestPathError(
            f"Could not create submission manifest directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise SubmissionManifestPathError(
            f"Submission manifest parent is not a directory: {parent}"
        )

    expected_original = _read_safe_manifest_bytes(manifest_path) if overwrite else None
    persist_submission_manifest(
        manifest_path,
        manifest,
        expected_original_bytes=expected_original,
    )
    return manifest_path


def persist_submission_manifest(
    path: str | Path,
    manifest: dict[str, Any],
    *,
    expected_original_bytes: bytes | None = None,
) -> PersistedSubmissionManifest:
    """Low-level compatibility writer; canonical services use contexts instead."""
    manifest_path = Path(os.path.abspath(Path(path)))
    return _persist_submission_manifest(
        manifest_path,
        manifest,
        expected_original_bytes=expected_original_bytes,
        preflight=lambda: _preflight_arbitrary_file_destination(manifest_path),
    )


def _persist_submission_manifest(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    expected_original_bytes: bytes | None = None,
    preflight: Any,
) -> PersistedSubmissionManifest:
    """Atomically persist a preselected destination with guarded verification."""
    validate_submission_manifest(manifest)
    try:
        preflight()
        data = _canonical_manifest_bytes(manifest)
        if expected_original_bytes is None:
            result = create_exclusive_record(
                manifest_path,
                data,
                preflight=preflight,
                verify_bytes=lambda loaded: _verify_manifest_bytes(loaded, manifest),
            )
        else:
            result = revision_guarded_update(
                manifest_path,
                expected_original_bytes,
                data,
                preflight=preflight,
                verify_bytes=lambda loaded: _verify_manifest_bytes(loaded, manifest),
                lock_purpose="submission-update",
            )
    except AtomicRecordConcurrencyError as error:
        raise SubmissionManifestConcurrencyError(str(error)) from error
    except AtomicRecordDurabilityError as error:
        raise SubmissionManifestPathError(
            str(error),
            possibly_durable_path=error.possibly_durable_path,
            possible_lock_path=error.possible_lock_path,
        ) from error
    except (AtomicRecordError, QuillanWorkPathError, OSError) as error:
        raise SubmissionManifestPathError(str(error)) from error
    return PersistedSubmissionManifest(manifest_path, result.status)


def _canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                manifest,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SubmissionManifestPathError(
            f"Could not serialize submission manifest: {error}"
        ) from error


def _verify_manifest_bytes(data: bytes, expected: dict[str, Any]) -> None:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SubmissionManifestError(f"Duplicate manifest JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise SubmissionManifestError(f"Invalid JSON constant: {value}")

    try:
        loaded = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SubmissionManifestPathError(
            f"Persisted submission manifest is not strict JSON: {error}"
        ) from error
    if not isinstance(loaded, dict):
        raise SubmissionManifestPathError(
            "Persisted submission manifest is not a JSON object."
        )
    validate_submission_manifest(loaded)
    if loaded != expected:
        raise SubmissionManifestPathError(
            "Reloaded submission manifest differs from the committed model."
        )


def _write_manifest_temporary(path: Path, data: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _validate_manifest_identity(
    manifest: dict[str, Any], work_ref: ModuleWorkRef, student_id: str
) -> None:
    validate_submission_manifest(manifest)
    try:
        canonical_ref = quillan_work_ref(work_ref.class_id, work_ref.work_id)
    except (AttributeError, ValueError) as error:
        raise SubmissionManifestPathError(
            "work_ref must be an exact Quillan ModuleWorkRef."
        ) from error
    if work_ref != canonical_ref:
        raise SubmissionManifestPathError(
            "work_ref must be an exact Quillan ModuleWorkRef."
        )
    expected = {
        "class_id": work_ref.class_id,
        "assignment_id": work_ref.work_id,
        "student_id": student_id,
    }
    for field, value in expected.items():
        if manifest[field] != value:
            raise SubmissionManifestPathError(
                f"Submission manifest {field} does not match its canonical identity."
            )


def _restore_manifest_bytes(path: Path, data: bytes) -> None:
    temporary = _write_manifest_temporary(path, data)
    installed = False
    try:
        os.replace(temporary, path)
        installed = True
        if path.read_bytes() != data:
            raise OSError("restored manifest bytes did not verify")
    finally:
        if not installed:
            temporary.unlink(missing_ok=True)


def _reload_compare(path: Path, manifest: dict[str, Any], data: bytes) -> None:
    if _is_link_like(path) or not path.is_file() or path.read_bytes() != data:
        raise SubmissionManifestPathError(
            f"Persisted submission manifest bytes failed verification: {path}"
        )
    if load_submission_manifest(path) != manifest:
        raise SubmissionManifestPathError(
            f"Reloaded submission manifest differs from the committed model: {path}"
        )


def _existing_manifest_matches(path: Path, manifest: dict[str, Any]) -> bool:
    try:
        return load_submission_manifest(path) == manifest
    except (SubmissionManifestError, OSError):
        return False


def _read_safe_manifest_bytes(path: Path) -> bytes:
    """Read only after proving the current target is an ordinary non-link file."""
    if not os.path.lexists(path):
        raise SubmissionManifestConcurrencyError(
            f"Submission manifest is missing: {path}"
        )
    if _is_link_like(path) or not path.is_file():
        raise SubmissionManifestConcurrencyError(
            f"Submission manifest is not an ordinary non-link file: {path}"
        )
    try:
        return path.read_bytes()
    except OSError as error:
        raise SubmissionManifestPathError(
            f"Could not read submission manifest {path}: {error}"
        ) from error


def _is_link_like(path: Path) -> bool:
    return _shared_is_link_like(path)


__all__ = [
    "create_quillan_submission_manifest",
    "PersistedSubmissionManifest",
    "SubmissionManifestConcurrencyError",
    "SubmissionManifestPathError",
    "submission_dir",
    "submission_manifest_path",
    "update_quillan_submission_manifest",
]
