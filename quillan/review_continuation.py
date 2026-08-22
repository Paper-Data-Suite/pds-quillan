"""Deterministic review-stage continuation over #383 work-queue items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from quillan.review_work_queue import WORK_QUEUE_CATEGORIES, ReviewWorkQueueItem

ReviewContinuationStatus = Literal["available", "complete", "unavailable"]
ReviewContinuationTarget = Literal[
    "minimum_requirements",
    "review_unit_observations",
    "overall_focus_standard_ratings",
    "focus_standard_feedback",
    "feedback_export",
]

CONTINUATION_STATUSES: Final[tuple[ReviewContinuationStatus, ...]] = (
    "available",
    "complete",
    "unavailable",
)
CONTINUATION_TARGETS: Final[tuple[ReviewContinuationTarget, ...]] = (
    "minimum_requirements",
    "review_unit_observations",
    "overall_focus_standard_ratings",
    "focus_standard_feedback",
    "feedback_export",
)


class ReviewContinuationError(ValueError):
    """Raised when safe continuation cannot be derived from a queue item."""


@dataclass(frozen=True, slots=True)
class ReviewContinuation:
    """Immutable next-stage guidance for one exact selected student."""

    class_id: str
    assignment_id: str
    student_id: str
    source_category: str
    source_reason_code: str
    status: ReviewContinuationStatus
    target: ReviewContinuationTarget | None
    label: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ContinuationResolution:
    status: ReviewContinuationStatus
    target: ReviewContinuationTarget | None
    label: str


_CATEGORY_RESOLUTIONS: Final[dict[str, _ContinuationResolution]] = {
    "no_submission": _ContinuationResolution(
        status="unavailable",
        target=None,
        label="unavailable (no reviewable submission)",
    ),
    "needs_assembly": _ContinuationResolution(
        status="unavailable",
        target=None,
        label="unavailable (submission needs assembly)",
    ),
    "minimum_requirements_pending": _ContinuationResolution(
        status="available",
        target="minimum_requirements",
        label="Review minimum requirements",
    ),
    "observations_pending": _ContinuationResolution(
        status="available",
        target="review_unit_observations",
        label="Review units and Focus Standard observations",
    ),
    "ratings_pending": _ContinuationResolution(
        status="available",
        target="overall_focus_standard_ratings",
        label="Overall Focus Standard ratings",
    ),
    "feedback_pending": _ContinuationResolution(
        status="available",
        target="focus_standard_feedback",
        label="Compose Focus Standard feedback",
    ),
    "export_pending": _ContinuationResolution(
        status="available",
        target="feedback_export",
        label="Export student feedback",
    ),
    "complete": _ContinuationResolution(
        status="complete",
        target=None,
        label="complete",
    ),
    "attention_required": _ContinuationResolution(
        status="unavailable",
        target=None,
        label="unavailable (attention required)",
    ),
}


def derive_review_continuation(item: ReviewWorkQueueItem) -> ReviewContinuation:
    """Map one canonical #383 work item to bounded no-write stage guidance."""
    _validate_source_item(item)
    try:
        resolution = _CATEGORY_RESOLUTIONS[item.category]
    except KeyError as error:
        raise ReviewContinuationError(
            f"Unknown review work category: {item.category!r}."
        ) from error

    return ReviewContinuation(
        class_id=item.class_id,
        assignment_id=item.assignment_id,
        student_id=item.student_id,
        source_category=item.category,
        source_reason_code=item.reason_code,
        status=resolution.status,
        target=resolution.target,
        label=resolution.label,
        warnings=item.warnings,
    )


def _validate_source_item(item: ReviewWorkQueueItem) -> None:
    for field_name, value in (
        ("class_id", item.class_id),
        ("assignment_id", item.assignment_id),
        ("student_id", item.student_id),
        ("reason_code", item.reason_code),
    ):
        if not isinstance(value, str) or not value:
            raise ReviewContinuationError(
                f"Review work queue item {field_name} must be a non-empty string."
            )
    if item.category not in WORK_QUEUE_CATEGORIES:
        raise ReviewContinuationError(
            f"Unknown review work category: {item.category!r}."
        )
