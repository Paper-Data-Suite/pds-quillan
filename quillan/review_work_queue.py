"""Deterministic read-only work queue for one Quillan assignment."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from quillan.assignment_summary_context import load_assignment
from quillan.minimum_requirement_review import configured_requirements
from quillan.review_dashboard import (
    AssignmentReviewDashboard,
    DashboardStudentStatus,
    build_assignment_review_dashboard,
)
from quillan.review_status_display import review_progress_status

WORK_QUEUE_SCHEMA_VERSION: Final = "1"
WORK_QUEUE_RECORD_TYPE: Final = "quillan_assignment_review_work_queue"
WORK_QUEUE_CATEGORIES: Final = (
    "no_submission",
    "needs_assembly",
    "minimum_requirements_pending",
    "observations_pending",
    "ratings_pending",
    "feedback_pending",
    "export_pending",
    "complete",
    "attention_required",
)

CATEGORY_LABELS: Final = {
    "no_submission": "no submission",
    "needs_assembly": "needs assembly",
    "minimum_requirements_pending": "minimum requirements pending",
    "observations_pending": "observations pending",
    "ratings_pending": "ratings pending",
    "feedback_pending": "feedback pending",
    "export_pending": "export pending",
    "complete": "complete",
    "attention_required": "attention required",
}

_VALID_MINIMUM_OUTCOMES: Final = {
    "met",
    "unmet_continue_review",
    "returned_without_full_review",
}
_RETURNED_STATE: Final = "returned_without_full_review"


class ReviewWorkQueueError(ValueError):
    """Raised when a safe deterministic work queue cannot be derived."""


@dataclass(frozen=True, slots=True)
class ReviewWorkQueueItem:
    """One roster student's mechanically derived assignment-work state."""

    class_id: str
    assignment_id: str
    student_id: str
    display_name: str
    category: str
    reason_code: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssignmentReviewWorkQueue:
    """Immutable roster-ordered work queue for one exact assignment."""

    class_id: str
    assignment_id: str
    assignment_title: str
    items: tuple[ReviewWorkQueueItem, ...]
    counts: tuple[tuple[str, int], ...]
    unrostered_student_ids: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def roster_count(self) -> int:
        return len(self.items)

    @property
    def complete_count(self) -> int:
        return dict(self.counts)["complete"]

    @property
    def needs_work_count(self) -> int:
        return self.roster_count - self.complete_count


