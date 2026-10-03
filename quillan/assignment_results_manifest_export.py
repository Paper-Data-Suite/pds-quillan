"""Machine-readable assignment-local reporting handoff for Quillan."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pds_core.identifiers import IdentifierValidationError, validate_identifier

from quillan.assignment_reporting_snapshot import (
    AssignmentReportingSnapshot,
    AssignmentReportingSnapshotError,
    ReportingStandardSummary,
    ReportingStudent,
    build_assignment_reporting_snapshot,
)
from quillan.assignment_summary_context import relative_path_for
from quillan.work_paths import (
    QuillanWorkPathError,
    assignment_results_manifest_path,
    assignment_review_report_path,
    class_summary_path,
    preflight_work_file_destination,
    quillan_work_ref,
    standards_summary_path,
    student_performance_summary_path,
)

SCHEMA_VERSION = "1"
RECORD_TYPE = "assignment_results_manifest"


class AssignmentResultsManifestExportError(Exception):
    """Raised when the assignment results manifest cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class ExportedAssignmentResultsManifest:
    """Information about one generated assignment results manifest."""

    class_id: str
    assignment_id: str
    manifest_path: Path
    manifest_relative_path: str
    student_count: int
    standard_count: int
    warning_count: int
    generated_at: str
    overwrote_existing: bool


def assignment_results_manifest_export_path(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> Path:
    """Return the canonical assignment-local results-manifest path."""
    _validate_identifier(class_id, "class_id")
    _validate_identifier(assignment_id, "assignment_id")
    return assignment_results_manifest_path(
        workspace_root,
        quillan_work_ref(class_id, assignment_id),
    )


def export_assignment_results_manifest(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    *,
    overwrite: bool = False,
    generated_at: datetime | str | None = None,
) -> ExportedAssignmentResultsManifest:
    """Build one reporting snapshot and export its machine-readable handoff."""
    normalized_generated_at = _normalize_timestamp(generated_at)
    try:
        snapshot = build_assignment_reporting_snapshot(
            workspace_root,
            class_id,
            assignment_id,
        )
    except AssignmentReportingSnapshotError as error:
        raise AssignmentResultsManifestExportError(str(error)) from error
    return _export_assignment_results_manifest_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_generated_at=normalized_generated_at,
    )


def export_assignment_results_manifest_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool = False,
    generated_at: datetime | str | None = None,
) -> ExportedAssignmentResultsManifest:
    """Render JSON from an already-loaded reporting snapshot."""
    return _export_assignment_results_manifest_from_snapshot(
        snapshot,
        overwrite=overwrite,
        normalized_generated_at=_normalize_timestamp(generated_at),
    )


def _export_assignment_results_manifest_from_snapshot(
    snapshot: AssignmentReportingSnapshot,
    *,
    overwrite: bool,
    normalized_generated_at: str,
) -> ExportedAssignmentResultsManifest:
    try:
        path = assignment_results_manifest_export_path(
            snapshot.workspace_root,
            snapshot.class_id,
            snapshot.assignment_id,
        )
        expected = preflight_work_file_destination(
            snapshot.workspace_root,
            quillan_work_ref(snapshot.class_id, snapshot.assignment_id),
            Path("exports") / "assignment_results_manifest.json",
        )
        if path != expected:
            raise AssignmentResultsManifestExportError(
                "Assignment results manifest path is not canonical."
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        QuillanWorkPathError,
        AssignmentResultsManifestExportError,
    ) as error:
        raise AssignmentResultsManifestExportError(str(error)) from error

    existed = path.exists()
    if existed and not overwrite:
        raise AssignmentResultsManifestExportError(
            f"Assignment results manifest already exists: {path}. "
            "Use --overwrite to replace it."
        )

    payload = _manifest_payload(snapshot, normalized_generated_at)
    _write_json(path, payload, overwrite=overwrite)
    return ExportedAssignmentResultsManifest(
        class_id=snapshot.class_id,
        assignment_id=snapshot.assignment_id,
        manifest_path=path,
        manifest_relative_path=relative_path_for(path, snapshot.workspace_root),
        student_count=len(snapshot.students),
        standard_count=len(snapshot.focus_standards),
        warning_count=len(payload["warnings"]),
        generated_at=normalized_generated_at,
        overwrote_existing=existed,
    )


