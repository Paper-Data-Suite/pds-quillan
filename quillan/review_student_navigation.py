"""Deterministic class-set student navigation over the review work queue."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quillan.review_work_queue import (
    WORK_QUEUE_CATEGORIES,
    AssignmentReviewWorkQueue,
    ReviewWorkQueueError,
    ReviewWorkQueueItem,
    build_assignment_review_work_queue,
)


class ReviewStudentNavigationError(ValueError):
    """Raised when safe deterministic student navigation cannot be derived."""


@dataclass(frozen=True, slots=True)
class ReviewStudentNavigation:
    """Immutable roster-position navigation for one selected review student."""

    class_id: str
    assignment_id: str
    current: ReviewWorkQueueItem
    position: int
    roster_count: int
    previous: ReviewWorkQueueItem | None
    next: ReviewWorkQueueItem | None
    next_needing_review: ReviewWorkQueueItem | None
    needs_work_count: int
    needs_work_after_current_count: int


def build_review_student_navigation(
    workspace_root: str | Path,
    class_id: str,
    assignment_id: str,
    student_id: str,
) -> ReviewStudentNavigation:
    """Build fresh navigation from the current canonical #383 work queue."""
    try:
        queue = build_assignment_review_work_queue(
            workspace_root,
            class_id,
            assignment_id,
        )
    except ReviewWorkQueueError as error:
        raise ReviewStudentNavigationError(
            f"Could not build review student navigation: {error}"
        ) from error
    return derive_review_student_navigation(queue, student_id)


def derive_review_student_navigation(
    queue: AssignmentReviewWorkQueue,
    student_id: str,
) -> ReviewStudentNavigation:
    """Resolve bounded roster navigation without writing or wrapping."""
    if not isinstance(student_id, str) or not student_id:
        raise ReviewStudentNavigationError("student_id must be a non-empty string")

    _validate_queue_identity(queue)

    current_index = next(
        (
            index
            for index, item in enumerate(queue.items)
            if item.student_id == student_id
        ),
        None,
    )
    if current_index is None:
        raise ReviewStudentNavigationError(
            f"Student {student_id!r} is not in the canonical review queue for "
            f"class {queue.class_id!r}, assignment {queue.assignment_id!r}."
        )

    previous = queue.items[current_index - 1] if current_index > 0 else None
    next_index = current_index + 1
    next_student = (
        queue.items[next_index] if next_index < len(queue.items) else None
    )
    later_items = queue.items[next_index:]
    next_needing_review = next(
        (item for item in later_items if item.category != "complete"),
        None,
    )
    needs_work_count = sum(item.category != "complete" for item in queue.items)
    needs_work_after_current_count = sum(
        item.category != "complete" for item in later_items
    )

    return ReviewStudentNavigation(
        class_id=queue.class_id,
        assignment_id=queue.assignment_id,
        current=queue.items[current_index],
        position=current_index + 1,
        roster_count=len(queue.items),
        previous=previous,
        next=next_student,
        next_needing_review=next_needing_review,
        needs_work_count=needs_work_count,
        needs_work_after_current_count=needs_work_after_current_count,
    )


def _validate_queue_identity(queue: AssignmentReviewWorkQueue) -> None:
    seen: set[str] = set()
    for item in queue.items:
        if item.class_id != queue.class_id or item.assignment_id != queue.assignment_id:
            raise ReviewStudentNavigationError(
                "Review queue item identity does not match its class/assignment."
            )
        if item.student_id in seen:
            raise ReviewStudentNavigationError(
                f"Review queue contains duplicate student_id {item.student_id!r}."
            )
        if item.category not in WORK_QUEUE_CATEGORIES:
            raise ReviewStudentNavigationError(
                f"Review queue contains unknown category {item.category!r}."
            )
        seen.add(item.student_id)
