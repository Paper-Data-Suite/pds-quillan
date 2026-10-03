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
class ReportingAssignmentSummary:
    """Assignment-local counts derived from one coherent reporting snapshot."""

    students_expected: int
    students_with_submissions: int
    students_without_submissions: int
    students_with_valid_reviews: int
    students_reviewed: int
    students_in_progress: int
    students_not_reviewed: int
    students_returned_without_full_review: int
    attention_required: int
    feedback_pdf_current: int
    feedback_pdf_stale: int
    feedback_pdf_missing_or_unknown: int
    feedback_markdown_current: int
    feedback_markdown_stale: int
    feedback_markdown_missing_or_unknown: int


@dataclass(frozen=True, slots=True)
class ReportingStandardSummary:
    """One Focus Standard distribution with missing states kept separate."""

    standard_id: str
    rating_counts: tuple[tuple[int, int], ...]
    rated_count: int
    unrated_count: int
    returned_without_full_review_count: int
    excluded_invalid_or_attention_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignmentReportingSnapshot:
    """One read-only projection shared by assignment report renderers."""

    workspace_root: Path
    class_id: str
    assignment_id: str
    assignment_title: str
    writing_type: str
    standards_profile_id: str
    source_assignment_updated_at: str
    focus_standards: tuple[ReportingStandard, ...]
    rating_levels: tuple[ReportingRatingLevel, ...]
    students: tuple[ReportingStudent, ...]
    assignment_summary: ReportingAssignmentSummary
    standard_summaries: tuple[ReportingStandardSummary, ...]
    warnings: tuple[str, ...]
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
        assignment_summary = _assignment_summary(students)
        standard_summaries = tuple(
            _standard_summary(
                standard.standard_id,
                students,
                rating_levels,
            )
            for standard in focus_standards
        )
        warnings = _snapshot_warnings(
            students,
            focus_standards,
            standard_summaries,
            key_warnings,
        )
    except (OSError, RuntimeError, ValueError, QuillanWorkPathError) as error:
        raise AssignmentReportingSnapshotError(str(error)) from error

    return AssignmentReportingSnapshot(
        workspace_root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        assignment_title=str(assignment["title"]),
        writing_type=str(assignment["writing_type"]),
        standards_profile_id=str(assignment["standards_profile_id"]),
        source_assignment_updated_at=str(assignment["updated_at"]),
        focus_standards=focus_standards,
        rating_levels=rating_levels,
        students=students,
        assignment_summary=assignment_summary,
        standard_summaries=standard_summaries,
        warnings=warnings,
        column_key_warnings=key_warnings,
    )



_ATTENTION_WARNINGS = frozenset(
    {
        "invalid_submission",
        "invalid_review",
        "identity_mismatch",
        "unsafe_path",
        "orphan_review",
    }
)
_REVIEWED_STATES = frozenset(
    {
        "ratings_complete",
        "feedback_composed",
        "ready_for_export",
        "exported",
    }
)


def _assignment_summary(
    students: tuple[ReportingStudent, ...],
) -> ReportingAssignmentSummary:
    return ReportingAssignmentSummary(
        students_expected=len(students),
        students_with_submissions=sum(student.submission_valid for student in students),
        students_without_submissions=sum(
            "missing_submission" in student.warnings for student in students
        ),
        students_with_valid_reviews=sum(student.review_valid for student in students),
        students_reviewed=sum(
            student.review_valid
            and student.returned_without_full_review is not True
            and student.review_state in _REVIEWED_STATES
            for student in students
        ),
        students_in_progress=sum(_is_review_in_progress(student) for student in students),
        students_not_reviewed=sum(_is_not_reviewed(student) for student in students),
        students_returned_without_full_review=sum(
            student.returned_without_full_review is True for student in students
        ),
        attention_required=sum(_requires_attention(student) for student in students),
        feedback_pdf_current=sum(
            student.feedback_pdf.status == "present" for student in students
        ),
        feedback_pdf_stale=sum(
            student.feedback_pdf.status == "stale" for student in students
        ),
        feedback_pdf_missing_or_unknown=sum(
            student.feedback_pdf.status not in {"present", "stale"}
            for student in students
        ),
        feedback_markdown_current=sum(
            student.feedback_markdown.status == "present" for student in students
        ),
        feedback_markdown_stale=sum(
            student.feedback_markdown.status == "stale" for student in students
        ),
        feedback_markdown_missing_or_unknown=sum(
            student.feedback_markdown.status not in {"present", "stale"}
            for student in students
        ),
    )


def _standard_summary(
    standard_id: str,
    students: tuple[ReportingStudent, ...],
    rating_levels: tuple[ReportingRatingLevel, ...],
) -> ReportingStandardSummary:
    counts = {level.value: 0 for level in rating_levels}
    rated = 0
    unrated = 0
    returned = 0
    excluded = 0
    warnings: list[str] = []

    for student in students:
        if student.returned_without_full_review is True:
            returned += 1
            continue
        if _requires_attention(student):
            excluded += 1
            continue
        rating = next(
            (
                item
                for item in student.overall_standard_ratings
                if item.standard_id == standard_id
            ),
            None,
        )
        if rating is None:
            unrated += 1
            continue
        rated += 1
        if rating.value not in counts:
            warnings.append("unknown_rating_value")
            counts[rating.value] = 0
        counts[rating.value] += 1

    return ReportingStandardSummary(
        standard_id=standard_id,
        rating_counts=tuple(counts.items()),
        rated_count=rated,
        unrated_count=unrated,
        returned_without_full_review_count=returned,
        excluded_invalid_or_attention_count=excluded,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _snapshot_warnings(
    students: tuple[ReportingStudent, ...],
    standards: tuple[ReportingStandard, ...],
    standard_summaries: tuple[ReportingStandardSummary, ...],
    key_warnings: tuple[str, ...],
) -> tuple[str, ...]:
    warnings: list[str] = list(key_warnings)
    if any(standard.metadata_missing for standard in standards):
        warnings.append("standard_metadata_missing")
    for student in students:
        warnings.extend(student.warnings)
        warnings.extend(student.feedback_pdf.warnings)
        warnings.extend(student.feedback_markdown.warnings)
    for summary in standard_summaries:
        warnings.extend(summary.warnings)
    return tuple(dict.fromkeys(warnings))


def _requires_attention(student: ReportingStudent) -> bool:
    return bool(_ATTENTION_WARNINGS.intersection(student.warnings))


def _is_review_in_progress(student: ReportingStudent) -> bool:
    if not student.review_valid or student.returned_without_full_review is True:
        return False
    state = student.review_state or "not_started"
    return state not in _REVIEWED_STATES and state != "not_started"


def _is_not_reviewed(student: ReportingStudent) -> bool:
    if _requires_attention(student) or student.returned_without_full_review is True:
        return False
    if not student.review_valid:
        return True
    return (student.review_state or "not_started") == "not_started"



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
