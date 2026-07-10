"""Compact teacher-facing student-by-standard performance summary export."""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import find_standard_definition, load_workspace_standards_library

from quillan.assignment_summary_context import (
    LoadedStudentRecord,
    discover_students,
    load_assignment,
    load_student_record,
    rating_labels,
    relative_path_for,
)

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
    return (
        Path(workspace_root)
        / "classes"
        / class_id
        / "assignments"
        / assignment_id
        / "exports"
        / "student_performance_summary.csv"
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
    timestamp = _normalize_timestamp(created_at)
    try:
        root = Path(workspace_root).resolve(strict=False)
        path = student_performance_summary_export_path(root, class_id, assignment_id)
        assignment = load_assignment(root, class_id, assignment_id)
        standard_ids = list(assignment["focus_standard_ids"])
        labels = rating_labels(assignment)
        records = [
            load_student_record(student, class_id, assignment_id)
            for student in discover_students(root, class_id, assignment_id)
        ]
        headers, metadata_missing = _standard_headers(root, standard_ids)
    except (OSError, RuntimeError, ValueError, StudentPerformanceSummaryExportError) as error:
        raise StudentPerformanceSummaryExportError(str(error)) from error

    existed = path.exists()
    if existed and not overwrite:
        raise StudentPerformanceSummaryExportError(
            f"Student performance summary export already exists: {path}. "
            "Use --overwrite to replace it."
        )
    rows = [
        _student_row(record, standard_ids, headers, labels, metadata_missing)
        for record in records
    ]
    _write_csv(path, rows, BASE_CSV_COLUMNS + tuple(headers.values()) + ("notes_flags",), overwrite)
    return ExportedStudentPerformanceSummary(
        class_id=class_id,
        assignment_id=assignment_id,
        summary_path=path,
        summary_relative_path=relative_path_for(path, root),
        row_count=len(rows),
        reviewed_count=sum(row["review_status"] == "Reviewed" for row in rows),
        returned_without_full_review_count=sum(row["review_status"] == "Returned" for row in rows),
        missing_submission_count=_warning_count(records, "missing_submission"),
        missing_review_count=_warning_count(records, "missing_review"),
        invalid_submission_count=_warning_count(records, "invalid_submission"),
        invalid_review_count=_warning_count(records, "invalid_review"),
        identity_mismatch_count=_warning_count(records, "identity_mismatch"),
        created_at=timestamp,
        overwrote_existing=existed,
    )


def _standard_headers(root: Path, standard_ids: list[str]) -> tuple[dict[str, str], set[str]]:
    try:
        library = load_workspace_standards_library(root)
    except OSError:
        library = None
    headers: dict[str, str] = {}
    missing: set[str] = set()
    used: set[str] = set()
    for standard_id in standard_ids:
        definition = None if library is None else find_standard_definition(library, standard_id)
        header = standard_id
        if definition is not None:
            header = f"{definition.code} — {definition.short_name}"
        else:
            missing.add(standard_id)
        if header in used:
            header = standard_id
        used.add(header)
        headers[standard_id] = header
    return headers, missing


def _student_row(
    loaded: LoadedStudentRecord,
    standard_ids: list[str],
    headers: dict[str, str],
    labels: dict[int, str],
    metadata_missing: set[str],
) -> dict[str, str]:
    review = loaded.review
    warnings = list(loaded.warnings)
    if metadata_missing:
        warnings.append("standard_metadata_missing")
    returned = _returned(review)
    ratings: dict[str, dict[str, Any]] = {}
    if review is not None:
        for rating in review["overall_standard_ratings"]:
            standard_id = str(rating["standard_id"])
            if standard_id not in standard_ids:
                warnings.append("rating_for_non_assignment_standard")
            else:
                ratings[standard_id] = rating

    row = {
        "student_id": loaded.student.student_id,
        "student_display_name": loaded.student.display_name,
        "review_status": _review_status(loaded),
        "minimum_requirements": _minimum_requirements(review),
    }
    for standard_id in standard_ids:
        rating = None if returned else ratings.get(standard_id)
        if rating is None:
            row[headers[standard_id]] = MISSING_RATING
            continue
        value = int(rating["rating"])
        label = labels.get(value)
        if label is None:
            warnings.append("unknown_rating_value")
        row[headers[standard_id]] = str(value) if label is None else f"{value} - {label}"
    if returned:
        warnings.append("returned_without_full_review")
    row["notes_flags"] = ";".join(dict.fromkeys(warnings))
    return row


def _review_status(loaded: LoadedStudentRecord) -> str:
    warnings = set(loaded.warnings)
    if "identity_mismatch" in warnings:
        return "Needs attention"
    if "invalid_submission" in warnings:
        return "Invalid submission"
    if "missing_submission" in warnings:
        return "Not submitted"
    if "invalid_review" in warnings:
        return "Invalid review"
    if loaded.review is None:
        return "Not reviewed"
    if _returned(loaded.review):
        return "Returned"
    state = str(loaded.review["review_state"])
    if state in {"ready_for_export", "reviewed", "completed"}:
        return "Reviewed"
    if state in {"in_progress", "reviewing"}:
        return "In progress"
    return "Not reviewed"


def _minimum_requirements(review: dict[str, Any] | None) -> str:
    if review is None:
        return "Not checked"
    outcome = review["minimum_requirement_outcome"]
    if outcome["returned_without_full_review"]:
        return "Not met"
    return {"met": "Met", "not_met": "Not met", "not_checked": "Not checked"}.get(
        str(outcome["status"]), str(outcome["status"]).replace("_", " ").title()
    )


def _returned(review: dict[str, Any] | None) -> bool:
    return review is not None and bool(
        review["minimum_requirement_outcome"]["returned_without_full_review"]
    )


def _warning_count(records: list[LoadedStudentRecord], warning: str) -> int:
    return sum(warning in record.warnings for record in records)


def _write_csv(path: Path, rows: list[dict[str, str]], fields: tuple[str, ...], overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", prefix=f".{path.name}.",
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
