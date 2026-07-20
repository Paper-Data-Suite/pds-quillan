"""Canonical paths and safe writing for Quillan submission manifests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from quillan.submission_manifest import validate_submission_manifest
from quillan.work_paths import (
    QuillanWorkPathError,
    _preflight_arbitrary_file_destination,
    quillan_work_ref,
    student_submission_dir,
    submission_manifest_path as work_submission_manifest_path,
)


class SubmissionManifestPathError(ValueError):
    """Raised when a submission manifest path or write operation is invalid."""


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

    if not overwrite and manifest_path.exists():
        raise SubmissionManifestPathError(
            f"Submission manifest already exists: {manifest_path}"
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

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{manifest_path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(manifest, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if overwrite:
            os.replace(temporary_path, manifest_path)
        else:
            os.link(temporary_path, manifest_path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise SubmissionManifestPathError(
            f"Submission manifest already exists: {manifest_path}"
        ) from error
    except (OSError, TypeError, ValueError) as error:
        raise SubmissionManifestPathError(
            f"Could not write submission manifest {manifest_path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return manifest_path
