"""Canonical paths and safe writing for Quillan submission manifests."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
    validate_submission_manifest,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    _preflight_arbitrary_file_destination,
    quillan_work_ref,
    student_submission_dir,
    submission_manifest_path as work_submission_manifest_path,
)


class SubmissionManifestPathError(ValueError):
    """Raised when a submission manifest path or write operation is invalid."""


class SubmissionManifestConcurrencyError(SubmissionManifestPathError):
    """The manifest changed after assembly loaded its original revision."""


@dataclass(frozen=True, slots=True)
class PersistedSubmissionManifest:
    path: Path
    status: Literal["created", "updated", "unchanged"]


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
    """Atomically create or revision-guard update a validated manifest."""
    validate_submission_manifest(manifest)
    manifest_path = Path(path)
    try:
        _preflight_arbitrary_file_destination(manifest_path)
    except QuillanWorkPathError as error:
        raise SubmissionManifestPathError(str(error)) from error
    parent = manifest_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        _preflight_arbitrary_file_destination(manifest_path)
    except (OSError, QuillanWorkPathError) as error:
        raise SubmissionManifestPathError(
            f"Could not prepare submission manifest directory {parent}: {error}"
        ) from error
    data = _canonical_manifest_bytes(manifest)
    if expected_original_bytes is None:
        if os.path.lexists(manifest_path):
            raise SubmissionManifestPathError(
                f"Submission manifest already exists: {manifest_path}"
            )
        create_temporary = _write_manifest_temporary(manifest_path, data)
        try:
            os.link(create_temporary, manifest_path)
            create_temporary.unlink()
        except FileExistsError as error:
            raise SubmissionManifestConcurrencyError(
                f"Submission manifest was concurrently created: {manifest_path}"
            ) from error
        except OSError as error:
            raise SubmissionManifestPathError(
                f"Could not install submission manifest {manifest_path}: {error}"
            ) from error
        finally:
            try:
                create_temporary.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            _reload_compare(manifest_path, manifest, data)
        except Exception:
            if (
                not _is_link_like(manifest_path)
                and manifest_path.is_file()
                and manifest_path.read_bytes() == data
            ):
                manifest_path.unlink()
            raise
        return PersistedSubmissionManifest(manifest_path, "created")

    if not isinstance(expected_original_bytes, bytes):
        raise SubmissionManifestPathError(
            "expected_original_bytes must be bytes or None."
        )
    current_bytes = _read_safe_manifest_bytes(manifest_path)
    if current_bytes == expected_original_bytes and _existing_manifest_matches(
        manifest_path, manifest
    ):
        return PersistedSubmissionManifest(manifest_path, "unchanged")
    if data == expected_original_bytes:
        if _read_safe_manifest_bytes(manifest_path) != expected_original_bytes:
            raise SubmissionManifestConcurrencyError(
                "Submission manifest changed before unchanged-state verification."
            )
        _reload_compare(manifest_path, manifest, data)
        return PersistedSubmissionManifest(manifest_path, "unchanged")
    lock_path = parent / f".{manifest_path.name}.assembly.lock"
    lock_created = False
    temporary: Path | None = None
    try:
        if os.path.lexists(lock_path):
            raise SubmissionManifestConcurrencyError(
                f"Submission assembly lock already exists: {lock_path}"
            )
        with lock_path.open("xb") as lock_file:
            lock_created = True
            lock_file.write(b"quillan-submission-assembly-v1\n")
            lock_file.flush()
            os.fsync(lock_file.fileno())
        if _read_safe_manifest_bytes(manifest_path) != expected_original_bytes:
            raise SubmissionManifestConcurrencyError(
                "Submission manifest changed after assembly loaded it."
            )
        temporary = _write_manifest_temporary(manifest_path, data)
        if _read_safe_manifest_bytes(manifest_path) != expected_original_bytes:
            raise SubmissionManifestConcurrencyError(
                "Submission manifest changed before atomic replacement."
            )
        os.replace(temporary, manifest_path)
        temporary = None
        try:
            _reload_compare(manifest_path, manifest, data)
        except Exception as error:
            try:
                _restore_manifest_bytes(manifest_path, expected_original_bytes)
            except Exception as rollback_error:
                raise SubmissionManifestPathError(
                    "Updated manifest verification failed and original-byte "
                    f"restoration failed: {rollback_error}"
                ) from error
            raise
        return PersistedSubmissionManifest(manifest_path, "updated")
    except SubmissionManifestPathError:
        raise
    except OSError as error:
        raise SubmissionManifestPathError(
            f"Could not atomically update submission manifest {manifest_path}: {error}"
        ) from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        if lock_created:
            try:
                if _is_link_like(lock_path) or not lock_path.is_file():
                    raise SubmissionManifestPathError(
                        f"Assembly lock changed filesystem type: {lock_path}"
                    )
                lock_path.unlink()
            except OSError as error:
                raise SubmissionManifestPathError(
                    f"Could not remove submission assembly lock {lock_path}: {error}"
                ) from error


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
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction is not None and is_junction())


__all__ = [
    "PersistedSubmissionManifest",
    "SubmissionManifestConcurrencyError",
    "SubmissionManifestPathError",
    "persist_submission_manifest",
    "submission_dir",
    "submission_manifest_path",
    "write_submission_manifest",
]
