"""Focused read-only class review completion projection for one assignment."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from quillan.assignment_summary_context import load_assignment
from quillan.minimum_requirement_review import configured_requirements
from quillan.review_dashboard import (
    EXPORT_STATES,
    AssignmentReviewDashboard,
    build_assignment_review_dashboard,
)
from quillan.review_work_queue import (
    WORK_QUEUE_CATEGORIES,
    AssignmentReviewWorkQueue,
    ReviewWorkQueueError,
    derive_assignment_review_work_queue,
)

EXPORT_CAPABLE_CATEGORIES: Final = frozenset({"export_pending", "complete"})
FILTER_KINDS: Final = ("all", "needs_work", "category", "pdf", "markdown")


class ClassReviewCompletionError(ValueError):
    """Raised when focused class review completion cannot be derived safely."""


@dataclass(frozen=True, slots=True)
class ClassReviewCompletionItem:
    """One roster student's bounded operational state for class progress."""

    student_id: str
    display_name: str
    category: str
    reason_code: str
    feedback_pdf_status: str
    feedback_markdown_status: str
    warnings: tuple[str, ...]

    @property
    def export_capable(self) -> bool:
        return self.category in EXPORT_CAPABLE_CATEGORIES


@dataclass(frozen=True, slots=True)
class ClassReviewCompletionView:
    """Immutable roster-ordered focused projection for one exact assignment."""

    class_id: str
    assignment_id: str
    assignment_title: str
    items: tuple[ClassReviewCompletionItem, ...]
    category_counts: tuple[tuple[str, int], ...]
    feedback_pdf_counts: tuple[tuple[str, int], ...]
    feedback_markdown_counts: tuple[tuple[str, int], ...]
    unrostered_student_ids: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def roster_count(self) -> int:
        return len(self.items)

    @property
    def complete_count(self) -> int:
        return dict(self.category_counts)["complete"]

    @property
    def needs_work_count(self) -> int:
        return self.roster_count - self.complete_count

    @property
    def export_capable_count(self) -> int:
        counts = dict(self.category_counts)
        return counts["export_pending"] + counts["complete"]

    @property
    def export_pending_count(self) -> int:
        return dict(self.category_counts)["export_pending"]

    @property
    def attention_count(self) -> int:
        return dict(self.category_counts)["attention_required"]


@dataclass(frozen=True, slots=True)
class ClassReviewCompletionFilter:
    """One deterministic ephemeral filter for a focused class-progress view."""

    kind: str
    value: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in FILTER_KINDS:
            raise ClassReviewCompletionError(
                f"Unknown class review completion filter kind: {self.kind!r}."
            )
        if self.kind in {"all", "needs_work"}:
            if self.value is not None:
                raise ClassReviewCompletionError(
                    f"Filter {self.kind!r} does not accept a value."
                )
            return
        if self.value is None:
            raise ClassReviewCompletionError(
                f"Filter {self.kind!r} requires a value."
            )
        if self.kind == "category" and self.value not in WORK_QUEUE_CATEGORIES:
            raise ClassReviewCompletionError(
                f"Unknown review work category filter: {self.value!r}."
            )
        if self.kind in {"pdf", "markdown"} and self.value not in EXPORT_STATES:
            raise ClassReviewCompletionError(
                f"Unknown feedback export status filter: {self.value!r}."
            )


def build_class_review_completion_view(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
) -> ClassReviewCompletionView:
    """Build one focused view from one canonical dashboard snapshot."""
    root = Path(workspace_root)
    try:
        dashboard = build_assignment_review_dashboard(root, class_id, assignment_id)
        return derive_class_review_completion_view_from_dashboard(root, dashboard)
    except (OSError, ValueError) as error:
        if isinstance(error, ClassReviewCompletionError):
            raise
        raise ClassReviewCompletionError(
            f"Could not build class review completion view: {error}"
        ) from error


