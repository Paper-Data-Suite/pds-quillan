"""Immutable, read-only assignment review dashboard composition."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from pds_core.classes import load_class_roster
from pds_core.identifiers import validate_identifier
from pds_core.rosters import RosterError, student_display_name

from quillan.assignment_submission_assembly import (
    discover_assignment_routed_evidence_status,
)
from quillan.assignment_summary_context import feedback_status, relative_path_for
from quillan.assignments import AssignmentConfigError, load_assignment_config
from quillan.feedback_export import feedback_export_path, feedback_pdf_export_path
from quillan.plain_paper_submission import is_plain_paper_submission
from quillan.review_record import ReviewRecordError, load_review_record
from quillan.review_status_display import review_progress_status
from quillan.scan_review_resolution import (
    ScanReviewResolutionError,
    discover_scan_review_items,
)
from quillan.submission_manifest import (
    SubmissionManifestError,
    load_submission_manifest,
)

DASHBOARD_SCHEMA_VERSION: Final = "1"
DASHBOARD_RECORD_TYPE: Final = "quillan_assignment_review_dashboard"
SUBMISSION_STATES: Final = ("unreviewed", "in_progress", "needs_rescan", "reviewed")
PAGE_STATES: Final = ("present", "missing", "duplicate", "needs_rescan", "excluded")
REVIEW_STATES: Final = (
    "not_started",
    "requirements_checked",
    "returned_without_full_review",
    "observations_in_progress",
    "observations_complete",
    "ratings_complete",
    "feedback_composed",
    "ready_for_export",
    "exported",
)
MINIMUM_REQUIREMENT_STATES: Final = (
    "not_checked",
    "met",
    "unmet_continue_review",
    "returned_without_full_review",
)
EXPORT_STATES: Final = ("present", "stale", "missing", "unknown")


class ReviewDashboardError(ValueError):
    """Raised when an assignment dashboard cannot be built safely."""


@dataclass(frozen=True, slots=True)
class DashboardWarning:
    code: str
    message: str
    path: str | None = None
    student_id: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardStudentStatus:
    student_id: str
    display_name: str
    roster_status: str
    routed_evidence_present: bool
    needs_assembly: bool
    submission_status: str
    submission_path: str
    submission_state: str | None
    plain_paper: bool
    evidence_file_count: int
    page_counts: tuple[tuple[str, int], ...]
    review_status: str
    review_path: str
    review_state: str | None
    minimum_requirement_status: str | None
    returned_without_full_review: bool
    feedback_pdf_status: str
    feedback_markdown_status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DashboardScanReviewItem:
    failure_id: str
    status: str
    failure_category: str
    failure_message: str
    source_filename: str
    source_page_number: int | None
    student_id: str | None
    failure_metadata_path: str
    retained_source_path: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class AssignmentReviewDashboard:
    class_id: str
    assignment_id: str
    assignment_title: str
    writing_type: str
    standards_profile_id: str
    focus_standard_count: int
    assignment_path: str
    roster_available: bool
    rostered_count: int | None
    students: tuple[DashboardStudentStatus, ...]
    submission_counts: tuple[tuple[str, int], ...]
    submission_state_counts: tuple[tuple[str, int], ...]
    page_counts: tuple[tuple[str, int], ...]
    page_student_counts: tuple[tuple[str, int], ...]
    routed_counts: tuple[tuple[str, int], ...]
    review_counts: tuple[tuple[str, int], ...]
    review_state_counts: tuple[tuple[str, int], ...]
    minimum_requirement_counts: tuple[tuple[str, int], ...]
    workflow_counts: tuple[tuple[str, int], ...]
    feedback_pdf_counts: tuple[tuple[str, int], ...]
    feedback_markdown_counts: tuple[tuple[str, int], ...]
    scan_review_available: bool
    scan_review_counts: tuple[tuple[str, int], ...]
    scan_review_categories: tuple[tuple[str, int], ...]
    unassembled_routed_files: tuple[str, ...]
    unused_duplicate_routed_files: tuple[str, ...]
    skipped_routed_files: tuple[tuple[str, str], ...]
    scan_review_items: tuple[DashboardScanReviewItem, ...]
    warnings: tuple[DashboardWarning, ...]


def build_assignment_review_dashboard(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentReviewDashboard:
    """Build a deterministic dashboard using only existing workspace records."""
    try:
        validate_identifier(class_id, "class_id")
        validate_identifier(assignment_id, "assignment_id")
    except ValueError as error:
        raise ReviewDashboardError(str(error)) from error
    root = Path(workspace_root).resolve(strict=False)
    assignment_path = (
        root / "classes" / class_id / "assignments" / assignment_id / "assignment.json"
    )
    try:
        assignment = load_assignment_config(assignment_path)
    except (OSError, AssignmentConfigError) as error:
        raise ReviewDashboardError(f"Could not load assignment: {error}") from error
    if assignment["assignment_id"] != assignment_id:
        raise ReviewDashboardError(
            f"Assignment identity mismatch: expected {assignment_id!r}, "
            f"found {assignment['assignment_id']!r}."
        )
    if class_id not in assignment["class_ids"]:
        raise ReviewDashboardError(
            f"Assignment {assignment_id!r} is not configured for class {class_id!r}."
        )

    warnings: list[DashboardWarning] = []
    roster_students: tuple[Any, ...] | None
    try:
        roster_students = load_class_roster(root, class_id).students
    except (OSError, RosterError) as error:
        roster_students = None
        warnings.append(DashboardWarning("roster_unavailable", str(error)))

    submissions_dir = assignment_path.parent / "submissions"
    submission_ids = _directory_ids(submissions_dir)
    try:
        routed = discover_assignment_routed_evidence_status(
            root, class_id, assignment_id
        )
    except (OSError, ValueError) as error:
        raise ReviewDashboardError(
            f"Could not discover routed evidence: {error}"
        ) from error
    routed_ids = set(routed.evidence_by_student)
    ordered_ids, display_names, roster_ids = _student_population(
        roster_students, submission_ids, routed_ids
    )

    students: list[DashboardStudentStatus] = []
    valid_manifests: dict[str, dict[str, Any]] = {}
    assembled_paths: set[Path] = set()
    submission_files_present = 0
    review_files_present = 0
    orphaned_reviews = 0
    for student_id in ordered_ids:
        student_dir = submissions_dir / student_id
        manifest_path = student_dir / "submission.json"
        review_path = student_dir / "review.json"
        manifest_relative = relative_path_for(manifest_path, root)
        review_relative = relative_path_for(review_path, root)
        student_warnings: list[str] = []
        manifest: dict[str, Any] | None = None
        submission_status = "missing"
        if manifest_path.is_file():
            submission_files_present += 1
            try:
                loaded = load_submission_manifest(manifest_path)
            except (OSError, SubmissionManifestError) as error:
                submission_status = "invalid"
                student_warnings.append("invalid_submission")
                warnings.append(
                    DashboardWarning(
                        "invalid_submission", str(error), manifest_relative, student_id
                    )
                )
            else:
                if _identity_mismatch(loaded, class_id, assignment_id, student_id):
                    submission_status = "identity_mismatch"
                    student_warnings.append("submission_identity_mismatch")
                    warnings.append(
                        DashboardWarning(
                            "submission_identity_mismatch",
                            "Submission identity does not match its canonical path.",
                            manifest_relative,
                            student_id,
                        )
                    )
                else:
                    submission_status = "valid"
                    manifest = loaded
                    valid_manifests[student_id] = loaded
                    assembled_paths.update(_manifest_evidence_paths(root, loaded))
        elif student_id in roster_ids:
            student_warnings.append("missing_submission")

        review: dict[str, Any] | None = None
        review_status = "missing" if manifest is not None else "unavailable"
        if review_path.is_file():
            review_files_present += 1
            if manifest is None:
                review_status = "orphaned"
                orphaned_reviews += 1
                student_warnings.append("review_without_valid_submission")
                warnings.append(
                    DashboardWarning(
                        "review_without_valid_submission",
                        "Review record exists without a valid adjacent submission.",
                        review_relative,
                        student_id,
                    )
                )
            else:
                try:
                    loaded_review = load_review_record(review_path)
                except (OSError, ReviewRecordError) as error:
                    review_status = "invalid"
                    student_warnings.append("invalid_review")
                    warnings.append(
                        DashboardWarning(
                            "invalid_review", str(error), review_relative, student_id
                        )
                    )
                else:
                    if _identity_mismatch(
                        loaded_review, class_id, assignment_id, student_id
                    ):
                        review_status = "identity_mismatch"
                        student_warnings.append("review_identity_mismatch")
                        warnings.append(
                            DashboardWarning(
                                "review_identity_mismatch",
                                "Review identity does not match its canonical path.",
                                review_relative,
                                student_id,
                            )
                        )
                    else:
                        review_status = "valid"
                        review = loaded_review
        elif manifest is not None:
            student_warnings.append("missing_review")

        page_counts = Counter({state: 0 for state in PAGE_STATES})
        present_unselected = 0
        if manifest is not None:
            for page in manifest["pages"]:
                page_counts[page["page_state"]] += 1
                if (
                    page["page_state"] == "present"
                    and page["selected_evidence_id"] is None
                ):
                    present_unselected += 1
            page_counts["present_unselected"] = present_unselected

        pdf_default = feedback_pdf_export_path(
            root, class_id, assignment_id, student_id
        )
        md_default = feedback_export_path(root, class_id, assignment_id, student_id)
        _, pdf_status, _, pdf_warnings = feedback_status(
            root, review, "feedback_pdf", pdf_default
        )
        _, md_status, _, md_warnings = feedback_status(
            root, review, "feedback_markdown", md_default
        )
        student_warnings.extend(pdf_warnings)
        student_warnings.extend(md_warnings)
        for code in (*pdf_warnings, *md_warnings):
            warnings.append(
                DashboardWarning(code, _warning_message(code), student_id=student_id)
            )

        routed_present = student_id in routed_ids
        needs_assembly = routed_present and manifest is None
        if needs_assembly:
            student_warnings.append("routed_evidence_needs_assembly")
        if student_id not in roster_ids and roster_students is not None:
            student_warnings.append("unrostered_student")
        minimum = (
            None if review is None else review["minimum_requirement_outcome"]["status"]
        )
        returned = bool(
            review is not None
            and review["minimum_requirement_outcome"]["returned_without_full_review"]
        )
        students.append(
            DashboardStudentStatus(
                student_id=student_id,
                display_name=display_names.get(student_id, student_id),
                roster_status=(
                    "rostered"
                    if student_id in roster_ids
                    else "roster_unavailable"
                    if roster_students is None
                    else "unrostered"
                ),
                routed_evidence_present=routed_present,
                needs_assembly=needs_assembly,
                submission_status=submission_status,
                submission_path=manifest_relative,
                submission_state=None
                if manifest is None
                else manifest["submission_state"],
                plain_paper=manifest is not None
                and is_plain_paper_submission(manifest),
                evidence_file_count=(
                    0
                    if manifest is None
                    else sum(len(page["evidence"]) for page in manifest["pages"])
                ),
                page_counts=_fixed_counts(
                    page_counts, (*PAGE_STATES, "present_unselected")
                ),
                review_status=review_status,
                review_path=review_relative,
                review_state=None if review is None else review["review_state"],
                minimum_requirement_status=minimum,
                returned_without_full_review=returned,
                feedback_pdf_status=pdf_status,
                feedback_markdown_status=md_status,
                warnings=tuple(dict.fromkeys(student_warnings)),
            )
        )

    unassembled, unused_duplicates = _routed_file_status(
        root, routed.evidence_by_student, valid_manifests, assembled_paths
    )
    scan_available = True
    scan_items: tuple[DashboardScanReviewItem, ...] = ()
    scan_warning_count = 0
    try:
        scan_discovery = discover_scan_review_items(
            root, class_id=class_id, assignment_id=assignment_id, include_resolved=False
        )
        scan_warning_count = len(scan_discovery.warnings)
        for message in scan_discovery.warnings:
            warnings.append(DashboardWarning("scan_review_metadata_warning", message))
        scan_items = tuple(
            DashboardScanReviewItem(
                failure_id=item.failure_id,
                status=item.display_status,
                failure_category=item.failure_category,
                failure_message=item.failure_message,
                source_filename=item.source_filename,
                source_page_number=item.source_page_number,
                student_id=item.student_id,
                failure_metadata_path=item.failure_metadata_relative_path,
                retained_source_path=item.retained_source_path,
                created_at=item.created_at,
            )
            for item in scan_discovery.items
        )
    except (OSError, ScanReviewResolutionError, ValueError) as error:
        scan_available = False
        warnings.append(DashboardWarning("scan_review_unavailable", str(error)))

    return _dashboard(
        root=root,
        class_id=class_id,
        assignment_id=assignment_id,
        assignment=assignment,
        roster_students=roster_students,
        roster_ids=roster_ids,
        students=tuple(students),
        submission_files_present=submission_files_present,
        review_files_present=review_files_present,
        orphaned_reviews=orphaned_reviews,
        routed_ids=routed_ids,
        unassembled=unassembled,
        unused_duplicates=unused_duplicates,
        skipped=tuple(
            (relative_path_for(item.path, root), item.reason)
            for item in routed.skipped_files
        ),
        scan_available=scan_available,
        scan_warning_count=scan_warning_count,
        scan_items=scan_items,
        warnings=tuple(warnings),
    )


def _dashboard(**values: Any) -> AssignmentReviewDashboard:
    students: tuple[DashboardStudentStatus, ...] = values["students"]
    roster_ids: set[str] = values["roster_ids"]
    submission_statuses = Counter(student.submission_status for student in students)
    submission_states = Counter(
        student.submission_state
        for student in students
        if student.submission_state is not None
    )
    page_counts: Counter[str] = Counter()
    page_student_counts: Counter[str] = Counter()
    for student in students:
        counts = dict(student.page_counts)
        page_counts.update(counts)
        for state in (*PAGE_STATES, "present_unselected"):
            if counts[state]:
                page_student_counts[f"students_with_{state}"] += 1
    review_statuses = Counter(student.review_status for student in students)
    review_states = Counter(
        student.review_state for student in students if student.review_state is not None
    )
    minimum_states = Counter(
        student.minimum_requirement_status
        for student in students
        if student.minimum_requirement_status is not None
    )
    pdf_states = Counter(student.feedback_pdf_status for student in students)
    md_states = Counter(student.feedback_markdown_status for student in students)
    progress: Counter[str] = Counter()
    for student in students:
        if student.review_state is None:
            continue
        status = review_progress_status({"review_state": student.review_state})
        progress["observations_complete"] += status.observations_complete
        progress["ratings_complete"] += status.ratings_complete
        progress["feedback_composed"] += status.feedback_composed
        progress["ready_for_export"] += student.review_state in {
            "ready_for_export",
            "exported",
        }
        progress["exported"] += student.review_state == "exported"
    scan_items: tuple[DashboardScanReviewItem, ...] = values["scan_items"]
    scan_statuses = Counter(item.status for item in scan_items)
    categories = Counter(item.failure_category for item in scan_items)
    assignment = values["assignment"]
    roster_students = values["roster_students"]
    return AssignmentReviewDashboard(
        class_id=values["class_id"],
        assignment_id=values["assignment_id"],
        assignment_title=assignment["title"],
        writing_type=assignment["writing_type"],
        standards_profile_id=assignment["standards_profile_id"],
        focus_standard_count=len(assignment["focus_standard_ids"]),
        assignment_path=relative_path_for(
            values["root"]
            / "classes"
            / values["class_id"]
            / "assignments"
            / values["assignment_id"]
            / "assignment.json",
            values["root"],
        ),
        roster_available=roster_students is not None,
        rostered_count=None if roster_students is None else len(roster_students),
        students=students,
        submission_counts=(
            ("manifest_files_present", values["submission_files_present"]),
            ("valid", submission_statuses["valid"]),
            ("missing", submission_statuses["missing"]),
            ("invalid", submission_statuses["invalid"]),
            ("identity_mismatch", submission_statuses["identity_mismatch"]),
            ("plain_paper", sum(s.plain_paper for s in students)),
            (
                "rostered_students_missing_submission",
                sum(
                    s.student_id in roster_ids and s.submission_status != "valid"
                    for s in students
                ),
            ),
        ),
        submission_state_counts=_fixed_counts(submission_states, SUBMISSION_STATES),
        page_counts=(
            ("total", sum(page_counts[s] for s in PAGE_STATES)),
            *((state, page_counts[state]) for state in PAGE_STATES),
            ("present_unselected", page_counts["present_unselected"]),
        ),
        page_student_counts=_fixed_counts(
            page_student_counts,
            tuple(f"students_with_{s}" for s in (*PAGE_STATES, "present_unselected")),
        ),
        routed_counts=(
            ("students_with_routed_evidence", len(values["routed_ids"])),
            ("students_needing_assembly", sum(s.needs_assembly for s in students)),
            ("unassembled_files", len(values["unassembled"])),
            ("unused_duplicate_files", len(values["unused_duplicates"])),
            ("skipped_files", len(values["skipped"])),
            (
                "unrostered_students_discovered",
                sum(s.roster_status == "unrostered" for s in students),
            ),
        ),
        review_counts=(
            ("files_present", values["review_files_present"]),
            ("valid", review_statuses["valid"]),
            ("missing", review_statuses["missing"]),
            ("invalid", review_statuses["invalid"]),
            ("identity_mismatch", review_statuses["identity_mismatch"]),
            ("orphaned", values["orphaned_reviews"]),
        ),
        review_state_counts=_fixed_counts(review_states, REVIEW_STATES),
        minimum_requirement_counts=_fixed_counts(
            minimum_states, MINIMUM_REQUIREMENT_STATES
        ),
        workflow_counts=_fixed_counts(
            progress,
            (
                "observations_complete",
                "ratings_complete",
                "feedback_composed",
                "ready_for_export",
                "exported",
            ),
        ),
        feedback_pdf_counts=_fixed_counts(pdf_states, EXPORT_STATES),
        feedback_markdown_counts=_fixed_counts(md_states, EXPORT_STATES),
        scan_review_available=values["scan_available"],
        scan_review_counts=(
            ("attention_items", len(scan_items)),
            ("unresolved", scan_statuses["unresolved"]),
            ("deferred", scan_statuses["deferred"]),
            ("metadata_warning_count", values["scan_warning_count"]),
        ),
        scan_review_categories=tuple(sorted(categories.items())),
        unassembled_routed_files=values["unassembled"],
        unused_duplicate_routed_files=values["unused_duplicates"],
        skipped_routed_files=values["skipped"],
        scan_review_items=scan_items,
        warnings=values["warnings"],
    )


def assignment_review_dashboard_to_dict(
    dashboard: AssignmentReviewDashboard,
) -> dict[str, object]:
    """Serialize dashboard schema version 1 using JSON-native values."""
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "record_type": DASHBOARD_RECORD_TYPE,
        "class_id": dashboard.class_id,
        "assignment_id": dashboard.assignment_id,
        "assignment": {
            "title": dashboard.assignment_title,
            "writing_type": dashboard.writing_type,
            "standards_profile_id": dashboard.standards_profile_id,
            "focus_standard_count": dashboard.focus_standard_count,
            "path": dashboard.assignment_path,
        },
        "summary": {
            "students": {
                "dashboard_total": len(dashboard.students),
                "roster_available": dashboard.roster_available,
                "rostered": dashboard.rostered_count,
                "unrostered_discovered": dict(dashboard.routed_counts)[
                    "unrostered_students_discovered"
                ],
            },
            "submissions": {
                **dict(dashboard.submission_counts),
                "states": dict(dashboard.submission_state_counts),
            },
            "pages": {
                **dict(dashboard.page_counts),
                **dict(dashboard.page_student_counts),
            },
            "routed_evidence": dict(dashboard.routed_counts),
            "reviews": {
                **dict(dashboard.review_counts),
                "states": dict(dashboard.review_state_counts),
                "workflow": dict(dashboard.workflow_counts),
            },
            "minimum_requirements": dict(dashboard.minimum_requirement_counts),
            "feedback_exports": {
                "pdf": dict(dashboard.feedback_pdf_counts),
                "markdown": dict(dashboard.feedback_markdown_counts),
            },
            "scan_review": {
                "available": dashboard.scan_review_available,
                **dict(dashboard.scan_review_counts),
                "categories": dict(dashboard.scan_review_categories),
            },
        },
        "students": [_student_to_dict(student) for student in dashboard.students],
        "unassembled_routed_files": list(dashboard.unassembled_routed_files),
        "unused_duplicate_routed_files": list(dashboard.unused_duplicate_routed_files),
        "skipped_routed_files": [
            {"path": path, "reason": reason}
            for path, reason in dashboard.skipped_routed_files
        ],
        "scan_review_items": [
            _scan_item_to_dict(item) for item in dashboard.scan_review_items
        ],
        "warnings": [_warning_to_dict(warning) for warning in dashboard.warnings],
    }


def format_assignment_review_dashboard(
    dashboard: AssignmentReviewDashboard,
    *,
    show_unused_duplicate_files: bool = True,
) -> str:
    """Return concise deterministic teacher-facing dashboard text."""
    submissions, pages = dict(dashboard.submission_counts), dict(dashboard.page_counts)
    routed, reviews = dict(dashboard.routed_counts), dict(dashboard.review_counts)
    lines = [
        "Assignment Review Dashboard",
        "",
        f"Submission status for assignment {dashboard.assignment_id}",
        "",
        f"Class: {dashboard.class_id}",
        f"Assignment: {dashboard.assignment_title} ({dashboard.assignment_id})",
        f"Writing type: {dashboard.writing_type}",
        f"Focus Standards: {dashboard.focus_standard_count}",
        "",
        "Student coverage:",
        f"- Roster available: {'yes' if dashboard.roster_available else 'no'}",
        f"- Rostered students: {dashboard.rostered_count if dashboard.rostered_count is not None else 'unknown'}",
        f"- Dashboard students: {len(dashboard.students)}",
        f"- Unrostered records: {routed['unrostered_students_discovered']}",
        "",
        "Submission intake:",
        f"- Valid manifests: {submissions['valid']}",
        f"- Rostered students missing submissions: {submissions['rostered_students_missing_submission']}",
        f"- Routed-evidence students needing assembly: {routed['students_needing_assembly']}",
        f"- Invalid manifests: {submissions['invalid']}",
        f"- Identity mismatches: {submissions['identity_mismatch']}",
        f"- Plain-paper submissions: {submissions['plain_paper']}",
        f"- Unassembled routed files: {routed['unassembled_files']}",
        f"- Skipped routed files: {routed['skipped_files']}",
        "",
        "Submission states:",
    ]
    lines.extend(
        f"- {key}: {value}" for key, value in dashboard.submission_state_counts
    )
    lines.extend(["", "Page states:"])
    lines.extend(f"- {key.replace('_', ' ')}: {pages[key]}" for key in PAGE_STATES)
    lines.append(f"- present but unselected: {pages['present_unselected']}")
    lines.extend(
        [
            "",
            "Review progress:",
            f"- Valid reviews: {reviews['valid']}",
            f"- Missing reviews: {reviews['missing']}",
            f"- Invalid reviews: {reviews['invalid']}",
            f"- Identity mismatches: {reviews['identity_mismatch']}",
            f"- Orphaned reviews: {reviews['orphaned']}",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in dashboard.review_state_counts)
    lines.extend(["", "Minimum requirements:"])
    lines.extend(
        f"- {key}: {value}" for key, value in dashboard.minimum_requirement_counts
    )
    lines.extend(["", "Feedback exports:"])
    lines.extend(
        f"- PDF {key}: {value}" for key, value in dashboard.feedback_pdf_counts
    )
    lines.extend(
        f"- Markdown {key}: {value}"
        for key, value in dashboard.feedback_markdown_counts
    )
    scan = dict(dashboard.scan_review_counts)
    lines.extend(
        [
            "",
            "Scan review:",
            f"- Available: {'yes' if dashboard.scan_review_available else 'no'}",
            f"- Attention items: {scan['attention_items']}",
            f"- Unresolved: {scan['unresolved']}",
            f"- Deferred: {scan['deferred']}",
            f"- Metadata warnings: {scan['metadata_warning_count']}",
        ]
    )
    lines.extend(["", "Students:"])
    for student in dashboard.students:
        page_detail = ",".join(f"{k}:{v}" for k, v in student.page_counts if v)
        lines.append(
            f"- {student.display_name} ({student.student_id}):"
            if student.display_name != student.student_id
            else f"- {student.student_id}:"
        )
        lines.append(
            f"  submission={student.submission_state or student.submission_status}; pages={page_detail or 'none'}; "
            f"review={student.review_state or student.review_status}; pdf={student.feedback_pdf_status}; "
            f"markdown={student.feedback_markdown_status}"
        )
    attention = [s for s in dashboard.students if s.warnings]
    if attention or dashboard.scan_review_items or dashboard.warnings:
        lines.extend(["", "Needs attention:"])
        for student in attention:
            lines.append(f"- {student.display_name}: {', '.join(student.warnings)}")
        for item in dashboard.scan_review_items:
            lines.append(
                f"- Scan {item.failure_id}: {item.status}; {item.failure_category}; {item.failure_message}"
            )
        for warning in dashboard.warnings:
            if warning.student_id is None:
                lines.append(f"- {warning.code}: {warning.message}")
    if dashboard.skipped_routed_files:
        lines.extend(["", "Skipped routed files:"])
        lines.extend(
            f"- {path} — {reason}" for path, reason in dashboard.skipped_routed_files
        )
    if dashboard.unassembled_routed_files:
        lines.extend(
            [
                "",
                "Unassembled routed files:",
                *(f"- {p}" for p in dashboard.unassembled_routed_files),
            ]
        )
    if show_unused_duplicate_files and dashboard.unused_duplicate_routed_files:
        lines.extend(
            [
                "",
                "Duplicate routed files not used:",
                *(f"- {p}" for p in dashboard.unused_duplicate_routed_files),
            ]
        )
    return "\n".join(lines)


def _student_population(
    roster: tuple[Any, ...] | None, submission_ids: set[str], routed_ids: set[str]
) -> tuple[tuple[str, ...], dict[str, str], set[str]]:
    roster_ids: set[str] = set()
    display: dict[str, str] = {}
    ordered: list[str] = []
    if roster is not None:
        for student in roster:
            roster_ids.add(student.student_id)
            ordered.append(student.student_id)
            display[student.student_id] = student_display_name(student)
    ordered.extend(sorted(submission_ids - roster_ids))
    ordered.extend(sorted(routed_ids - set(ordered)))
    return tuple(ordered), display, roster_ids


def _directory_ids(path: Path) -> set[str]:
    try:
        return {entry.name for entry in path.iterdir() if entry.is_dir()}
    except (FileNotFoundError, NotADirectoryError):
        return set()
    except OSError as error:
        raise ReviewDashboardError(
            f"Could not discover submission directories: {error}"
        ) from error


def _identity_mismatch(
    record: dict[str, Any], class_id: str, assignment_id: str, student_id: str
) -> bool:
    return any(
        record[field] != expected
        for field, expected in (
            ("class_id", class_id),
            ("assignment_id", assignment_id),
            ("student_id", student_id),
        )
    )


def _manifest_evidence_paths(root: Path, manifest: dict[str, Any]) -> set[Path]:
    return {
        (root / item["routed_evidence_path"]).resolve(strict=False)
        for page in manifest["pages"]
        for item in page["evidence"]
    }


def _routed_file_status(
    root: Path,
    evidence_by_student: dict[str, list[Any]],
    manifests: dict[str, dict[str, Any]],
    assembled: set[Path],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    represented = {
        student_id: {
            page["page_number"] for page in manifest["pages"] if page["evidence"]
        }
        for student_id, manifest in manifests.items()
    }
    unassembled: list[str] = []
    duplicates: list[str] = []
    for student_id, items in evidence_by_student.items():
        for item in items:
            path = Path(item.routed_evidence_path)
            resolved = (root / path).resolve(strict=False)
            if resolved in assembled:
                continue
            relative = relative_path_for(resolved, root)
            if (
                item.duplicate_number is not None
                and item.page_number in represented.get(student_id, set())
            ):
                duplicates.append(relative)
            else:
                unassembled.append(relative)
    return tuple(sorted(unassembled, key=str.casefold)), tuple(
        sorted(duplicates, key=str.casefold)
    )


def _fixed_counts(
    counter: Counter[Any], keys: tuple[str, ...]
) -> tuple[tuple[str, int], ...]:
    return tuple((key, int(counter[key])) for key in keys)


def _student_to_dict(student: DashboardStudentStatus) -> dict[str, object]:
    return {
        "student_id": student.student_id,
        "display_name": student.display_name,
        "roster_status": student.roster_status,
        "routed_evidence_present": student.routed_evidence_present,
        "needs_assembly": student.needs_assembly,
        "submission": {
            "status": student.submission_status,
            "path": student.submission_path,
            "state": student.submission_state,
            "plain_paper": student.plain_paper,
            "pages": dict(student.page_counts),
        },
        "review": {
            "status": student.review_status,
            "path": student.review_path,
            "state": student.review_state,
            "minimum_requirement_status": student.minimum_requirement_status,
            "returned_without_full_review": student.returned_without_full_review,
        },
        "exports": {
            "feedback_pdf": student.feedback_pdf_status,
            "feedback_markdown": student.feedback_markdown_status,
        },
        "warnings": list(student.warnings),
    }


def _scan_item_to_dict(item: DashboardScanReviewItem) -> dict[str, object]:
    return {
        "failure_id": item.failure_id,
        "status": item.status,
        "failure_category": item.failure_category,
        "failure_message": item.failure_message,
        "source_filename": item.source_filename,
        "source_page_number": item.source_page_number,
        "student_id": item.student_id,
        "failure_metadata_path": item.failure_metadata_path,
        "retained_source_path": item.retained_source_path,
        "created_at": item.created_at,
    }


def _warning_to_dict(warning: DashboardWarning) -> dict[str, object]:
    return {
        "code": warning.code,
        "message": warning.message,
        "path": warning.path,
        "student_id": warning.student_id,
    }


def _warning_message(code: str) -> str:
    return code.replace("_", " ").capitalize() + "."