def build_assignment_review_work_queue(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> AssignmentReviewWorkQueue:
    """Build a read-only roster queue from current canonical Quillan state."""
    root = Path(workspace_root)
    try:
        dashboard = build_assignment_review_dashboard(root, class_id, assignment_id)
        assignment = load_assignment(root, class_id, assignment_id)
    except (OSError, ValueError) as error:
        raise ReviewWorkQueueError(
            f"Could not build review work queue: {error}"
        ) from error

    requirement_count = len(configured_requirements(assignment))
    return derive_assignment_review_work_queue(
        dashboard,
        configured_requirement_count=requirement_count,
    )


def derive_assignment_review_work_queue(
    dashboard: AssignmentReviewDashboard,
    *,
    configured_requirement_count: int,
) -> AssignmentReviewWorkQueue:
    """Derive queue classification from one already-built canonical dashboard."""
    if configured_requirement_count < 0:
        raise ReviewWorkQueueError(
            "configured_requirement_count must be zero or greater"
        )
    if not dashboard.roster_available or dashboard.rostered_count is None:
        raise ReviewWorkQueueError(
            "Canonical class roster is unavailable; review queue ordering cannot "
            "be derived safely."
        )

    items: list[ReviewWorkQueueItem] = []
    unrostered_student_ids: list[str] = []
    for student in dashboard.students:
        if student.roster_status == "rostered":
            items.append(
                classify_review_work_queue_item(
                    dashboard.class_id,
                    dashboard.assignment_id,
                    student,
                    configured_requirement_count=configured_requirement_count,
                )
            )
        elif student.roster_status == "unrostered":
            unrostered_student_ids.append(student.student_id)
        else:
            raise ReviewWorkQueueError(
                "Unexpected student roster state while a canonical roster is "
                f"available: {student.roster_status!r}."
            )

    if len(items) != dashboard.rostered_count:
        raise ReviewWorkQueueError(
            "Roster/dashboard population mismatch: expected "
            f"{dashboard.rostered_count} roster students, derived {len(items)}."
        )

    counts = Counter(item.category for item in items)
    warnings = [
        warning.code
        for warning in dashboard.warnings
        if warning.student_id is None
    ]
    if unrostered_student_ids:
        warnings.append("unrostered_records_excluded")

    return AssignmentReviewWorkQueue(
        class_id=dashboard.class_id,
        assignment_id=dashboard.assignment_id,
        assignment_title=dashboard.assignment_title,
        items=tuple(items),
        counts=tuple(
            (category, counts[category]) for category in WORK_QUEUE_CATEGORIES
        ),
        unrostered_student_ids=tuple(unrostered_student_ids),
        warnings=_dedupe(warnings),
    )


def classify_review_work_queue_item(
    class_id: str,
    assignment_id: str,
    student: DashboardStudentStatus,
    *,
    configured_requirement_count: int,
) -> ReviewWorkQueueItem:
    """Classify one dashboard student without inventing teacher judgment."""
    if configured_requirement_count < 0:
        raise ReviewWorkQueueError(
            "configured_requirement_count must be zero or greater"
        )

    warnings = list(student.warnings)

    if student.submission_status == "invalid":
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "invalid_submission",
            warnings,
        )
    if student.submission_status == "identity_mismatch":
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "record_identity_mismatch",
            warnings,
        )
    if student.review_status == "invalid":
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "invalid_review",
            warnings,
        )
    if student.review_status == "identity_mismatch":
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "record_identity_mismatch",
            warnings,
        )
    if student.review_status == "orphaned":
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "orphan_review",
            warnings,
        )

    if student.submission_status != "valid":
        if student.submission_status not in {"missing"}:
            return _item(
                class_id,
                assignment_id,
                student,
                "attention_required",
                "submission_state_unavailable",
                warnings,
            )
        if student.needs_assembly:
            return _item(
                class_id,
                assignment_id,
                student,
                "needs_assembly",
                "routed_evidence_needs_assembly",
                warnings,
            )
        return _item(
            class_id,
            assignment_id,
            student,
            "no_submission",
            "submission_missing",
            warnings,
        )

    if student.review_status not in {"valid", "missing"}:
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "review_state_unavailable",
            warnings,
        )

    outcome_returned = student.minimum_requirement_status == _RETURNED_STATE
    flag_returned = student.returned_without_full_review
    state_returned = student.review_state == _RETURNED_STATE
    any_returned = outcome_returned or flag_returned or state_returned
    all_returned = outcome_returned and flag_returned and state_returned
    if any_returned and not all_returned:
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "returned_state_inconsistent",
            warnings,
        )
    if all_returned and configured_requirement_count == 0:
        return _item(
            class_id,
            assignment_id,
            student,
            "attention_required",
            "returned_state_without_configured_requirements",
            warnings,
        )

    if configured_requirement_count > 0 and (
        student.minimum_requirement_status not in _VALID_MINIMUM_OUTCOMES
    ):
        if student.review_state not in {None, "not_started", "requirements_checked"}:
            warnings.append("workflow_state_ahead_of_minimum_requirements")
        return _item(
            class_id,
            assignment_id,
            student,
            "minimum_requirements_pending",
            "minimum_requirement_outcome_not_checked",
            warnings,
        )

    if all_returned:
        return _export_or_complete_item(
            class_id,
            assignment_id,
            student,
            warnings,
        )

    state = student.review_state or "not_started"
    progress = review_progress_status({"review_state": state})
    if not progress.observations_complete:
        return _item(
            class_id,
            assignment_id,
            student,
            "observations_pending",
            "observations_not_complete",
            warnings,
        )
    if not progress.ratings_complete:
        return _item(
            class_id,
            assignment_id,
            student,
            "ratings_pending",
            "ratings_not_complete",
            warnings,
        )
    if not progress.feedback_composed:
        return _item(
            class_id,
            assignment_id,
            student,
            "feedback_pending",
            "feedback_not_composed",
            warnings,
        )

    return _export_or_complete_item(
        class_id,
        assignment_id,
        student,
        warnings,
    )