def derive_class_review_completion_view_from_dashboard(
    workspace_root: str | Path,
    dashboard: AssignmentReviewDashboard,
) -> ClassReviewCompletionView:
    """Derive focused progress from one already-built dashboard snapshot."""
    root = Path(workspace_root)
    try:
        assignment = load_assignment(
            root,
            dashboard.class_id,
            dashboard.assignment_id,
        )
        requirement_count = len(configured_requirements(assignment))
        return derive_class_review_completion_view(
            dashboard,
            configured_requirement_count=requirement_count,
        )
    except (OSError, ValueError) as error:
        if isinstance(error, ClassReviewCompletionError):
            raise
        raise ClassReviewCompletionError(
            f"Could not derive class review completion view: {error}"
        ) from error


def derive_class_review_completion_view(
    dashboard: AssignmentReviewDashboard,
    *,
    configured_requirement_count: int,
) -> ClassReviewCompletionView:
    """Derive focused progress from one dashboard and the authoritative #383 queue."""
    try:
        queue = derive_assignment_review_work_queue(
            dashboard,
            configured_requirement_count=configured_requirement_count,
        )
    except ReviewWorkQueueError as error:
        raise ClassReviewCompletionError(str(error)) from error

    roster_students = {
        student.student_id: student
        for student in dashboard.students
        if student.roster_status == "rostered"
    }
    if len(roster_students) != queue.roster_count:
        raise ClassReviewCompletionError(
            "Roster/dashboard population mismatch while deriving class progress."
        )

    items: list[ClassReviewCompletionItem] = []
    for queue_item in queue.items:
        student = roster_students.get(queue_item.student_id)
        if student is None:
            raise ClassReviewCompletionError(
                "Queue student is missing from the same dashboard snapshot: "
                f"{queue_item.student_id}."
            )
        _validate_export_status(student.feedback_pdf_status)
        _validate_export_status(student.feedback_markdown_status)
        items.append(
            ClassReviewCompletionItem(
                student_id=queue_item.student_id,
                display_name=queue_item.display_name,
                category=queue_item.category,
                reason_code=queue_item.reason_code,
                feedback_pdf_status=student.feedback_pdf_status,
                feedback_markdown_status=student.feedback_markdown_status,
                warnings=queue_item.warnings,
            )
        )

    return _view_from_queue(queue, tuple(items))


def filter_class_review_completion_items(
    view: ClassReviewCompletionView,
    filter_spec: ClassReviewCompletionFilter,
) -> tuple[ClassReviewCompletionItem, ...]:
    """Filter one immutable view without changing canonical roster order."""
    if filter_spec.kind == "all":
        return view.items
    if filter_spec.kind == "needs_work":
        return tuple(item for item in view.items if item.category != "complete")
    if filter_spec.kind == "category":
        return tuple(
            item for item in view.items if item.category == filter_spec.value
        )

    if filter_spec.kind == "pdf":
        return tuple(
            item
            for item in view.items
            if item.export_capable and item.feedback_pdf_status == filter_spec.value
        )
    if filter_spec.kind == "markdown":
        return tuple(
            item
            for item in view.items
            if item.export_capable
            and item.feedback_markdown_status == filter_spec.value
        )
    raise ClassReviewCompletionError(
        f"Unhandled class review completion filter kind: {filter_spec.kind!r}."
    )


def _view_from_queue(
    queue: AssignmentReviewWorkQueue,
    items: tuple[ClassReviewCompletionItem, ...],
) -> ClassReviewCompletionView:
    pdf_counts: Counter[str] = Counter()
    markdown_counts: Counter[str] = Counter()
    for item in items:
        if not item.export_capable:
            continue
        pdf_counts[item.feedback_pdf_status] += 1
        markdown_counts[item.feedback_markdown_status] += 1

    return ClassReviewCompletionView(
        class_id=queue.class_id,
        assignment_id=queue.assignment_id,
        assignment_title=queue.assignment_title,
        items=items,
        category_counts=queue.counts,
        feedback_pdf_counts=tuple(
            (state, pdf_counts[state]) for state in EXPORT_STATES
        ),
        feedback_markdown_counts=tuple(
            (state, markdown_counts[state]) for state in EXPORT_STATES
        ),
        unrostered_student_ids=queue.unrostered_student_ids,
        warnings=queue.warnings,
    )


def _validate_export_status(status: str) -> None:
    if status not in EXPORT_STATES:
        raise ClassReviewCompletionError(
            f"Unknown feedback export status in dashboard snapshot: {status!r}."
        )
