"""Teacher-facing assignment-local Focus Standard summary CSV export."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier
from pds_core.standards import (
    StandardsLibrary,
    find_standard_definition,
    load_workspace_standards_library,
)

from quillan.assignment_summary_context import (
    LoadedStudentRecord,
    discover_students,
    feedback_status,
    load_assignment,
    load_student_record,
    rating_values,
    relative_path_for,
    standard_column_keys,
)
from quillan.work_paths import quillan_work_paths

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
    return quillan_work_paths(
        workspace_root, class_id, assignment_id
    ).exports_dir / "standards_summary.csv"


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
        resolved_root = Path(workspace_root).resolve(strict=False)
        output_path = standards_summary_export_path(
            resolved_root, class_id, assignment_id
        )
        assignment = load_assignment(resolved_root, class_id, assignment_id)
        focus_standard_ids = list(assignment["focus_standard_ids"])
        column_keys, key_warnings = standard_column_keys(focus_standard_ids)
        values = rating_values(assignment)
        students = discover_students(resolved_root, class_id, assignment_id)
    except (OSError, RuntimeError, ValueError, StandardsSummaryExportError) as error:
        raise StandardsSummaryExportError(str(error)) from error

    overwrote_existing = output_path.exists()
    if overwrote_existing and not overwrite:
        raise StandardsSummaryExportError(
            f"Standards summary export already exists: {output_path}. "
            "Use --overwrite to replace it."
        )

    loaded_records = [
        load_student_record(student, class_id, assignment_id) for student in students
    ]
    standards_library = _load_standards_library(resolved_root)
    rows = [
        _build_row(
            resolved_root,
            class_id,
            assignment_id,
            assignment,
            standard_id,
            index,
            column_keys[standard_id],
            values,
            loaded_records,
            standards_library,
            key_warnings,
        )
        for index, standard_id in enumerate(focus_standard_ids, start=1)
    ]
    _write_csv(output_path, rows, overwrite=overwrite)

    warning_counts = _warning_counts(loaded_records)
    return ExportedStandardsSummary(
        class_id=class_id,
        assignment_id=assignment_id,
        summary_path=output_path,
        summary_relative_path=relative_path_for(output_path, resolved_root),
        row_count=len(rows),
        standard_count=len(rows),
        student_count=len(students),
        review_count=sum(record.review is not None for record in loaded_records),
        missing_review_count=warning_counts["missing_review"],
        invalid_review_count=warning_counts["invalid_review"],
        missing_submission_count=warning_counts["missing_submission"],
        invalid_submission_count=warning_counts["invalid_submission"],
        identity_mismatch_count=warning_counts["identity_mismatch"],
        returned_without_full_review_count=sum(
            _returned_without_full_review(record.review)
            for record in loaded_records
        ),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _build_row(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    assignment: dict[str, Any],
    standard_id: str,
    focus_order: int,
    standard_column_key: str,
    rating_scale_values: tuple[int, ...],
    records: list[LoadedStudentRecord],
    standards_library: StandardsLibrary,
    key_warnings: tuple[str, ...],
) -> dict[str, str]:
    warnings = list(key_warnings)
    definition = find_standard_definition(standards_library, standard_id)
    if definition is None:
        warnings.append("standard_metadata_missing")

    rating_counts = {str(value): 0 for value in rating_scale_values}
    students_with_submissions = 0
    students_with_valid_reviews = 0
    students_reviewed_for_standard = 0
    students_returned = 0
    students_missing_rating = 0
    students_included = 0
    feedback_pdf_present = 0
    feedback_pdf_stale = 0

    for record in records:
        if record.submission is not None:
            students_with_submissions += 1
        review = record.review
        if review is None:
            continue
        students_with_valid_reviews += 1
        pdf_path = record.student.student_dir / "exports" / "feedback.pdf"
        _, pdf_status, _, _ = feedback_status(
            workspace_root, review, "feedback_pdf", pdf_path
        )
        if pdf_status == "present":
            feedback_pdf_present += 1
        elif pdf_status == "stale":
            feedback_pdf_stale += 1

        if _returned_without_full_review(review):
            students_returned += 1
            continue

        ratings_by_standard = {
            rating["standard_id"]: rating
            for rating in review["overall_standard_ratings"]
        }
        extra_ratings = set(ratings_by_standard) - set(assignment["focus_standard_ids"])
        if extra_ratings:
            warnings.append("rating_for_non_assignment_standard")

        rating = ratings_by_standard.get(standard_id)
        if rating is None:
            students_missing_rating += 1
            continue
        students_reviewed_for_standard += 1
        value = str(rating["rating"])
        if value not in rating_counts:
            warnings.append("unknown_rating_value")
            rating_counts[value] = 0
        rating_counts[value] += 1
        if rating["include_in_feedback"]:
            students_included += 1

    return {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "standards_profile_id": str(assignment["standards_profile_id"]),
        "focus_standard_order": str(focus_order),
        "standard_id": standard_id,
        "standard_column_key": standard_column_key,
        "standard_display_code": definition.code if definition is not None else "",
        "standard_display_name": definition.short_name if definition is not None else "",
        "students_expected": str(len(records)),
        "students_with_submissions": str(students_with_submissions),
        "students_with_valid_reviews": str(students_with_valid_reviews),
        "students_reviewed_for_standard": str(students_reviewed_for_standard),
        "students_returned_without_full_review": str(students_returned),
        "students_missing_rating": str(students_missing_rating),
        "students_with_rating_included_in_feedback": str(students_included),
        "feedback_pdf_present_count": str(feedback_pdf_present),
        "feedback_pdf_stale_count": str(feedback_pdf_stale),
        "rating_counts_json": json.dumps(rating_counts, sort_keys=True, separators=(",", ":")),
        "warnings": ";".join(dict.fromkeys(warnings)),
    }


def _warning_counts(records: list[LoadedStudentRecord]) -> dict[str, int]:
    return {
        warning: sum(warning in record.warnings for record in records)
        for warning in (
            "missing_review",
            "invalid_review",
            "missing_submission",
            "invalid_submission",
            "identity_mismatch",
        )
    }


def _returned_without_full_review(review: dict[str, Any] | None) -> bool:
    if review is None:
        return False
    return bool(review["minimum_requirement_outcome"]["returned_without_full_review"])


def _load_standards_library(workspace_root: Path) -> StandardsLibrary:
    try:
        return load_workspace_standards_library(workspace_root)
    except OSError:
        return StandardsLibrary(standards=(), profiles=())


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
