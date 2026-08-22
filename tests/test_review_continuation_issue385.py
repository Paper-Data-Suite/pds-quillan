"""Issue #385 Slice 1 tests for deterministic Continue Review projection."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from quillan.review_continuation import (
    CONTINUATION_STATUSES,
    CONTINUATION_TARGETS,
    ReviewContinuation,
    ReviewContinuationError,
    derive_review_continuation,
)
from quillan.review_work_queue import ReviewWorkQueueItem

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"
STUDENT_ID = "00100"


def _item(
    category: str,
    *,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
    student_id: str = STUDENT_ID,
    reason_code: str | None = None,
    warnings: tuple[str, ...] = (),
) -> ReviewWorkQueueItem:
    return ReviewWorkQueueItem(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        display_name="Avery Rivera",
        category=category,
        reason_code=(f"reason_{category}" if reason_code is None else reason_code),
        warnings=warnings,
    )


@pytest.mark.parametrize(
    ("category", "status", "target", "label"),
    (
        (
            "no_submission",
            "unavailable",
            None,
            "unavailable (no reviewable submission)",
        ),
        (
            "needs_assembly",
            "unavailable",
            None,
            "unavailable (submission needs assembly)",
        ),
        (
            "minimum_requirements_pending",
            "available",
            "minimum_requirements",
            "Review minimum requirements",
        ),
        (
            "observations_pending",
            "available",
            "review_unit_observations",
            "Review units and Focus Standard observations",
        ),
        (
            "ratings_pending",
            "available",
            "overall_focus_standard_ratings",
            "Overall Focus Standard ratings",
        ),
        (
            "feedback_pending",
            "available",
            "focus_standard_feedback",
            "Compose Focus Standard feedback",
        ),
        (
            "export_pending",
            "available",
            "feedback_export",
            "Export student feedback",
        ),
        ("complete", "complete", None, "complete"),
        (
            "attention_required",
            "unavailable",
            None,
            "unavailable (attention required)",
        ),
    ),
)
def test_every_383_category_has_one_exact_continuation_mapping(
    category: str,
    status: str,
    target: str | None,
    label: str,
) -> None:
    result = derive_review_continuation(_item(category))

    assert result.status == status
    assert result.target == target
    assert result.label == label


def test_exact_identity_reason_and_warnings_are_propagated() -> None:
    item = _item(
        "attention_required",
        class_id="english10_p2_synthetic",
        assignment_id="unit_1_analysis_synthetic",
        student_id="00900",
        reason_code="record_identity_mismatch",
        warnings=("invalid_review_identity", "feedback_export_stale"),
    )

    result = derive_review_continuation(item)

    assert result.class_id == item.class_id
    assert result.assignment_id == item.assignment_id
    assert result.student_id == item.student_id
    assert result.source_category == item.category
    assert result.source_reason_code == item.reason_code
    assert result.warnings == item.warnings


def test_available_target_vocabulary_is_bounded() -> None:
    results = tuple(
        derive_review_continuation(_item(category))
        for category in (
            "minimum_requirements_pending",
            "observations_pending",
            "ratings_pending",
            "feedback_pending",
            "export_pending",
        )
    )

    assert tuple(result.target for result in results) == CONTINUATION_TARGETS
    assert all(result.status == "available" for result in results)
    assert CONTINUATION_STATUSES == ("available", "complete", "unavailable")


def test_non_actionable_states_never_receive_a_target() -> None:
    for category in (
        "no_submission",
        "needs_assembly",
        "complete",
        "attention_required",
    ):
        result = derive_review_continuation(_item(category))
        assert result.target is None
        assert result.status != "available"


def test_projection_is_immutable() -> None:
    result = derive_review_continuation(_item("ratings_pending"))

    with pytest.raises(FrozenInstanceError):
        result.label = "changed"  # type: ignore[misc]


def test_repeated_resolution_is_deterministic() -> None:
    item = _item(
        "feedback_pending",
        reason_code="feedback_not_composed",
        warnings=("bounded_warning",),
    )

    first = derive_review_continuation(item)
    second = derive_review_continuation(item)

    assert first == second


@pytest.mark.parametrize(
    ("field_name", "item"),
    (
        ("class_id", _item("ratings_pending", class_id="")),
        ("assignment_id", _item("ratings_pending", assignment_id="")),
        ("student_id", _item("ratings_pending", student_id="")),
        ("reason_code", _item("ratings_pending", reason_code="")),
    ),
)
def test_invalid_source_identity_or_reason_fails_closed(
    field_name: str,
    item: ReviewWorkQueueItem,
) -> None:
    with pytest.raises(ReviewContinuationError, match=field_name):
        derive_review_continuation(item)


def test_unknown_queue_category_fails_closed() -> None:
    item = _item("future_unknown_category")

    with pytest.raises(ReviewContinuationError, match="Unknown review work category"):
        derive_review_continuation(item)


def test_projection_contains_no_student_or_teacher_review_content_fields() -> None:
    field_names = set(ReviewContinuation.__dataclass_fields__)

    assert field_names == {
        "class_id",
        "assignment_id",
        "student_id",
        "source_category",
        "source_reason_code",
        "status",
        "target",
        "label",
        "warnings",
    }
    assert not field_names.intersection(
        {
            "display_name",
            "student_writing",
            "feedback",
            "teacher_notes",
            "rating",
            "rationale",
        }
    )
