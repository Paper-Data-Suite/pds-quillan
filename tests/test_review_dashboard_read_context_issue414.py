"""Issue #414 tests for dashboard reuse of the redraw-scoped read context."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

import quillan.review_dashboard as dashboard_module
import quillan.review_read_context as read_context_module
from quillan.review_dashboard import (
    ReviewDashboardError,
    assignment_review_dashboard_to_dict,
    build_assignment_review_dashboard,
    build_assignment_review_dashboard_from_read_context,
)
from quillan.review_read_context import build_assignment_review_read_context
from tests.review_test_support import ASSIGNMENT_ID, CLASS_ID, STUDENT_ID
from tests.test_class_summary_export import (
    _write_assignment,
    _write_records,
    _write_roster,
)


def test_dashboard_from_read_context_matches_public_builder(tmp_path: Path) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, STUDENT_ID)

    expected = assignment_review_dashboard_to_dict(
        build_assignment_review_dashboard(tmp_path, CLASS_ID, ASSIGNMENT_ID)
    )
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    actual = assignment_review_dashboard_to_dict(
        build_assignment_review_dashboard_from_read_context(read_context)
    )

    assert actual == expected


def test_dashboard_reuses_exact_assignment_context_for_every_student_record_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, STUDENT_ID)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )
    seen_assignment_contexts: list[object] = []
    dashboard_hooks: Any = dashboard_module
    original = (
        dashboard_hooks.load_quillan_student_review_context_from_assignment_context
    )

    def counted_loader(
        assignment_context: Any,
        student_id: Any,
        *,
        review_policy: Any,
    ) -> Any:
        seen_assignment_contexts.append(assignment_context)
        return original(
            assignment_context,
            student_id,
            review_policy=review_policy,
        )

    monkeypatch.setattr(
        dashboard_module,
        "load_quillan_student_review_context_from_assignment_context",
        counted_loader,
    )

    build_assignment_review_dashboard_from_read_context(read_context)

    assert seen_assignment_contexts
    assert all(
        context is read_context.assignment_context
        for context in seen_assignment_contexts
    )


def test_dashboard_from_context_does_not_rebuild_assignment_level_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, STUDENT_ID)
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    def unexpected_rebuild(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("dashboard rebuilt assignment-level read context")

    monkeypatch.setattr(
        dashboard_module,
        "build_assignment_review_read_context",
        unexpected_rebuild,
    )

    dashboard = build_assignment_review_dashboard_from_read_context(read_context)

    assert dashboard.class_id == CLASS_ID
    assert dashboard.assignment_id == ASSIGNMENT_ID


def test_public_dashboard_builds_assignment_read_context_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)
    _write_records(tmp_path, STUDENT_ID)
    calls = 0
    dashboard_hooks: Any = dashboard_module
    original = dashboard_hooks.build_assignment_review_read_context

    def counted_builder(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        dashboard_module,
        "build_assignment_review_read_context",
        counted_builder,
    )

    build_assignment_review_dashboard(tmp_path, CLASS_ID, ASSIGNMENT_ID)

    assert calls == 1


def test_dashboard_preserves_fail_closed_observation_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_assignment(tmp_path)
    _write_roster(tmp_path)

    monkeypatch.setattr(
        read_context_module,
        "group_response_page_observations_by_student",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("synthetic observation failure")
        ),
    )
    read_context = build_assignment_review_read_context(
        tmp_path,
        CLASS_ID,
        ASSIGNMENT_ID,
    )

    assert read_context.observations_by_student is None
    with pytest.raises(
        ReviewDashboardError,
        match="Could not discover routed evidence: synthetic observation failure",
    ):
        build_assignment_review_dashboard_from_read_context(read_context)


def test_dashboard_from_context_rejects_wrong_context_type() -> None:
    with pytest.raises(ReviewDashboardError, match="exact AssignmentReviewReadContext"):
        build_assignment_review_dashboard_from_read_context(
            cast(Any, object())
        )
