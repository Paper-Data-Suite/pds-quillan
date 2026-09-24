"""Issue #414 tests for selected-student projections from one redraw read."""

from __future__ import annotations

from pathlib import Path

import pytest

import quillan.review_student_navigation as navigation_module
import quillan.student_review_status as status_module
from quillan.review_read_context import build_assignment_review_read_context
from quillan.review_student_navigation import (
    ReviewStudentNavigationError,
    build_review_student_navigation,
    build_review_student_navigation_from_read_context,
)
from quillan.student_review_status import (
    StudentReviewStatusError,
    build_student_review_status,
    build_student_review_status_from_read_context,
    student_review_status_to_dict,
)
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID
from tests.test_class_summary_export import (
    _write_assignment,
    _write_records,
    _write_roster,
)


def test_selected_student_status_from_context_matches_public_status(
    tmp_path: Path,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, "00100")

    expected = student_review_status_to_dict(
        build_student_review_status(
            tmp_path,
            CLASS_ID,
            ASSIGNMENT_ID,
            "00100",
        )
    )
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    actual = student_review_status_to_dict(
        build_student_review_status_from_read_context(
            read_context,
            "00100",
        )
    )

    assert actual == expected


def test_selected_student_status_from_context_does_not_repeat_assignment_level_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, "00100")
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    def unexpected_read(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("selected-student projection repeated assignment-level read")

    monkeypatch.setattr(
        status_module,
        "load_quillan_assignment_context",
        unexpected_read,
    )
    monkeypatch.setattr(status_module, "load_class_roster", unexpected_read)
    monkeypatch.setattr(
        status_module,
        "group_response_page_observations_by_student",
        unexpected_read,
    )
    monkeypatch.setattr(
        status_module,
        "load_quillan_student_review_context",
        unexpected_read,
    )

    status = build_student_review_status_from_read_context(
        read_context,
        "00100",
    )

    assert status.student_id == "00100"
    assert status.assignment["title"] == "Synthetic Essay"


def test_selected_student_status_from_context_reuses_exact_assignment_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, "00100")
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    seen: list[object] = []
    original = (
        status_module.load_quillan_student_review_context_from_assignment_context
    )

    def counted_loader(assignment_context, student_id, *, review_policy):
        seen.append(assignment_context)
        return original(
            assignment_context,
            student_id,
            review_policy=review_policy,
        )

    monkeypatch.setattr(
        status_module,
        "load_quillan_student_review_context_from_assignment_context",
        counted_loader,
    )

    build_student_review_status_from_read_context(read_context, "00100")

    assert seen == [read_context.assignment_context]


def test_navigation_from_context_matches_public_navigation(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)

    expected = build_review_student_navigation(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
        "00100",
    )
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    actual = build_review_student_navigation_from_read_context(
        read_context,
        "00100",
    )

    assert actual == expected


def test_navigation_from_context_uses_context_qualified_queue_only(
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
    seen: list[object] = []
    original = navigation_module.build_assignment_review_work_queue_from_read_context

    def unexpected_public_queue(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("context-qualified navigation called public queue builder")

    def counted_context_queue(context):
        seen.append(context)
        return original(context)

    monkeypatch.setattr(
        navigation_module,
        "build_assignment_review_work_queue",
        unexpected_public_queue,
    )
    monkeypatch.setattr(
        navigation_module,
        "build_assignment_review_work_queue_from_read_context",
        counted_context_queue,
    )

    result = build_review_student_navigation_from_read_context(
        read_context,
        "00100",
    )

    assert seen == [read_context]
    assert result.current.student_id == "00100"


def test_context_qualified_projections_reject_wrong_context_type() -> None:
    with pytest.raises(StudentReviewStatusError, match="exact AssignmentReviewReadContext"):
        build_student_review_status_from_read_context(  # type: ignore[arg-type]
            object(),
            "00100",
        )
    with pytest.raises(
        ReviewStudentNavigationError,
        match="exact AssignmentReviewReadContext",
    ):
        build_review_student_navigation_from_read_context(  # type: ignore[arg-type]
            object(),
            "00100",
        )