def _manifest_payload(
    snapshot: AssignmentReportingSnapshot,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "module": "quillan",
        "record_type": RECORD_TYPE,
        "generated_at": generated_at,
        "class": {
            "class_id": snapshot.class_id,
        },
        "assignment": {
            "assignment_id": snapshot.assignment_id,
            "title": snapshot.assignment_title,
            "writing_type": snapshot.writing_type,
            "standards_profile_id": snapshot.standards_profile_id,
            "source_updated_at": snapshot.source_assignment_updated_at,
        },
        "rating_scale": [
            {"value": level.value, "label": level.label}
            for level in snapshot.rating_levels
        ],
        "focus_standards": [
            {
                "standard_id": standard.standard_id,
                "order": standard.order,
                "column_key": standard.column_key,
                "display_code": standard.display_code,
                "display_name": standard.display_name,
                "metadata_missing": standard.metadata_missing,
            }
            for standard in snapshot.focus_standards
        ],
        "assignment_summary": {
            "students_expected": snapshot.assignment_summary.students_expected,
            "rostered_students": snapshot.assignment_summary.rostered_students,
            "unrostered_submissions": (
                snapshot.assignment_summary.unrostered_submissions
            ),
            "students_with_submissions": (
                snapshot.assignment_summary.students_with_submissions
            ),
            "students_without_submissions": (
                snapshot.assignment_summary.students_without_submissions
            ),
            "students_with_valid_reviews": (
                snapshot.assignment_summary.students_with_valid_reviews
            ),
            "students_reviewed": snapshot.assignment_summary.students_reviewed,
            "students_in_progress": snapshot.assignment_summary.students_in_progress,
            "students_not_reviewed": snapshot.assignment_summary.students_not_reviewed,
            "students_returned_without_full_review": (
                snapshot.assignment_summary.students_returned_without_full_review
            ),
            "attention_required": snapshot.assignment_summary.attention_required,
            "feedback_pdf": {
                "current": snapshot.assignment_summary.feedback_pdf_current,
                "stale": snapshot.assignment_summary.feedback_pdf_stale,
                "missing_or_unknown": (
                    snapshot.assignment_summary.feedback_pdf_missing_or_unknown
                ),
            },
            "feedback_markdown": {
                "current": snapshot.assignment_summary.feedback_markdown_current,
                "stale": snapshot.assignment_summary.feedback_markdown_stale,
                "missing_or_unknown": (
                    snapshot.assignment_summary.feedback_markdown_missing_or_unknown
                ),
            },
        },
        "standard_summaries": [
            _standard_summary_payload(snapshot, summary)
            for summary in snapshot.standard_summaries
        ],
        "students": [_student_payload(student) for student in snapshot.students],
        "warnings": list(snapshot.warnings),
        "generated_artifacts": _artifact_inventory(snapshot),
        "module_details": {},
    }


def _standard_summary_payload(
    snapshot: AssignmentReportingSnapshot,
    summary: ReportingStandardSummary,
) -> dict[str, Any]:
    standard = next(
        item
        for item in snapshot.focus_standards
        if item.standard_id == summary.standard_id
    )
    labels = {level.value: level.label for level in snapshot.rating_levels}
    distribution: list[dict[str, Any]] = []
    for value, count in summary.rating_counts:
        distribution.append(
            {
                "value": value,
                "label": labels.get(value),
                "count": count,
                "percent_of_rated": (
                    None
                    if summary.rated_count == 0
                    else round((count / summary.rated_count) * 100.0, 1)
                ),
                "denominator": "rated_students",
                "denominator_count": summary.rated_count,
            }
        )
    return {
        "standard_id": summary.standard_id,
        "order": standard.order,
        "display_code": standard.display_code,
        "display_name": standard.display_name,
        "rating_distribution": distribution,
        "rated_count": summary.rated_count,
        "unrated_count": summary.unrated_count,
        "returned_without_full_review_count": (
            summary.returned_without_full_review_count
        ),
        "excluded_invalid_or_attention_count": (
            summary.excluded_invalid_or_attention_count
        ),
        "warnings": list(summary.warnings),
    }


