"""Comprehensive assignment-local class summary CSV for audit/troubleshooting."""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.assignment_summary_context import (
    LoadedStudentRecord,
    discover_students,
    feedback_status,
    load_assignment,
    load_student_record,
    rating_labels,
    relative_path_for,
    standard_column_keys,
)
from quillan.work_paths import (
    QuillanWorkPathError,
    class_summary_path,
    feedback_markdown_path,
    feedback_pdf_path,
    preflight_work_file_destination,
    quillan_work_ref,
)
from quillan.record_context import canonical_workspace_root

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
        resolved_root = canonical_workspace_root(workspace_root)
        output_path = class_summary_export_path(
            resolved_root, class_id, assignment_id
        )
        assignment = load_assignment(resolved_root, class_id, assignment_id)
        expected_output = preflight_work_file_destination(
            resolved_root,
            quillan_work_ref(class_id, assignment_id),
            Path("exports") / "class_summary.csv",
        )
        if output_path != expected_output:
            raise ClassSummaryExportError("Class summary path is not canonical.")
        focus_standard_ids = list(assignment["focus_standard_ids"])
        column_keys, key_warnings = standard_column_keys(focus_standard_ids)
        labels = rating_labels(assignment)
        students = discover_students(resolved_root, class_id, assignment_id)
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

    fieldnames = _fieldnames(focus_standard_ids, column_keys)
    loaded_records = [
        load_student_record(student, class_id, assignment_id) for student in students
    ]
    rows = [
        _build_student_row(
            resolved_root,
            class_id,
            assignment_id,
            record,
            focus_standard_ids,
            column_keys,
            labels,
            key_warnings,
        )
        for record in loaded_records
    ]
    _write_csv(output_path, rows, fieldnames=fieldnames, overwrite=overwrite)

    return ExportedClassSummary(
        class_id=class_id,
        assignment_id=assignment_id,
        summary_path=output_path,
        summary_relative_path=relative_path_for(output_path, resolved_root),
        row_count=len(rows),
        ready_count=sum(row["review_valid"] == "true" for row in rows),
        missing_review_count=sum("missing_review" in row["warnings"].split(";") for row in rows),
        invalid_review_count=sum("invalid_review" in row["warnings"].split(";") for row in rows),
        missing_submission_count=sum("missing_submission" in row["warnings"].split(";") for row in rows),
        invalid_submission_count=sum("invalid_submission" in row["warnings"].split(";") for row in rows),
        identity_mismatch_count=sum("identity_mismatch" in row["warnings"].split(";") for row in rows),
        returned_without_full_review_count=sum(
            row["returned_without_full_review"] == "true" for row in rows
        ),
        feedback_pdf_present_count=sum(row["feedback_pdf_status"] == "present" for row in rows),
        feedback_pdf_stale_count=sum(row["feedback_pdf_status"] == "stale" for row in rows),
        created_at=normalized_created_at,
        overwrote_existing=overwrote_existing,
    )


def _fieldnames(
    focus_standard_ids: list[str], column_keys: dict[str, str]
) -> tuple[str, ...]:
    dynamic_columns: list[str] = []
    for standard_id in focus_standard_ids:
        key = column_keys[standard_id]
        dynamic_columns.extend(
            (
                f"rating__{key}",
                f"rating_label__{key}",
                f"rating_included_in_feedback__{key}",
                f"rating_missing__{key}",
            )
        )
    return BASE_CSV_COLUMNS[:-1] + tuple(dynamic_columns) + ("warnings",)


def _build_student_row(
    workspace_root: Path,
    class_id: str,
    assignment_id: str,
    loaded: LoadedStudentRecord,
    focus_standard_ids: list[str],
    column_keys: dict[str, str],
    labels: dict[int, str],
    key_warnings: tuple[str, ...],
) -> dict[str, str]:
    student = loaded.student
    review = loaded.review
    warnings = list(loaded.warnings) + list(key_warnings)
    canonical_pdf_path = feedback_pdf_path(
        workspace_root, student.work_ref, student.student_id
    )
    canonical_markdown_path = feedback_markdown_path(
        workspace_root, student.work_ref, student.student_id
    )
    pdf_path, pdf_status, pdf_stale, pdf_warnings = feedback_status(
        workspace_root, review, "feedback_pdf", canonical_pdf_path
    )
    md_path, md_status, md_stale, md_warnings = feedback_status(
        workspace_root, review, "feedback_markdown", canonical_markdown_path
    )
    warnings.extend(pdf_warnings)
    warnings.extend(md_warnings)

    row = {
        "class_id": class_id,
        "assignment_id": assignment_id,
        "student_id": student.student_id,
        "student_display_name": student.display_name,
        "roster_status": student.roster_status,
        "submission_manifest_path": relative_path_for(
            loaded.submission_manifest_path, workspace_root
        ),
        "submission_state": _record_value(loaded.submission, "submission_state"),
        "submission_valid": loaded.submission_valid,
        "review_record_path": relative_path_for(loaded.review_record_path, workspace_root),
        "review_state": _record_value(review, "review_state"),
        "review_valid": loaded.review_valid,
        "minimum_requirement_status": "",
        "returned_without_full_review": "",
        "feedback_pdf_path": pdf_path,
        "feedback_pdf_status": pdf_status,
        "feedback_pdf_stale": pdf_stale,
        "feedback_markdown_path": md_path,
        "feedback_markdown_status": md_status,
        "feedback_markdown_stale": md_stale,
    }

    ratings_by_standard: dict[str, dict[str, Any]] = {}
    if review is not None:
        outcome = review["minimum_requirement_outcome"]
        row["minimum_requirement_status"] = str(outcome["status"])
        row["returned_without_full_review"] = _csv_bool(
            bool(outcome["returned_without_full_review"])
        )
        for rating in review["overall_standard_ratings"]:
            standard_id = rating["standard_id"]
            if standard_id not in focus_standard_ids:
                warnings.append("rating_for_non_assignment_standard")
                continue
            ratings_by_standard[standard_id] = rating

    for standard_id in focus_standard_ids:
        key = column_keys[standard_id]
        rating = ratings_by_standard.get(standard_id)
        if rating is None:
            row[f"rating__{key}"] = ""
            row[f"rating_label__{key}"] = ""
            row[f"rating_included_in_feedback__{key}"] = ""
            row[f"rating_missing__{key}"] = "true"
            continue
        value = int(rating["rating"])
        label = labels.get(value)
        if label is None:
            warnings.append("unknown_rating_value")
            label = ""
        row[f"rating__{key}"] = str(value)
        row[f"rating_label__{key}"] = label
        row[f"rating_included_in_feedback__{key}"] = _csv_bool(
            bool(rating["include_in_feedback"])
        )
        row[f"rating_missing__{key}"] = "false"

    row["warnings"] = ";".join(dict.fromkeys(warnings))
    return row


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


def _record_value(record: dict[str, Any] | None, field: str) -> str:
    if record is None:
        return ""
    return str(record[field])


def _csv_bool(value: bool) -> str:
    return "true" if value else "false"
