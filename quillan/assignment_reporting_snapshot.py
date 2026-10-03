"""Immutable assignment-local reporting projection for Quillan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    relative_path_for,
    standard_column_keys,
)
from quillan.record_context import canonical_workspace_root
from quillan.submission_evidence_validation import selected_evidence_fingerprint
from quillan.work_paths import (
    QuillanWorkPathError,
    feedback_markdown_path,
    feedback_pdf_path,
)


class AssignmentReportingSnapshotError(Exception):
    """Raised when an assignment reporting snapshot cannot be built safely."""


@dataclass(frozen=True, slots=True)
class ReportingRatingLevel:
    """One assignment-defined rating level."""

    value: int
    label: str


@dataclass(frozen=True, slots=True)
class ReportingStandard:
    """One assignment Focus Standard and its display metadata."""

    standard_id: str
    order: int
    column_key: str
    display_code: str
    display_name: str
    metadata_missing: bool


@dataclass(frozen=True, slots=True)
class ReportingStandardRating:
    """One teacher-entered overall Focus Standard rating."""

    standard_id: str
    value: int
    label: str | None
    include_in_feedback: bool


@dataclass(frozen=True, slots=True)
class ReportingFeedbackExport:
    """Derived status for one student feedback export."""

    path: str
    status: str
    stale: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportingStudent:
    """Reportable assignment-local state for one roster/discovered student."""

    student_id: str
    display_name: str
    roster_status: str
    submission_manifest_path: str
    submission_state: str | None
    submission_valid: bool
    review_record_path: str
    review_state: str | None
    review_valid: bool
    minimum_requirement_status: str | None
    returned_without_full_review: bool | None
    overall_standard_ratings: tuple[ReportingStandardRating, ...]
    feedback_pdf: ReportingFeedbackExport
    feedback_markdown: ReportingFeedbackExport
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignmentReportingSnapshot:
    """One read-only projection shared by assignment report renderers."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    assignment_title: str
    standards_profile_id: str
    source_assignment_updated_at: str
    focus_standards: tuple[ReportingStandard, ...]
    rating_levels: tuple[ReportingRatingLevel, ...]
    students: tuple[ReportingStudent, ...]
    column_key_warnings: tuple[str, ...]

    @property
    def focus_standard_ids(self) -> tuple[str, ...]:
        """Return Focus Standard IDs in assignment order."""
        return tuple(standard.standard_id for standard in self.focus_standards)

    @property
    def rating_values(self) -> tuple[int, ...]:
        """Return assignment rating values in configured order."""
        return tuple(level.value for level in self.rating_levels)