def assignment_review_work_queue_to_dict(
    queue: AssignmentReviewWorkQueue,
) -> dict[str, object]:
    """Serialize the emitted queue representation using deterministic key order."""
    return {
        "schema_version": WORK_QUEUE_SCHEMA_VERSION,
        "record_type": WORK_QUEUE_RECORD_TYPE,
        "class_id": queue.class_id,
        "assignment_id": queue.assignment_id,
        "assignment_title": queue.assignment_title,
        "counts": dict(queue.counts),
        "students": [
            {
                "student_id": item.student_id,
                "display_name": item.display_name,
                "category": item.category,
                "reason_code": item.reason_code,
                "warnings": list(item.warnings),
            }
            for item in queue.items
        ],
        "unrostered_student_ids": list(queue.unrostered_student_ids),
        "warnings": list(queue.warnings),
    }


def format_assignment_review_work_queue(
    queue: AssignmentReviewWorkQueue,
) -> str:
    """Render a concise deterministic teacher-facing queue."""
    lines = [
        "Review Work Queue",
        "",
        f"Class: {queue.class_id}",
        f"Assignment: {queue.assignment_title} ({queue.assignment_id})",
        "",
        f"Complete: {queue.complete_count} / {queue.roster_count}",
        f"Needs work: {queue.needs_work_count}",
        "",
        "Category counts:",
    ]
    lines.extend(
        f"- {CATEGORY_LABELS[category]}: {count}"
        for category, count in queue.counts
    )
    lines.extend(["", "Students:"])
    if not queue.items:
        lines.append("- none")
    for index, item in enumerate(queue.items, start=1):
        identity = (
            f"{item.display_name} ({item.student_id})"
            if item.display_name != item.student_id
            else item.student_id
        )
        lines.append(
            f"{index}. {identity} — {CATEGORY_LABELS[item.category]} "
            f"[{item.reason_code}]"
        )

    if queue.unrostered_student_ids:
        lines.extend(
            [
                "",
                "Unrostered records excluded from queue:",
                *(f"- {student_id}" for student_id in queue.unrostered_student_ids),
            ]
        )
    if queue.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in queue.warnings)
    return "\n".join(lines)


def _export_or_complete_item(
    class_id: str,
    assignment_id: str,
    student: DashboardStudentStatus,
    warnings: list[str],
) -> ReviewWorkQueueItem:
    statuses = (student.feedback_pdf_status, student.feedback_markdown_status)
    if "present" in statuses:
        return _item(
            class_id,
            assignment_id,
            student,
            "complete",
            "current_feedback_export_present",
            warnings,
        )
    if "stale" in statuses:
        reason = "feedback_export_stale"
    elif "unknown" in statuses:
        reason = "feedback_export_metadata_unknown"
    else:
        reason = "feedback_export_missing"
    return _item(
        class_id,
        assignment_id,
        student,
        "export_pending",
        reason,
        warnings,
    )


def _item(
    class_id: str,
    assignment_id: str,
    student: DashboardStudentStatus,
    category: str,
    reason_code: str,
    warnings: list[str],
) -> ReviewWorkQueueItem:
    if category not in WORK_QUEUE_CATEGORIES:
        raise ReviewWorkQueueError(f"Unknown work queue category: {category}")
    return ReviewWorkQueueItem(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student.student_id,
        display_name=student.display_name,
        category=category,
        reason_code=reason_code,
        warnings=_dedupe(warnings),
    )


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
