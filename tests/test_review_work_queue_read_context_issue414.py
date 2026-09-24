"""Issue #414 tests for work-queue reuse of the redraw-scoped read context."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.review_work_queue as queue_module
from quillan.review_read_context import build_assignment_review_read_context
from quillan.review_work_queue import (
    ReviewWorkQueueError,
    assignment_review_work_queue_to_dict,
    build_assignment_review_work_queue,
    build_assignment_review_work_queue_from_read_context,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import (
    _write_assignment,
    _write_records,
    _write_roster,
)


def test_queue_from_read_context_matches_public_builder(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, "00100")

    expected = assignment_review_work_queue_to_dict(
        build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    actual = assignment_review_work_queue_to_dict(
        build_assignment_review_work_queue_from_read_context(read_context)
    )

    assert actual == expected


def test_public_queue_builds_assignment_read_context_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    calls = 0
    original = queue_module.build_assignment_review_read_context

    def counted_builder(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        queue_module,
        "build_assignment_review_read_context",
        counted_builder,
    )

    build_assignment_review_work_queue(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert calls == 1


def test_queue_from_context_reuses_exact_context_for_dashboard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    seen: list[tuple[object, bool]] = []
    original = queue_module.build_assignment_review_dashboard_from_read_context

    def counted_dashboard(
        context: object,
        *,
        include_scan_review: bool = True,
    ):
        seen.append((context, include_scan_review))
        return original(  # type: ignore[arg-type]
            context,
            include_scan_review=include_scan_review,
        )

    monkeypatch.setattr(
        queue_module,
        "build_assignment_review_dashboard_from_read_context",
        counted_dashboard,
    )

    build_assignment_review_work_queue_from_read_context(read_context)

    assert seen == [(read_context, False)]


def test_queue_requirement_count_uses_assignment_already_in_read_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    assignments_seen: list[dict[str, object]] = []
    original = queue_module.configured_requirements

    def counted_requirements(assignment: dict[str, object]):
        assignments_seen.append(assignment)
        return original(assignment)  # type: ignore[arg-type]

    monkeypatch.setattr(
        queue_module,
        "configured_requirements",
        counted_requirements,
    )

    build_assignment_review_work_queue_from_read_context(read_context)

    assert len(assignments_seen) == 1
    assert assignments_seen[0]["assignment_id"] == ASSIGNMENT_ID


def test_queue_from_context_rejects_wrong_context_type() -> None:
    with pytest.raises(ReviewWorkQueueError, match="exact AssignmentReviewReadContext"):
        build_assignment_review_work_queue_from_read_context(  # type: ignore[arg-type]
            object()
        )
