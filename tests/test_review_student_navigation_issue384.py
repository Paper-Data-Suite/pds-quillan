"""Issue #384 tests for deterministic class-set student navigation."""

from __future__ import annotations

from pathlib import Path

import pytest

from quillan.review_student_navigation import (
    ReviewStudentNavigationError,
    build_review_student_navigation,
    derive_review_student_navigation,
)
from quillan.review_work_queue import (
    WORK_QUEUE_CATEGORIES,
    AssignmentReviewWorkQueue,
    ReviewWorkQueueItem,
)
import quillan.review_student_navigation as navigation_module

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"


def _item(
    student_id: str,
    category: str,
    *,
    display_name: str | None = None,
    class_id: str = CLASS_ID,
    assignment_id: str = ASSIGNMENT_ID,
) -> ReviewWorkQueueItem:
    return ReviewWorkQueueItem(
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id,
        display_name=display_name or f"Student {student_id}",
        category=category,
        reason_code=f"reason_{category}",
        warnings=(),
    )


def _queue(*items: ReviewWorkQueueItem) -> AssignmentReviewWorkQueue:
    counts = tuple(
        (
            category,
            sum(item.category == category for item in items),
        )
        for category in WORK_QUEUE_CATEGORIES
    )
    return AssignmentReviewWorkQueue(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=items,
        counts=counts,
        unrostered_student_ids=(),
        warnings=(),
    )


def test_middle_student_resolves_previous_next_and_first_later_work() -> None:
    queue = _queue(
        _item("001", "observations_pending"),
        _item("002", "ratings_pending"),
        _item("003", "complete"),
        _item("004", "feedback_pending"),
        _item("005", "complete"),
    )

    result = derive_review_student_navigation(queue, "002")

    assert result.position == 2
    assert result.roster_count == 5
    assert result.current.student_id == "002"
    assert result.previous is not None
    assert result.previous.student_id == "001"
    assert result.next is not None
    assert result.next.student_id == "003"
    assert result.next_needing_review is not None
    assert result.next_needing_review.student_id == "004"
    assert result.needs_work_count == 3
    assert result.needs_work_after_current_count == 1


def test_first_student_has_no_previous_and_never_wraps() -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("002", "ratings_pending"),
    )

    result = derive_review_student_navigation(queue, "001")

    assert result.position == 1
    assert result.previous is None
    assert result.next is not None
    assert result.next.student_id == "002"
    assert result.next_needing_review is not None
    assert result.next_needing_review.student_id == "002"


def test_last_student_has_no_forward_target_and_never_wraps() -> None:
    queue = _queue(
        _item("001", "ratings_pending"),
        _item("002", "complete"),
        _item("003", "complete"),
    )

    result = derive_review_student_navigation(queue, "003")

    assert result.position == 3
    assert result.previous is not None
    assert result.previous.student_id == "002"
    assert result.next is None
    assert result.next_needing_review is None
    assert result.needs_work_count == 1
    assert result.needs_work_after_current_count == 0


def test_all_complete_has_no_next_needing_review() -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("002", "complete"),
        _item("003", "complete"),
    )

    for student_id in ("001", "002", "003"):
        result = derive_review_student_navigation(queue, student_id)
        assert result.next_needing_review is None
        assert result.needs_work_count == 0


@pytest.mark.parametrize(
    "category",
    tuple(category for category in WORK_QUEUE_CATEGORIES if category != "complete"),
)
def test_every_non_complete_queue_category_is_eligible_for_next_work(
    category: str,
) -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("002", "complete"),
        _item("003", category),
        _item("004", "observations_pending"),
    )

    result = derive_review_student_navigation(queue, "001")

    assert result.next_needing_review is not None
    assert result.next_needing_review.student_id == "003"
    assert result.next_needing_review.category == category


def test_duplicate_display_names_remain_distinct_by_exact_student_id() -> None:
    queue = _queue(
        _item("001", "complete", display_name="Alex Lee"),
        _item("017", "ratings_pending", display_name="Alex Lee"),
    )

    first = derive_review_student_navigation(queue, "001")
    second = derive_review_student_navigation(queue, "017")

    assert first.current.display_name == second.current.display_name == "Alex Lee"
    assert first.current.student_id == "001"
    assert second.current.student_id == "017"
    assert first.next is not None
    assert first.next.student_id == "017"
    assert second.previous is not None
    assert second.previous.student_id == "001"


def test_current_student_outside_roster_queue_fails_closed() -> None:
    queue = _queue(_item("001", "complete"), _item("002", "ratings_pending"))

    with pytest.raises(ReviewStudentNavigationError, match="not in the canonical"):
        derive_review_student_navigation(queue, "unrostered_003")


def test_duplicate_student_identity_in_queue_fails_closed() -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("001", "ratings_pending", display_name="Duplicate"),
    )

    with pytest.raises(ReviewStudentNavigationError, match="duplicate student_id"):
        derive_review_student_navigation(queue, "001")


def test_mismatched_queue_item_identity_fails_closed() -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("002", "ratings_pending", class_id="other_class"),
    )

    with pytest.raises(ReviewStudentNavigationError, match="identity does not match"):
        derive_review_student_navigation(queue, "001")


def test_empty_student_id_is_rejected() -> None:
    queue = _queue(_item("001", "complete"))

    with pytest.raises(ReviewStudentNavigationError, match="non-empty string"):
        derive_review_student_navigation(queue, "")


def test_repeated_derivation_is_deterministic() -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("002", "ratings_pending"),
        _item("003", "feedback_pending"),
    )

    first = derive_review_student_navigation(queue, "002")
    second = derive_review_student_navigation(queue, "002")

    assert first == second


def test_workspace_builder_reuses_exact_383_queue_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue(
        _item("001", "complete"),
        _item("002", "ratings_pending"),
    )
    calls: list[tuple[str | Path, str, str]] = []

    def fake_build_queue(
        workspace_root: str | Path,
        class_id: str,
        assignment_id: str,
    ) -> AssignmentReviewWorkQueue:
        calls.append((workspace_root, class_id, assignment_id))
        return queue

    monkeypatch.setattr(
        navigation_module,
        "build_assignment_review_work_queue",
        fake_build_queue,
    )

    result = build_review_student_navigation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        "001",
    )

    assert calls == [(tmp_path, CLASS_ID, ASSIGNMENT_ID)]
    assert result.current.student_id == "001"
    assert result.next is not None
    assert result.next.student_id == "002"
