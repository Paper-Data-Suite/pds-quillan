"""Teacher-facing standards-linked review summary CSV export."""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import (
    StandardDefinition,
    StandardsLibrary,
    load_workspace_standards_library,
    find_standard_definition,
)

from quillan.review_record import ReviewRecordError, load_review_record
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)

CSV_COLUMNS: Final[tuple[str, ...]] = (
    "class_id",
    "assignment_id",
    "standard_id",
    "code",
    "short_name",
    "standard_source",
    "subject",
    "course",
    "domain",
    "student_count",
    "tag_student_count",
    "comment_student_count",
    "tag_count",
    "positive_tag_count",
    "developing_tag_count",
    "negative_tag_count",
    "neutral_tag_count",
    "selected_comment_count",
    "included_comment_count",
    "excluded_comment_count",
    "review_count",
    "missing_review_count",
    "invalid_review_count",
    "missing_submission_count",
    "invalid_submission_count",
    "identity_mismatch_count",
    "source",
)


class StandardsSummaryExportError(Exception):
    """Raised when a standards summary cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedStandardsSummary:
    """Information about one generated assignment standards summary."""

    class_id: str
    assignment_id: str
    summary_path: Path
    summary_relative_path: str
    row_count: int
    standard_count: int
    student_count: int
    review_count: int
    missing_review_count: int
    invalid_review_count: int
    missing_submission_count: int
    invalid_submission_count: int
    identity_mismatch_count: int
    created_at: str
    overwrote_existing: bool


@dataclass(slots=True)
class _StandardCounts:
    """Mutable aggregation state for one durable standard ID."""

    tag_students: set[str] = field(default_factory=set)
    comment_students: set[str] = field(default_factory=set)
    tag_count: int = 0
    positive_tag_count: int = 0
    developing_tag_count: int = 0
    negative_tag_count: int = 0
    neutral_tag_count: int = 0
    selected_comment_count: int = 0
    included_comment_count: int = 0
    excluded_comment_count: int = 0


def standards_summary_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the canonical assignment-level standards summary CSV path."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return (
        Path(workspace_root)
        / "classes"
        / class_id
        / "assignments"
        / assignment_id
        / "exports"
        / "standards_summary.csv"
    )


def export_standards_summary(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedStandardsSummary:
    """Export standards-linked tag and selected-comment aggregates."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        resolved_root = Path(workspace_root).resolve(strict=False)
        output_path = standards_summary_export_path(
            resolved_root, class_id, assignment_id
        )
    except (OSError, RuntimeError, StandardsSummaryExportError) as error:
        raise StandardsSummaryExportError(str(error)) from error

    submissions_dir = output_path.parent.parent / "submissions"
    if not submissions_dir.is_dir():
        raise StandardsSummaryExportError(
            "Assignment submissions directory does not exist: "
            f"{submissions_dir}"
        )

    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise StandardsSummaryExportError(
            f"Standards summary export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    try:
        student_dirs = sorted(
            (path for path in submissions_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
    except OSError as error:
        raise StandardsSummaryExportError(
            f"Could not discover student submission directories: {error}"
        ) from error

    aggregates: dict[str, _StandardCounts] = {}
    status_counts = {
        "review": 0,
        "missing_review": 0,
        "invalid_review": 0,
        "missing_submission": 0,
        "invalid_submission": 0,
        "identity_mismatch": 0,
    }
    try:
        standards_library = load_workspace_standards_library(resolved_root)
    except OSError:
        standards_library = StandardsLibrary(standards=(), profiles=())
    for student_dir in student_dirs:
        _inspect_student(
            class_id,
            assignment_id,
            student_dir,
            aggregates,
            status_counts,
        )

    rows = [
        _build_row(
            class_id,
            assignment_id,
            standard_id,
            aggregates[standard_id],
            status_counts,
            find_standard_definition(standards_library, standard_id),
        )
        for standard_id in sorted(aggregates)
    ]
    _write_csv(output_path, rows, overwrite=overwrite)

    return ExportedStandardsSummary(
        class_id=class_id,
        assignment_id=assignment_id,
        summary_path=output_path,
        summary_relative_path=_relative_path(output_path, resolved_root),
        row_count=len(rows),
        standard_count=len(aggregates),
        student_count=len(student_dirs),
        review_count=status_counts["review"],
        missing_review_count=status_counts["missing_review"],
        invalid_review_count=status_counts["invalid_review"],
        missing_submission_count=status_counts["missing_submission"],
        invalid_submission_count=status_counts["invalid_submission"],
        identity_mismatch_count=status_counts["identity_mismatch"],
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _inspect_student(
    class_id: str,
    assignment_id: str,
    student_dir: Path,
    aggregates: dict[str, _StandardCounts],
    status_counts: dict[str, int],
) -> None:
    student_id = student_dir.name
    manifest_path = student_dir / "submission.json"
    review_path = student_dir / "review.json"

    if not manifest_path.is_file():
        status_counts["missing_submission"] += 1
        return
    try:
        manifest = load_submission_manifest(manifest_path)
    except (OSError, SubmissionManifestError):
        status_counts["invalid_submission"] += 1
        return
    if _has_identity_mismatch(
        manifest, class_id, assignment_id, student_id
    ):
        status_counts["identity_mismatch"] += 1
        return

    if not review_path.is_file():
        status_counts["missing_review"] += 1
        return
    try:
        review = load_review_record(review_path)
    except (OSError, ReviewRecordError):
        status_counts["invalid_review"] += 1
        return
    if _has_identity_mismatch(review, class_id, assignment_id, student_id):
        status_counts["identity_mismatch"] += 1
        return

    status_counts["review"] += 1
    for tag in review["tags"]:
        standard_id = tag.get("standard_id")
        if standard_id is None:
            continue
        counts = aggregates.setdefault(standard_id, _StandardCounts())
        counts.tag_students.add(student_id)
        counts.tag_count += 1
        polarity_field = f"{tag['polarity']}_tag_count"
        setattr(counts, polarity_field, getattr(counts, polarity_field) + 1)

    for comment in review["comments"]:
        standard_id = comment.get("standard_id")
        if standard_id is None:
            continue
        counts = aggregates.setdefault(standard_id, _StandardCounts())
        counts.comment_students.add(student_id)
        counts.selected_comment_count += 1
        if comment["include_in_feedback"]:
            counts.included_comment_count += 1
        else:
            counts.excluded_comment_count += 1


def _build_row(
    class_id: str,
    assignment_id: str,
    standard_id: str,
    counts: _StandardCounts,
    status_counts: dict[str, int],
    definition: StandardDefinition | None,
) -> dict[str, str]:
    return {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "standard_id": standard_id,
        "code": definition.code if definition is not None else "",
        "short_name": definition.short_name if definition is not None else "",
        "standard_source": definition.source if definition is not None else "",
        "subject": definition.subject or "" if definition is not None else "",
        "course": definition.course or "" if definition is not None else "",
        "domain": definition.domain or "" if definition is not None else "",
        "student_count": str(
            len(counts.tag_students | counts.comment_students)
        ),
        "tag_student_count": str(len(counts.tag_students)),
        "comment_student_count": str(len(counts.comment_students)),
        "tag_count": str(counts.tag_count),
        "positive_tag_count": str(counts.positive_tag_count),
        "developing_tag_count": str(counts.developing_tag_count),
        "negative_tag_count": str(counts.negative_tag_count),
        "neutral_tag_count": str(counts.neutral_tag_count),
        "selected_comment_count": str(counts.selected_comment_count),
        "included_comment_count": str(counts.included_comment_count),
        "excluded_comment_count": str(counts.excluded_comment_count),
        "review_count": str(status_counts["review"]),
        "missing_review_count": str(status_counts["missing_review"]),
        "invalid_review_count": str(status_counts["invalid_review"]),
        "missing_submission_count": str(status_counts["missing_submission"]),
        "invalid_submission_count": str(status_counts["invalid_submission"]),
        "identity_mismatch_count": str(status_counts["identity_mismatch"]),
        "source": "review_tags_and_comments",
    }


def _has_identity_mismatch(
    record: dict[str, Any],
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> bool:
    return any(
        record[field] != expected
        for field, expected in (
            ("class_id", class_id),
            ("assignment_id", assignment_id),
            ("student_id", student_id),
        )
    )


def _write_csv(
    path: Path, rows: list[dict[str, str]], *, overwrite: bool
) -> None:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StandardsSummaryExportError(
            f"Could not create standards summary export directory {parent}: "
            f"{error}"
        ) from error
    if not parent.is_dir():
        raise StandardsSummaryExportError(
            f"Standards summary export parent is not a directory: {parent}"
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
        raise StandardsSummaryExportError(
            f"Standards summary export already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except (OSError, csv.Error) as error:
        raise StandardsSummaryExportError(
            f"Could not write standards summary export {path}: {error}"
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
            raise StandardsSummaryExportError(
                "created_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise StandardsSummaryExportError(
            "created_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise StandardsSummaryExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StandardsSummaryExportError(
            "created_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise StandardsSummaryExportError(str(error)) from error


def _relative_path(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(workspace_root).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise StandardsSummaryExportError(
            f"Could not resolve workspace-relative export path: {error}"
        ) from error
