"""Teacher-facing assignment-local Focus Standard summary CSV export."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from quillan.assignment_reporting_snapshot import (
    AssignmentReportingSnapshot,
    AssignmentReportingSnapshotError,
    ReportingStandard,
    build_assignment_reporting_snapshot,
)
from quillan.assignment_summary_context import relative_path_for
from quillan.work_paths import (
    QuillanWorkPathError,
    preflight_work_file_destination,
    quillan_work_ref,
    standards_summary_path,
)
from quillan.report_csv import REPORT_CSV_ENCODING

CSV_COLUMNS: Final[tuple[str, ...]] = (
    "class_id",
    "assignment_id",
    "standards_profile_id",
    "focus_standard_order",
    "standard_id",
    "standard_column_key",
    "standard_display_code",
    "standard_display_name",
    "students_expected",
    "students_with_submissions",
    "students_with_valid_reviews",
    "students_reviewed_for_standard",
    "students_returned_without_full_review",
    "students_missing_rating",
    "students_with_rating_included_in_feedback",
    "feedback_pdf_present_count",
    "feedback_pdf_stale_count",
    "rating_counts_json",
    "warnings",
)


class StandardsSummaryExportError(Exception):
    """Raised when a standards summary cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedStandardsSummary:
    """Information about one generated assignment Focus Standard summary."""

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
    returned_without_full_review_count: int
    created_at: str
    overwrote_existing: bool


def standards_summary_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the canonical assignment-local standards summary CSV path."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return standards_summary_path(
        workspace_root, quillan_work_ref(class_id, assignment_id)
    )


def export_standards_summary(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedStandardsSummary:
    """Export assignment-local Focus Standard rating aggregates."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        snapshot = build_assignment_reporting_snapshot(
            workspace_root,
            class_id,
            assignment_id,
        )
    except AssignmentReportingSnapshotError as error:
        raise StandardsSummaryExportError(str(error)) from error
    return _export_standards_summary_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=normalized_created_at,
    )


def export_standards_summary_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedStandardsSummary:
    """Render the standards summary from an already-loaded reporting snapshot."""
    return _export_standards_summary_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=_normalize_timestamp(created_at),
    )


def _export_standards_summary_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool,
    normalized_created_at: str,
) -> ExportedStandardsSummary:
    try:
        output_path = standards_summary_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        )
        expected_output = preflight_work_file_destination(
            snapshot.workspace_root,
            quillan_work_ref(snapshot.class_id, snapshot.assignment_id),
            Path("exports") / "standards_summary.csv",
        )
        if output_path != expected_output:
            raise StandardsSummaryExportError(
                "Standards summary path is not canonical."
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        QuillanWorkPathError,
        StandardsSummaryExportError,
    ) as error:
        raise StandardsSummaryExportError(str(error)) from error

    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise StandardsSummaryExportError(
            f"Standards summary export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    rows = [_build_row(snapshot, standard) for standard in snapshot.focus_standards]
    _write_csv(output_path, rows, overwrite=overwrite)

    return ExportedStandardsSummary(
        class_id=snapshot.class_id,
        assignment_id=snapshot.assignment_id,
        summary_path=output_path,
        summary_relative_path=relative_path_for(
            output_path,
            snapshot.workspace_root,
        ),
        row_count=len(rows),
        standard_count=len(rows),
        student_count=len(snapshot.students),
        review_count=sum(student.review_valid for student in snapshot.students),
        missing_review_count=_warning_count(snapshot, "missing_review"),
        invalid_review_count=_warning_count(snapshot, "invalid_review"),
        missing_submission_count=_warning_count(snapshot, "missing_submission"),
        invalid_submission_count=_warning_count(snapshot, "invalid_submission"),
        identity_mismatch_count=_warning_count(snapshot, "identity_mismatch"),
        returned_without_full_review_count=sum(
            student.returned_without_full_review is True
            for student in snapshot.students
        ),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _build_row(
    snapshot: AssignmentReportingSnapshot,
    standard: ReportingStandard,
) -> dict[str, str]:
    warnings = list(snapshot.column_key_warnings)
    if standard.metadata_missing:
        warnings.append("standard_metadata_missing")

    rating_counts = {str(value): 0 for value in snapshot.rating_values}
    students_with_submissions = 0
    students_with_valid_reviews = 0
    students_reviewed_for_standard = 0
    students_returned = 0
    students_missing_rating = 0
    students_included = 0
    feedback_pdf_present = 0
    feedback_pdf_stale = 0

    for student in snapshot.students:
        if student.submission_valid:
            students_with_submissions += 1
        if not student.review_valid:
            continue
        students_with_valid_reviews += 1

        if student.feedback_pdf.status == "present":
            feedback_pdf_present += 1
        elif student.feedback_pdf.status == "stale":
            feedback_pdf_stale += 1

        if student.returned_without_full_review:
            students_returned += 1
            continue

        ratings_by_standard = {
            rating.standard_id: rating
            for rating in student.overall_standard_ratings
        }
        if "rating_for_non_assignment_standard" in student.warnings:
            warnings.append("rating_for_non_assignment_standard")

        rating = ratings_by_standard.get(standard.standard_id)
        if rating is None:
            students_missing_rating += 1
            continue

        students_reviewed_for_standard += 1
        value = str(rating.value)
        if value not in rating_counts:
            warnings.append("unknown_rating_value")
            rating_counts[value] = 0
        rating_counts[value] += 1
        if rating.include_in_feedback:
            students_included += 1

    return {
        "class_id": snapshot.class_id,
        "assignment_id": snapshot.assignment_id,
        "standards_profile_id": snapshot.standards_profile_id,
        "focus_standard_order": str(standard.order),
        "standard_id": standard.standard_id,
        "standard_column_key": standard.column_key,
        "standard_display_code": standard.display_code,
        "standard_display_name": standard.display_name,
        "students_expected": str(len(snapshot.students)),
        "students_with_submissions": str(students_with_submissions),
        "students_with_valid_reviews": str(students_with_valid_reviews),
        "students_reviewed_for_standard": str(students_reviewed_for_standard),
        "students_returned_without_full_review": str(students_returned),
        "students_missing_rating": str(students_missing_rating),
        "students_with_rating_included_in_feedback": str(students_included),
        "feedback_pdf_present_count": str(feedback_pdf_present),
        "feedback_pdf_stale_count": str(feedback_pdf_stale),
        "rating_counts_json": json.dumps(
            rating_counts,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "warnings": ";".join(dict.fromkeys(warnings)),
    }


def _warning_count(snapshot: AssignmentReportingSnapshot, warning: str) -> int:
    return sum(warning in student.warnings for student in snapshot.students)


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
            encoding=REPORT_CSV_ENCODING,
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