def build_assignment_reporting_snapshot(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentReportingSnapshot:
    """Load canonical assignment-local reporting state exactly once."""
    try:
        root = canonical_workspace_root(workspace_root)
        assignment = load_assignment(root, class_id, assignment_id)
        focus_standard_ids = tuple(
            str(standard_id) for standard_id in assignment["focus_standard_ids"]
        )
        column_keys, key_warnings = standard_column_keys(list(focus_standard_ids))
        rating_levels = tuple(
            ReportingRatingLevel(
                value=int(level["value"]),
                label=str(level["label"]),
            )
            for level in assignment["rating_scale"]["levels"]
        )
        rating_labels = {level.value: level.label for level in rating_levels}
        standards_library = _load_standards_library(root)
        focus_standards = tuple(
            _reporting_standard(
                standards_library,
                standard_id,
                order,
                column_keys[standard_id],
            )
            for order, standard_id in enumerate(focus_standard_ids, start=1)
        )
        loaded_records = tuple(
            load_student_record(student, class_id, assignment_id)
            for student in discover_students(root, class_id, assignment_id)
        )
        students = tuple(
            _reporting_student(
                root,
                record,
                focus_standard_ids,
                rating_labels,
            )
            for record in loaded_records
        )
    except (OSError, RuntimeError, ValueError, QuillanWorkPathError) as error:
        raise AssignmentReportingSnapshotError(str(error)) from error

    return AssignmentReportingSnapshot(
        workspace_root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        assignment_title=str(assignment["title"]),
        standards_profile_id=str(assignment["standards_profile_id"]),
        source_assignment_updated_at=str(assignment["updated_at"]),
        focus_standards=focus_standards,
        rating_levels=rating_levels,
        students=students,
        column_key_warnings=key_warnings,
    )


def _load_standards_library(
    workspace_root: Path,
) -> StandardsLibrary | None:
    try:
        return load_workspace_standards_library(workspace_root)
    except OSError:
        return None


def _reporting_standard(
    standards_library: StandardsLibrary | None,
    standard_id: str,
    order: int,
    column_key: str,
) -> ReportingStandard:
    definition = (
        None
        if standards_library is None
        else find_standard_definition(standards_library, standard_id)
    )
    return ReportingStandard(
        standard_id=standard_id,
        order=order,
        column_key=column_key,
        display_code="" if definition is None else definition.code,
        display_name="" if definition is None else definition.short_name,
        metadata_missing=definition is None,
    )


def _reporting_student(
    workspace_root: Path,
    loaded: LoadedStudentRecord,
    focus_standard_ids: tuple[str, ...],
    rating_labels: dict[int, str],
) -> ReportingStudent:
    student = loaded.student
    submission = loaded.submission
    review = loaded.review
    selected_fingerprint = (
        None if submission is None else selected_evidence_fingerprint(submission)
    )

    pdf = _feedback_export(
        workspace_root,
        loaded,
        "feedback_pdf",
        feedback_pdf_path(
            workspace_root,
            student.work_ref,
            student.student_id,
        ),
        selected_fingerprint,
    )
    markdown = _feedback_export(
        workspace_root,
        loaded,
        "feedback_markdown",
        feedback_markdown_path(
            workspace_root,
            student.work_ref,
            student.student_id,
        ),
        selected_fingerprint,
    )

    warnings = list(loaded.warnings)
    ratings: list[ReportingStandardRating] = []
    minimum_requirement_status: str | None = None
    returned_without_full_review: bool | None = None
    review_state: str | None = None

    if review is not None:
        review_state = str(review["review_state"])
        outcome = review["minimum_requirement_outcome"]
        minimum_requirement_status = str(outcome["status"])
        returned_without_full_review = bool(
            outcome["returned_without_full_review"]
        )
        for rating in review["overall_standard_ratings"]:
            standard_id = str(rating["standard_id"])
            value = int(rating["rating"])
            ratings.append(
                ReportingStandardRating(
                    standard_id=standard_id,
                    value=value,
                    label=rating_labels.get(value),
                    include_in_feedback=bool(rating["include_in_feedback"]),
                )
            )
            if standard_id not in focus_standard_ids:
                warnings.append("rating_for_non_assignment_standard")

    return ReportingStudent(
        student_id=student.student_id,
        display_name=student.display_name,
        roster_status=student.roster_status,
        submission_manifest_path=relative_path_for(
            loaded.submission_manifest_path,
            workspace_root,
        ),
        submission_state=(
            None if submission is None else str(submission["submission_state"])
        ),
        submission_valid=loaded.submission_valid == "true",
        review_record_path=relative_path_for(
            loaded.review_record_path,
            workspace_root,
        ),
        review_state=review_state,
        review_valid=loaded.review_valid == "true",
        minimum_requirement_status=minimum_requirement_status,
        returned_without_full_review=returned_without_full_review,
        overall_standard_ratings=tuple(ratings),
        feedback_pdf=pdf,
        feedback_markdown=markdown,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _feedback_export(
    workspace_root: Path,
    loaded: LoadedStudentRecord,
    field: str,
    default_path: Path,
    selected_fingerprint: str | None,
) -> ReportingFeedbackExport:
    path, status, stale, warnings = feedback_status(
        workspace_root,
        loaded.review,
        field,
        default_path,
        selected_evidence_fingerprint=selected_fingerprint,
    )
    return ReportingFeedbackExport(
        path=path,
        status=status,
        stale=stale,
        warnings=warnings,
    )