def _student_payload(student: ReportingStudent) -> dict[str, Any]:
    return {
        "student_id": student.student_id,
        "student_display_name": student.display_name,
        "roster_status": student.roster_status,
        "submission_manifest_path": (
            None
            if "missing_submission" in student.warnings
            else student.submission_manifest_path
        ),
        "submission_state": student.submission_state,
        "submission_valid": student.submission_valid,
        "review_record_path": (
            None
            if "missing_review" in student.warnings
            else student.review_record_path
        ),
        "review_state": student.review_state,
        "review_valid": student.review_valid,
        "minimum_requirement_status": student.minimum_requirement_status,
        "returned_without_full_review": student.returned_without_full_review,
        "overall_standard_ratings": [
            {
                "standard_id": rating.standard_id,
                "rating": rating.value,
                "rating_label": rating.label,
                "include_in_feedback": rating.include_in_feedback,
            }
            for rating in student.overall_standard_ratings
        ],
        "feedback_exports": {
            "feedback_pdf": {
                "path": (
                    None
                    if student.feedback_pdf.status == "missing"
                    else student.feedback_pdf.path
                ),
                "status": student.feedback_pdf.status,
                "stale": _json_stale(student.feedback_pdf.stale),
            },
            "feedback_markdown": {
                "path": (
                    None
                    if student.feedback_markdown.status == "missing"
                    else student.feedback_markdown.path
                ),
                "status": student.feedback_markdown.status,
                "stale": _json_stale(student.feedback_markdown.stale),
            },
        },
        "warnings": list(
            dict.fromkeys(
                (
                    *student.warnings,
                    *student.feedback_pdf.warnings,
                    *student.feedback_markdown.warnings,
                )
            )
        ),
        "module_details": {},
    }


def _json_stale(value: str) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _artifact_inventory(
    snapshot: AssignmentReportingSnapshot,
) -> list[dict[str, Any]]:
    work_ref = quillan_work_ref(snapshot.class_id, snapshot.assignment_id)
    artifacts = (
        (
            "student_performance_summary_csv",
            student_performance_summary_path(snapshot.workspace_root, work_ref),
            "csv",
            False,
        ),
        (
            "class_summary_csv",
            class_summary_path(snapshot.workspace_root, work_ref),
            "csv",
            False,
        ),
        (
            "standards_summary_csv",
            standards_summary_path(snapshot.workspace_root, work_ref),
            "csv",
            False,
        ),
        (
            "assignment_review_report_pdf",
            assignment_review_report_path(snapshot.workspace_root, work_ref),
            "pdf",
            False,
        ),
        (
            "assignment_results_manifest_json",
            assignment_results_manifest_path(snapshot.workspace_root, work_ref),
            "json",
            True,
        ),
    )
    return [
        {
            "artifact": name,
            "path": relative_path_for(path, snapshot.workspace_root),
            "format": format_name,
            "status": (
                "generated"
                if generated_now
                else ("present" if path.is_file() else "missing")
            ),
        }
        for name, path, format_name, generated_now in artifacts
    ]


def _write_json(path: Path, payload: dict[str, Any], *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
        temporary = None
    except FileExistsError as error:
        raise AssignmentResultsManifestExportError(
            f"Assignment results manifest already exists: {path}. "
            "Use --overwrite to replace it."
        ) from error
    except (OSError, TypeError, ValueError) as error:
        raise AssignmentResultsManifestExportError(
            f"Could not write assignment results manifest {path}: {error}"
        ) from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _normalize_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise AssignmentResultsManifestExportError(
                "generated_at datetime must be timezone-aware."
            )
        return value.isoformat()
    if not isinstance(value, str):
        raise AssignmentResultsManifestExportError(
            "generated_at must be a timezone-aware datetime or ISO 8601 string."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise AssignmentResultsManifestExportError(
            "generated_at must be a timezone-aware ISO 8601 string."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssignmentResultsManifestExportError(
            "generated_at must be a timezone-aware ISO 8601 string."
        )
    return value


def _validate_identifier(value: str, field: str) -> None:
    try:
        validate_identifier(value, field)
    except IdentifierValidationError as error:
        raise AssignmentResultsManifestExportError(str(error)) from error
