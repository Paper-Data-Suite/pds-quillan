"""Teacher-facing class review summary CSV export."""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.review_record import ReviewRecordError, load_review_record
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)

CSV_COLUMNS: Final[tuple[str, ...]] = (
    "class_id",
    "assignment_id",
    "student_id",
    "row_status",
    "review_state",
    "submission_state",
    "score_count",
    "total_score",
    "total_max_score",
    "included_comment_count",
    "selected_comment_count",
    "tag_count",
    "note_count",
    "feedback_export_exists",
    "submission_manifest_path",
    "review_record_path",
    "feedback_export_path",
    "error",
)


class ClassSummaryExportError(Exception):
    """Raised when a class review summary cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedClassSummary:
    """Information about one generated assignment-level class summary."""

    class_id: str
    assignment_id: str
    summary_path: Path
    summary_relative_path: str
    row_count: int
    ready_count: int
    missing_review_count: int
    invalid_review_count: int
    missing_submission_count: int
    invalid_submission_count: int
    identity_mismatch_count: int
    created_at: str
    overwrote_existing: bool


def class_summary_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the canonical assignment-level class summary CSV path."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return (
        Path(workspace_root)
        / "classes"
        / class_id
        / "assignments"
        / assignment_id
        / "exports"
        / "class_summary.csv"
    )


def export_class_review_summary(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedClassSummary:
    """Export one deterministic CSV row per discovered student directory."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        resolved_root = Path(workspace_root).resolve(strict=False)
        output_path = class_summary_export_path(
            resolved_root, class_id, assignment_id
        )
    except (OSError, RuntimeError, ClassSummaryExportError) as error:
        raise ClassSummaryExportError(str(error)) from error

    submissions_dir = output_path.parent.parent / "submissions"
    if not submissions_dir.is_dir():
        raise ClassSummaryExportError(
            "Assignment submissions directory does not exist: "
            f"{submissions_dir}"
        )

    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise ClassSummaryExportError(
            f"Class summary export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    try:
        student_dirs = sorted(
            (path for path in submissions_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
    except OSError as error:
        raise ClassSummaryExportError(
            f"Could not discover student submission directories: {error}"
        ) from error

    rows = [
        _build_student_row(
            resolved_root,
            class_id,
            assignment_id,
            student_dir,
        )
        for student_dir in student_dirs
    ]
    _write_csv(output_path, rows, overwrite=overwrite)

    counts = {
        status: sum(row["row_status"] == status for row in rows)
        for status in (
            "ready",
            "missing_review",
            "invalid_review",
            "missing_submission",
            "invalid_submission",
            "identity_mismatch",
        )
    }
    return ExportedClassSummary(
        class_id=class_id,
        assignment_id=assignment_id,
        summary_path=output_path,
        summary_relative_path=_relative_path(output_path, resolved_root),
        row_count=len(rows),
        ready_count=counts["ready"],
        missing_review_count=counts["missing_review"],
        invalid_review_count=counts["invalid_review"],
        missing_submission_count=counts["missing_submission"],
        invalid_submission_count=counts["invalid_submission"],
        identity_mismatch_count=counts["identity_mismatch"],
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _build_student_row(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    student_dir: Path,
) -> dict[str, str]:
    student_id = student_dir.name
    manifest_path = student_dir / "submission.json"
    review_path = student_dir / "review.json"
    feedback_path = student_dir / "exports" / "feedback.md"
    row = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "row_status": "",
        "review_state": "",
        "submission_state": "",
        "score_count": "",
        "total_score": "",
        "total_max_score": "",
        "included_comment_count": "",
        "selected_comment_count": "",
        "tag_count": "",
        "note_count": "",
        "feedback_export_exists": _csv_bool(feedback_path.is_file()),
        "submission_manifest_path": _relative_path(
            manifest_path, workspace_root
        ),
        "review_record_path": _relative_path(review_path, workspace_root),
        "feedback_export_path": _relative_path(feedback_path, workspace_root),
        "error": "",
    }

    if not manifest_path.is_file():
        return _failed_row(
            row,
            "missing_submission",
            f"Submission manifest is missing: {row['submission_manifest_path']}",
        )
    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError) as error:
        return _failed_row(
            row, "invalid_submission", f"Invalid submission manifest: {error}"
        )

    row["submission_state"] = str(manifest["submission_state"])
    mismatch = _identity_mismatch(
        manifest, class_id, assignment_id, student_id, "Submission manifest"
    )
    if mismatch is not None:
        return _failed_row(row, "identity_mismatch", mismatch)

    if not review_path.is_file():
        return _failed_row(
            row,
            "missing_review",
            f"Review record is missing: {row['review_record_path']}",
        )
    try:
        review = load_review_record(review_path)
    except (OSError, ReviewRecordError) as error:
        return _failed_row(
            row, "invalid_review", f"Invalid review record: {error}"
        )

    mismatch = _identity_mismatch(
        review, class_id, assignment_id, student_id, "Review record"
    )
    if mismatch is not None:
        return _failed_row(row, "identity_mismatch", mismatch)

    scores = review["scores"]
    comments = review["comments"]
    row.update(
        {
            "row_status": "ready",
            "review_state": str(review["review_state"]),
            "score_count": str(len(scores)),
            "total_score": _format_number(
                sum(score["score"] for score in scores)
            ),
            "total_max_score": _format_number(
                sum(score["max_score"] for score in scores)
            ),
            "included_comment_count": str(
                sum(comment["include_in_feedback"] for comment in comments)
            ),
            "selected_comment_count": str(len(comments)),
            "tag_count": str(len(review["tags"])),
            "note_count": str(len(review["notes"])),
        }
    )
    return row


def _failed_row(
    row: dict[str, str], status: str, message: str
) -> dict[str, str]:
    row["row_status"] = status
    row["error"] = " ".join(message.split())
    return row


def _identity_mismatch(
    record: dict[str, Any],
    class_id: str,
    assignment_id: str,
    student_id: str,
    record_name: str,
) -> str | None:
    expected_values = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
    }
    for field, expected in expected_values.items():
        actual = record[field]
        if actual != expected:
            return (
                f"{record_name} {field} is {actual!r}, expected {expected!r}."
            )
    return None


def _write_csv(
    path: Path, rows: list[dict[str, str]], *, overwrite: bool
) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ClassSummaryExportError(
            f"Could not create class summary export directory {parent}: {error}"
        ) from error
    if not parent.is_dir():
        raise ClassSummaryExportError(
            f"Class summary export parent is not a directory: {parent}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(
                temporary_file,
                fieldnames=CSV_COLUMNS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
            temporary_path.unlink()
        temporary_path = None
    except FileExistsError as error:
        raise ClassSummaryExportError(
            f"Class summary export already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except (OSError, csv.Error) as error:
        raise ClassSummaryExportError(
            f"Could not write class summary export {path}: {error}"
        ) from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ClassSummaryExportError(
                "created_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise ClassSummaryExportError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ClassSummaryExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ClassSummaryExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise ClassSummaryExportError(str(error)) from error


def _relative_path(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise ClassSummaryExportError(
            f"Could not resolve workspace-relative export path: {error}"
        ) from error


def _csv_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_number(value: int | float) -> str:
    return format(value, "g")
