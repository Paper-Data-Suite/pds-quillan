"""Issue #387 service tests for batch feedback planning and verification."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

import quillan.batch_feedback_export as batch
from quillan.feedback_export import FeedbackExportError
from quillan.batch_feedback_export import (
    BatchFeedbackExportError,
    BatchFeedbackExportPlan,
    OverwritePolicy,
    BatchFeedbackExportStudentPlan,
    _StudentExportSnapshot,
    build_batch_feedback_export_plan,
    execute_batch_feedback_export,
)
from quillan.review_work_queue import (
    AssignmentReviewWorkQueue,
    ReviewWorkQueueItem,
)

CLASS_ID = "english12_p3_synthetic"
ASSIGNMENT_ID = "essay_01_synthetic"


def _item(
    student_id: str,
    category: str,
    *,
    reason: str | None = None,
) -> ReviewWorkQueueItem:
    return ReviewWorkQueueItem(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        student_id=student_id,
        display_name=f"Student {student_id}",
        category=category,
        reason_code=reason or category,
        warnings=(),
    )


def _queue(*items: ReviewWorkQueueItem) -> AssignmentReviewWorkQueue:
    categories = (
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
    return AssignmentReviewWorkQueue(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        items=items,
        counts=tuple(
            (category, sum(item.category == category for item in items))
            for category in categories
        ),
        unrostered_student_ids=(),
        warnings=(),
    )


def _snapshot(
    *,
    pdf: str = "missing",
    markdown: str = "missing",
    updated_at: str = "2026-08-23T12:00:00+00:00",
) -> _StudentExportSnapshot:
    statuses = (("feedback_pdf", pdf), ("feedback_markdown", markdown))
    return _StudentExportSnapshot(
        review_updated_at=updated_at,
        statuses=statuses,
        file_present=(
            ("feedback_pdf", pdf in {"present", "stale"}),
            ("feedback_markdown", markdown in {"present", "stale"}),
        ),
        metadata_present=(
            ("feedback_pdf", pdf in {"present", "stale"}),
            ("feedback_markdown", markdown in {"present", "stale"}),
        ),
        source_review_updated_at=(
            ("feedback_pdf", updated_at if pdf == "present" else None),
            ("feedback_markdown", updated_at if markdown == "present" else None),
        ),
        paths=(
            ("feedback_pdf", "classes/c/a/s/feedback.pdf"),
            ("feedback_markdown", "classes/c/a/s/feedback.md"),
        ),
        warnings=(),
    )


def _install_plan_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    queue: AssignmentReviewWorkQueue,
    snapshots: dict[str, _StudentExportSnapshot],
) -> None:
    monkeypatch.setattr(
        batch, "build_assignment_review_work_queue", lambda *args: queue
    )
    monkeypatch.setattr(
        batch,
        "_load_student_export_snapshot",
        lambda *args: snapshots[args[-1]],
    )


def test_completed_scope_uses_only_export_capable_queue_states(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue = _queue(
        _item("001", "export_pending"),
        _item("002", "feedback_pending"),
        _item("003", "complete"),
        _item("004", "attention_required"),
    )
    _install_plan_dependencies(
        monkeypatch,
        queue,
        {"001": _snapshot(), "003": _snapshot(pdf="present")},
    )

    plan = build_batch_feedback_export_plan(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        scope="completed",
        feedback_format="pdf",
    )

    assert [item.student_id for item in plan.items] == ["001", "003"]
    assert [item.action for item in plan.items] == ["create", "skip_current"]
    assert plan.excluded_incomplete_count == 1
    assert plan.excluded_attention_count == 1
    assert plan.writable_count == 1


def test_explicit_selection_preserves_roster_order_and_blocks_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue = _queue(
        _item("001", "feedback_pending"),
        _item("002", "complete"),
        _item("003", "export_pending"),
    )
    _install_plan_dependencies(
        monkeypatch,
        queue,
        {"002": _snapshot(pdf="present"), "003": _snapshot()},
    )

    plan = build_batch_feedback_export_plan(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        scope="selected",
        student_ids=("003", "001"),
        feedback_format="pdf",
    )

    assert [item.student_id for item in plan.items] == ["001", "003"]
    assert [item.action for item in plan.items] == ["blocked_incomplete", "create"]


def test_explicit_selection_rejects_unknown_or_duplicate_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue = _queue(_item("001", "complete"))
    monkeypatch.setattr(
        batch, "build_assignment_review_work_queue", lambda *args: queue
    )

    with pytest.raises(BatchFeedbackExportError, match="unknown roster student"):
        build_batch_feedback_export_plan(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            scope="selected",
            student_ids=("999",),
            feedback_format="pdf",
        )
    with pytest.raises(BatchFeedbackExportError, match="must be unique"):
        build_batch_feedback_export_plan(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            scope="selected",
            student_ids=("001", "001"),
            feedback_format="pdf",
        )


@pytest.mark.parametrize(
    ("policy", "status", "action"),
    (
        ("none", "missing", "create"),
        ("none", "present", "skip_current"),
        ("none", "stale", "blocked_conflict"),
        ("stale", "stale", "replace"),
        ("stale", "present", "skip_current"),
        ("all", "present", "replace"),
        ("all", "stale", "replace"),
        ("all", "unknown", "blocked_unknown_state"),
    ),
)
def test_single_format_overwrite_policy_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    policy: str,
    status: str,
    action: str,
) -> None:
    queue = _queue(_item("001", "complete"))
    _install_plan_dependencies(monkeypatch, queue, {"001": _snapshot(pdf=status)})

    plan = build_batch_feedback_export_plan(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        scope="completed",
        feedback_format="pdf",
        overwrite_policy=cast(OverwritePolicy, policy),
    )

    assert plan.items[0].action == action


@pytest.mark.parametrize(
    ("policy", "pdf", "markdown", "action"),
    (
        ("none", "missing", "missing", "create"),
        ("none", "present", "present", "skip_current"),
        ("none", "present", "missing", "blocked_conflict"),
        ("stale", "present", "missing", "blocked_conflict"),
        ("stale", "stale", "present", "replace"),
        ("all", "present", "missing", "replace"),
        ("all", "missing", "present", "replace"),
    ),
)
def test_both_format_is_planned_as_one_coupled_operation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    policy: str,
    pdf: str,
    markdown: str,
    action: str,
) -> None:
    queue = _queue(_item("001", "complete"))
    _install_plan_dependencies(
        monkeypatch,
        queue,
        {"001": _snapshot(pdf=pdf, markdown=markdown)},
    )

    plan = build_batch_feedback_export_plan(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        scope="completed",
        feedback_format="both",
        overwrite_policy=cast(OverwritePolicy, policy),
    )

    assert plan.items[0].action == action


def _execution_plan(*items: BatchFeedbackExportStudentPlan) -> BatchFeedbackExportPlan:
    return BatchFeedbackExportPlan(
        class_id=CLASS_ID,
        assignment_id=ASSIGNMENT_ID,
        assignment_title="Synthetic Essay",
        scope="selected",
        feedback_format="pdf",
        overwrite_policy="none",
        roster_count=len(items),
        excluded_incomplete_count=0,
        excluded_attention_count=0,
        items=items,
    )


def _writable(student_id: str) -> BatchFeedbackExportStudentPlan:
    return BatchFeedbackExportStudentPlan(
        student_id=student_id,
        display_name=f"Student {student_id}",
        category="export_pending",
        reason_code="feedback_export_missing",
        warnings=(),
        review_updated_at="2026-08-23T12:00:00+00:00",
        requested_export_statuses=(("feedback_pdf", "missing"),),
        action="create",
    )


def test_state_change_after_preview_prevents_that_student_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item = _writable("001")
    plan = _execution_plan(item)
    queue = _queue(_item("001", "export_pending"))
    monkeypatch.setattr(
        batch, "build_assignment_review_work_queue", lambda *args: queue
    )
    monkeypatch.setattr(
        batch,
        "_load_student_export_snapshot",
        lambda *args: _snapshot(updated_at="2026-08-23T12:01:00+00:00"),
    )
    calls: list[str] = []
    monkeypatch.setattr(
        batch,
        "export_student_feedback_pdf",
        lambda *args, **kwargs: calls.append("write"),
    )

    result = execute_batch_feedback_export(tmp_path, plan)

    assert result.items[0].outcome == "state_changed"
    assert calls == []


def test_failure_isolation_continues_to_later_students(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _writable("001")
    second = _writable("002")
    third = _writable("003")
    plan = _execution_plan(first, second, third)
    queue = _queue(
        _item("001", "export_pending"),
        _item("002", "export_pending"),
        _item("003", "export_pending"),
    )
    monkeypatch.setattr(
        batch, "build_assignment_review_work_queue", lambda *args: queue
    )
    monkeypatch.setattr(
        batch,
        "_load_student_export_snapshot",
        lambda *args: _snapshot(),
    )
    attempted: list[str] = []

    def export(*args: object, **kwargs: object) -> None:
        student_id = str(args[3])
        attempted.append(student_id)
        if student_id == "002":
            raise FeedbackExportError("synthetic export failure")

    monkeypatch.setattr(batch, "export_student_feedback_pdf", export)
    monkeypatch.setattr(
        batch,
        "_verify_student_export",
        lambda root, current_plan, student_id: (f"verified/{student_id}.pdf",),
    )

    result = execute_batch_feedback_export(tmp_path, plan)

    assert attempted == ["001", "002", "003"]
    assert [item.outcome for item in result.items] == [
        "created",
        "export_failed",
        "created",
    ]
    assert result.failure_count == 1


def test_verification_failure_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    item = _writable("001")
    plan = _execution_plan(item)
    queue = _queue(_item("001", "export_pending"))
    monkeypatch.setattr(
        batch, "build_assignment_review_work_queue", lambda *args: queue
    )
    monkeypatch.setattr(
        batch, "_load_student_export_snapshot", lambda *args: _snapshot()
    )
    monkeypatch.setattr(
        batch, "export_student_feedback_pdf", lambda *args, **kwargs: None
    )

    def fail_verification(*args: object, **kwargs: object) -> tuple[str, ...]:
        raise BatchFeedbackExportError("synthetic verification failure")

    monkeypatch.setattr(batch, "_verify_student_export", fail_verification)

    result = execute_batch_feedback_export(tmp_path, plan)

    assert result.items[0].outcome == "verification_failed"
    assert result.failure_count == 1
