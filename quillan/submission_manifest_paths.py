"""Canonical paths and safe writing for Quillan submission manifests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.submission_manifest import validate_submission_manifest


class SubmissionManifestPathError(ValueError):
    """Raised when a submission manifest path or write operation is invalid."""


def submission_dir(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical directory for one student's Quillan submission."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    _validate_identifier(student_id, "student_id")
    return (
        Path(workspace_root)
        / "classes"
        / class_id
        / "assignments"
        / assignment_id
        / "submissions"
        / student_id
    )


def submission_manifest_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical submission.json path for one student."""
    return (
        submission_dir(workspace_root, class_id, assignment_id, student_id)
        / "submission.json"
    )


def write_submission_manifest(
    path: str | Path,
    manifest: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and safely write a submission manifest as UTF-8 JSON."""
    validate_submission_manifest(manifest)
    manifest_path = Path(path)

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


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise SubmissionManifestPathError(str(error)) from error
