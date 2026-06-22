"""Canonical paths and safe writing for Quillan submission review records."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.review_record import validate_review_record


class ReviewRecordPathError(ValueError):
    """Raised when a review record path or write operation is invalid."""


def review_record_dir(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical directory for one student's review record."""
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


def review_record_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> Path:
    """Return the canonical review.json path for one student."""
    return (
        review_record_dir(workspace_root, class_id, assignment_id, student_id)
        / "review.json"
    )


def write_review_record(
    path: str | Path,
    record: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    """Validate and safely write a review record as UTF-8 JSON."""
    validate_review_record(record)
    review_path = Path(path)

    if not overwrite and review_path.exists():
        raise ReviewRecordPathError(f"Review record already exists: {review_path}")

    parent = review_path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ReviewRecordPathError(
            f"Could not create review record directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise ReviewRecordPathError(
            f"Review record parent is not a directory: {parent}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{review_path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(record, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if overwrite:
            os.replace(temporary_path, review_path)
        else:
            os.link(temporary_path, review_path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise ReviewRecordPathError(
            f"Review record already exists: {review_path}"
        ) from error
    except (OSError, TypeError, ValueError) as error:
        raise ReviewRecordPathError(
            f"Could not write review record {review_path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return review_path


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise ReviewRecordPathError(str(error)) from error
