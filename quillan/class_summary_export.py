"""Comprehensive assignment-local class summary CSV for audit/troubleshooting."""

from __future__ import annotations

import csv
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
    ReportingStudent,
    build_assignment_reporting_snapshot,
)
from quillan.assignment_summary_context import relative_path_for
from quillan.work_paths import (
    QuillanWorkPathError,
    class_summary_path,
    preflight_work_file_destination,
    quillan_work_ref,
)
from quillan.report_csv import REPORT_CSV_ENCODING

BASE_CSV_COLUMNS: Final[tuple[str, ...]] = (
    "class_id",
    "assignment_id",
    "student_id",
    "student_display_name",
    "roster_status",
    "submission_manifest_path",
    "submission_state",
    "submission_valid",
    "review_record_path",
    "review_state",
    "review_valid",
    "minimum_requirement_status",
    "returned_without_full_review",
    "feedback_pdf_path",
    "feedback_pdf_status",
    "feedback_pdf_stale",
    "feedback_markdown_path",
    "feedback_markdown_status",
    "feedback_markdown_stale",
    "warnings",
)
CSV_COLUMNS: Final[tuple[str, ...]] = BASE_CSV_COLUMNS


class ClassSummaryExportError(Exception):
    """Raised when a class review summary cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedClassSummary:
    """Information about one generated assignment-local class summary."""

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
    returned_without_full_review_count: int
    feedback_pdf_present_count: int
    feedback_pdf_stale_count: int
    created_at: str
    overwrote_existing: bool


def class_summary_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the compatibility path for the comprehensive class summary."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return class_summary_path(
        workspace_root, quillan_work_ref(class_id, assignment_id)
    )


def export_class_review_summary(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedClassSummary:
    """Export one deterministic CSV row per rostered or discovered student."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        snapshot = build_assignment_reporting_snapshot(
            workspace_root,
            class_id,
            assignment_id,
        )
    except AssignmentReportingSnapshotError as error:
        raise ClassSummaryExportError(str(error)) from error
    return _export_class_review_summary_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=normalized_created_at,
    )


def export_class_review_summary_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedClassSummary:
    """Render the class summary from an already-loaded reporting snapshot."""
    return _export_class_review_summary_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=_normalize_timestamp(created_at),
    )


def _export_class_review_summary_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool,
    normalized_created_at: str,
) -> ExportedClassSummary:
    try:
        output_path = class_summary_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        )
        expected_output = preflight_work_file_destination(
            snapshot.workspace_root,
            quillan_work_ref(snapshot.class_id, snapshot.assignment_id),
            Path("exports") / "class_summary.csv",
        )
        if output_path != expected_output:
            raise ClassSummaryExportError("Class summary path is not canonical.")
    except (
        OSError,
        RuntimeError,
        ValueError,
        QuillanWorkPathError,
        ClassSummaryExportError,
    ) as error:
        raise ClassSummaryExportError(str(error)) from error

    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise ClassSummaryExportError(
            f"Class summary export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    fieldnames = _fieldnames(snapshot)
    rows = [_build_student_row(snapshot, student) for student in snapshot.students]
    _write_csv(output_path, rows, fieldnames=fieldnames, overwrite=overwrite)

    return ExportedClassSummary(
        class_id=snapshot.class_id,
        assignment_id=snapshot.assignment_id,
        summary_path=output_path,
        summary_relative_path=relative_path_for(
            output_path,
            snapshot.workspace_root,
        ),
        row_count=len(rows),
        ready_count=sum(student.review_valid for student in snapshot.students),
        missing_review_count=_warning_count(snapshot, "missing_review"),
        invalid_review_count=_warning_count(snapshot, "invalid_review"),
        missing_submission_count=_warning_count(snapshot, "missing_submission"),
        invalid_submission_count=_warning_count(snapshot, "invalid_submission"),
        identity_mismatch_count=_warning_count(snapshot, "identity_mismatch"),
        returned_without_full_review_count=sum(
            student.returned_without_full_review is True
            for student in snapshot.students
        ),
        feedback_pdf_present_count=sum(
            student.feedback_pdf.status == "present"
            for student in snapshot.students
        ),
        feedback_pdf_stale_count=sum(
            student.feedback_pdf.status == "stale"
            for student in snapshot.students
        ),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _fieldnames(snapshot: AssignmentReportingSnapshot) -> tuple[str, ...]:
    dynamic_columns: list[str] = []
    for standard in snapshot.focus_standards:
        dynamic_columns.extend(
            (
                f"rating__{standard.column_key}",
                f"rating_label__{standard.column_key}",
                f"rating_included_in_feedback__{standard.column_key}",
                f"rating_missing__{standard.column_key}",
            )
        )
    return BASE_CSV_COLUMNS[:-1] + tuple(dynamic_columns) + ("warnings",)


def _build_student_row(
    snapshot: AssignmentReportingSnapshot,
    student: ReportingStudent,
) -> dict[str, str]:
    warnings = [
        *student.warnings,
        *snapshot.column_key_warnings,
        *student.feedback_pdf.warnings,
        *student.feedback_markdown.warnings,
    ]
    row = {
        "class_id": snapshot.class_id,
        "assignment_id": snapshot.assignment_id,
        "student_id": student.student_id,
        "student_display_name": student.display_name,
        "roster_status": student.roster_status,
        "submission_manifest_path": student.submission_manifest_path,
        "submission_state": student.submission_state or "",
        "submission_valid": _csv_bool(student.submission_valid),
        "review_record_path": student.review_record_path,
        "review_state": student.review_state or "",
        "review_valid": _csv_bool(student.review_valid),
        "minimum_requirement_status": student.minimum_requirement_status or "",
        "returned_without_full_review": (
            ""
            if student.returned_without_full_review is None
            else _csv_bool(student.returned_without_full_review)
        ),
        "feedback_pdf_path": student.feedback_pdf.path,
        "feedback_pdf_status": student.feedback_pdf.status,
        "feedback_pdf_stale": student.feedback_pdf.stale,
        "feedback_markdown_path": student.feedback_markdown.path,
        "feedback_markdown_status": student.feedback_markdown.status,
        "feedback_markdown_stale": student.feedback_markdown.stale,
    }

    ratings_by_standard = {
        rating.standard_id: rating
        for rating in student.overall_standard_ratings
    }
    for standard in snapshot.focus_standards:
        key = standard.column_key
        rating = ratings_by_standard.get(standard.standard_id)
        if rating is None:
            row[f"rating__{key}"] = ""
            row[f"rating_label__{key}"] = ""
            row[f"rating_included_in_feedback__{key}"] = ""
            row[f"rating_missing__{key}"] = "true"
            continue
        label = rating.label
        if label is None:
            warnings.append("unknown_rating_value")
            label = ""
        row[f"rating__{key}"] = str(rating.value)
        row[f"rating_label__{key}"] = label
        row[f"rating_included_in_feedback__{key}"] = _csv_bool(
            rating.include_in_feedback
        )
        row[f"rating_missing__{key}"] = "false"

    row["warnings"] = ";".join(dict.fromkeys(warnings))
    return row


def _warning_count(snapshot: AssignmentReportingSnapshot, warning: str) -> int:
    return sum(warning in student.warnings for student in snapshot.students)


def _write_csv(
    path: Path,
    rows: list[dict[str, str]],
    *,
    fieldnames: tuple[str, ...],
    overwrite: bool,
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
                fieldnames=fieldnames,
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


def _csv_bool(value: bool) -> str:
    return "true" if value else "false"
