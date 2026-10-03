"""Compact teacher-facing student-by-standard performance summary export."""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
    preflight_work_file_destination,
    quillan_work_ref,
    student_performance_summary_path,
)
from quillan.report_csv import REPORT_CSV_ENCODING

MISSING_RATING = ""
BASE_CSV_COLUMNS = (
    "student_id",
    "student_display_name",
    "review_status",
    "minimum_requirements",
)


class StudentPerformanceSummaryExportError(Exception):
    """Raised when a student performance summary cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedStudentPerformanceSummary:
    """Information about one generated student performance summary."""

    class_id: str
    assignment_id: str
    summary_path: Path
    summary_relative_path: str
    row_count: int
    reviewed_count: int
    returned_without_full_review_count: int
    missing_submission_count: int
    missing_review_count: int
    invalid_submission_count: int
    invalid_review_count: int
    identity_mismatch_count: int
    created_at: str
    overwrote_existing: bool


def student_performance_summary_export_path(
    workspace_root: str | Path, class_id: str, assignment_id: str
) -> Path:
    """Return the assignment-local student performance summary CSV path."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return student_performance_summary_path(
        workspace_root, quillan_work_ref(class_id, assignment_id)
    )


def export_student_performance_summary(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedStudentPerformanceSummary:
    """Export one compact row per rostered or discovered student."""
    normalized_created_at = _normalize_timestamp(created_at)
    try:
        snapshot = build_assignment_reporting_snapshot(
            workspace_root,
            class_id,
            assignment_id,
        )
    except AssignmentReportingSnapshotError as error:
        raise StudentPerformanceSummaryExportError(str(error)) from error
    return _export_student_performance_summary_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=normalized_created_at,
    )


def export_student_performance_summary_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool = False,
    created_at: datetime | str | None = None,
) -> ExportedStudentPerformanceSummary:
    """Render the compact summary from an already-loaded reporting snapshot."""
    return _export_student_performance_summary_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_created_at=_normalize_timestamp(created_at),
    )


def _export_student_performance_summary_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool,
    normalized_created_at: str,
) -> ExportedStudentPerformanceSummary:
    try:
        path = student_performance_summary_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        )
        expected_path = preflight_work_file_destination(
            snapshot.workspace_root,
            quillan_work_ref(snapshot.class_id, snapshot.assignment_id),
            Path("exports") / "student_performance_summary.csv",
        )
        if path != expected_path:
            raise StudentPerformanceSummaryExportError(
                "Student performance summary path is not canonical."
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        QuillanWorkPathError,
        StudentPerformanceSummaryExportError,
    ) as error:
        raise StudentPerformanceSummaryExportError(str(error)) from error

    existed = path.exists()
    if existed and not overwrite:
        raise StudentPerformanceSummaryExportError(
            f"Student performance summary export already exists: {path}. "
            "Use --overwrite to replace it."
        )

    headers, metadata_missing = _standard_headers(snapshot)
    rows = [
        _student_row(
            student,
            snapshot,
            headers,
            metadata_missing,
        )
        for student in snapshot.students
    ]
    fields = (
        BASE_CSV_COLUMNS
        + tuple(headers[standard_id] for standard_id in snapshot.focus_standard_ids)
        + ("notes_flags",)
    )
    _write_csv(path, rows, fields, overwrite)
    return ExportedStudentPerformanceSummary(
        class_id=snapshot.class_id,
        assignment_id=snapshot.assignment_id,
        summary_path=path,
        summary_relative_path=relative_path_for(
            path,
            snapshot.workspace_root,
        ),
        row_count=len(rows),
        reviewed_count=sum(row["review_status"] == "Reviewed" for row in rows),
        returned_without_full_review_count=sum(
            row["review_status"] == "Returned" for row in rows
        ),
        missing_submission_count=_warning_count(snapshot, "missing_submission"),
        missing_review_count=_warning_count(snapshot, "missing_review"),
        invalid_submission_count=_warning_count(snapshot, "invalid_submission"),
        invalid_review_count=_warning_count(snapshot, "invalid_review"),
        identity_mismatch_count=_warning_count(snapshot, "identity_mismatch"),
        created_at=normalized_created_at,
        overwrote_existing=existed,
    )


def _standard_headers(
    snapshot: AssignmentReportingSnapshot,
) -> tuple[dict[str, str], bool]:
    headers: dict[str, str] = {}
    used: set[str] = set()
    metadata_missing = False
    for standard in snapshot.focus_standards:
        header = standard.standard_id
        if standard.metadata_missing:
            metadata_missing = True
        else:
            header = f"{standard.display_code} — {standard.display_name}"
        if header in used:
            header = standard.standard_id
        used.add(header)
        headers[standard.standard_id] = header
    return headers, metadata_missing


def _student_row(
    student: ReportingStudent,
    snapshot: AssignmentReportingSnapshot,
    headers: dict[str, str],
    metadata_missing: bool,
) -> dict[str, str]:
    warnings = list(student.warnings)
    if metadata_missing:
        warnings.append("standard_metadata_missing")
    returned = student.returned_without_full_review is True
    ratings = {
        rating.standard_id: rating
        for rating in student.overall_standard_ratings
    }

    row = {
        "student_id": student.student_id,
        "student_display_name": student.display_name,
        "review_status": _review_status(student),
        "minimum_requirements": _minimum_requirements(student),
    }
    for standard_id in snapshot.focus_standard_ids:
        rating = None if returned else ratings.get(standard_id)
        if rating is None:
            row[headers[standard_id]] = MISSING_RATING
            continue
        if rating.label is None:
            warnings.append("unknown_rating_value")
            row[headers[standard_id]] = str(rating.value)
        else:
            row[headers[standard_id]] = f"{rating.value} - {rating.label}"
    if returned:
        warnings.append("returned_without_full_review")
    row["notes_flags"] = ";".join(dict.fromkeys(warnings))
    return row


def _review_status(student: ReportingStudent) -> str:
    warnings = set(student.warnings)
    if "identity_mismatch" in warnings:
        return "Needs attention"
    if "invalid_submission" in warnings:
        return "Invalid submission"
    if "missing_submission" in warnings:
        return "Not submitted"
    if "invalid_review" in warnings:
        return "Invalid review"
    if not student.review_valid:
        return "Not reviewed"
    if student.returned_without_full_review:
        return "Returned"
    state = student.review_state or ""
    if state in {"ready_for_export", "reviewed", "completed"}:
        return "Reviewed"
    if state in {"in_progress", "reviewing"}:
        return "In progress"
    return "Not reviewed"


def _minimum_requirements(student: ReportingStudent) -> str:
    if not student.review_valid or student.minimum_requirement_status is None:
        return "Not checked"
    if student.returned_without_full_review:
        return "Not met"
    status = student.minimum_requirement_status
    return {
        "met": "Met",
        "not_met": "Not met",
        "not_checked": "Not checked",
    }.get(status, status.replace("_", " ").title())


def _warning_count(snapshot: AssignmentReportingSnapshot, warning: str) -> int:
    return sum(warning in student.warnings for student in snapshot.students)


def _write_csv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...], overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding=REPORT_CSV_ENCODING, newline="", prefix=f".{path.name}.",
            suffix=".tmp", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            file.flush()
            os.fsync(file.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
        temporary = None
    except (OSError, csv.Error) as error:
        raise StudentPerformanceSummaryExportError(
            f"Could not write student performance summary export {path}: {error}"
        ) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StudentPerformanceSummaryExportError("created_at must be timezone-aware.")
    return value.isoformat() if isinstance(value, datetime) else value


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise StudentPerformanceSummaryExportError(str(error)) from error
